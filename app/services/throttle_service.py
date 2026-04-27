from __future__ import annotations

import logging
import os
import time
from typing import Dict, Optional, Tuple, cast

import redis

from app.services.redis_typing import RedisStrClient

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Client Redis global — partagé par ThrottleService et EscalationService
# Importé dans webhook.py : from app.services.throttle_service import _redis_client, _USE_REDIS
# ─────────────────────────────────────────────────────────────────────────────

_REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
_REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

_redis_client: Optional[RedisStrClient] = None   # type annoté avec le Protocol
_USE_REDIS:    bool = False

try:
    _raw_client = redis.Redis(
        host=_REDIS_HOST,
        port=_REDIS_PORT,
        decode_responses=True,        # runtime → retourne str, jamais bytes
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    _raw_client.ping()
    # cast() dit à Pyright : "ce client suit le Protocol RedisStrClient"
    # Sans cast, Pyright voit redis.Redis (ResponseT=Unknown) → Awaitable[Unknown]
    _redis_client = cast(RedisStrClient, _raw_client)
    _USE_REDIS    = True
    logger.info("✅ throttle_service — Redis disponible (%s:%s)", _REDIS_HOST, _REDIS_PORT)
except Exception as exc:
    _redis_client = None
    _USE_REDIS    = False
    logger.warning("⚠️  throttle_service — Redis indisponible, mode mémoire : %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# ThrottleService — empêche les doublons de notification
# ─────────────────────────────────────────────────────────────────────────────

class ThrottleService:
    """
    Gère le throttle de notifications via Redis (ou dict mémoire si Redis absent).

    Clés Redis visibles dans ton MONITOR :
      throttle:{project_key}:{alert_type}:{level}
      throttle:portfolio:digest
    """

    def __init__(self) -> None:
        # RedisStrClient (Protocol) — Pyright connaît tous les types de retour
        self._redis:     Optional[RedisStrClient] = _redis_client
        self._use_redis: bool                     = _USE_REDIS
        self._mem:       Dict[str, float]          = {}   # fallback mémoire

    def is_throttled(self, key: str, seconds: int = 3600) -> bool:
        """True si la clé est encore dans sa fenêtre de throttle."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                exists: int = self._redis.exists(full_key)   # int ✅ (Protocol)
                return bool(exists)
            except redis.RedisError as exc:
                logger.error("ThrottleService.is_throttled [%s]: %s", full_key, exc)
                return False
        return time.monotonic() < self._mem.get(full_key, 0.0)

    def mark(self, key: str, seconds: int = 3600) -> None:
        """Pose le throttle pour `seconds` secondes (SET NX EX)."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                self._redis.set(full_key, "1", ex=seconds, nx=True)
            except redis.RedisError as exc:
                logger.error("ThrottleService.mark [%s]: %s", full_key, exc)
            return
        self._mem[full_key] = time.monotonic() + seconds
        
    def is_throttled_or_mark(self, key: str, seconds: int = 3600) -> bool:
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                result = self._redis.set(full_key, "1", ex=seconds, nx=True)
                return result is None   # None = key existed = already throttled
            except Exception as exc:
                logger.error("ThrottleService.is_throttled_or_mark [%s]: %s", full_key, exc)
                return False
        now = time.monotonic()
        if now < self._mem.get(full_key, 0.0):
            return True
        self._mem[full_key] = now + seconds
        return False

    def clear(self, key: str) -> None:
        """Supprime le throttle (permet un re-envoi immédiat)."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                self._redis.delete(full_key)
            except redis.RedisError as exc:
                logger.error("ThrottleService.clear [%s]: %s", full_key, exc)
            return
        self._mem.pop(full_key, None)

    def get_ttl(self, key: str) -> int:
        """TTL restant en secondes. -1=persistant, -2=absent."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                ttl: int = self._redis.ttl(full_key)   # int ✅ (Protocol)
                return ttl
            except redis.RedisError:
                return -2
        remaining = int(self._mem.get(full_key, 0.0) - time.monotonic())
        return max(remaining, -2)


# ─────────────────────────────────────────────────────────────────────────────
# EscalationService — gère l'état d'escalade avec cache local anti-spam Redis
# ─────────────────────────────────────────────────────────────────────────────

class EscalationService:
    """
    Clés Redis :  escalation:{project_key} → "pending"

    CACHE LOCAL 10s : évite les centaines de GET/s visibles dans ton MONITOR.
    """

    ESCALATION_TTL_SECONDS: int  = 3600
    _LOCAL_CACHE_TTL:       float = 10.0

    def __init__(self) -> None:
        self._redis:     Optional[RedisStrClient]                    = _redis_client
        self._use_redis: bool                                        = _USE_REDIS
        self._cache:     Dict[str, Tuple[Optional[str], float]] = {}

    def is_pending(self, project_key: str) -> bool:
        """Vérifie si une escalade est en attente (cache local 10s)."""
        now = time.monotonic()
        cached_val, cached_at = self._cache.get(project_key, (None, 0.0))

        if now - cached_at < self._LOCAL_CACHE_TTL:
            return cached_val == "pending"   # cache encore valide → pas de Redis

        if not self._use_redis or self._redis is None:
            return False

        try:
            val: Optional[str] = self._redis.get(f"escalation:{project_key}")  # str|None ✅
        except redis.RedisError as exc:
            logger.error("EscalationService.is_pending [%s]: %s", project_key, exc)
            return False

        self._cache[project_key] = (val, now)
        return val == "pending"

    def set_pending(self, project_key: str, ttl_seconds: Optional[int] = None) -> None:
        """Marque le projet comme 'escalade en attente'."""
        ttl = ttl_seconds or self.ESCALATION_TTL_SECONDS
        if self._use_redis and self._redis is not None:
            try:
                self._redis.set(f"escalation:{project_key}", "pending", ex=ttl)
            except redis.RedisError as exc:
                logger.error("EscalationService.set_pending [%s]: %s", project_key, exc)
        self._cache[project_key] = ("pending", time.monotonic())

    def clear_pending(self, project_key: str) -> None:
        """Efface l'état d'escalade après traitement."""
        if self._use_redis and self._redis is not None:
            try:
                self._redis.delete(f"escalation:{project_key}")
            except redis.RedisError as exc:
                logger.error("EscalationService.clear_pending [%s]: %s", project_key, exc)
        self._cache[project_key] = (None, time.monotonic())

    def invalidate_cache(self, project_key: Optional[str] = None) -> None:
        """Invalide le cache local (tout ou un projet)."""
        if project_key is None:
            self._cache.clear()
        else:
            self._cache.pop(project_key, None)