from __future__ import annotations

import logging
import os
from dotenv import load_dotenv
load_dotenv()
import time
from typing import Dict, Optional, Tuple, cast

import redis

from app.services.redis_typing import RedisStrClient

logger = logging.getLogger(__name__)


def _get_redis_client() -> tuple[Optional[RedisStrClient], bool]:
    """Crée le client Redis dynamiquement (lit .env à chaque appel si besoin)."""
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    try:
        _raw_client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        _raw_client.ping()
        logger.info("✅ throttle_service — Redis disponible (%s:%s)", host, port)
        return cast(RedisStrClient, _raw_client), True
    except Exception as exc:
        logger.warning("⚠️  throttle_service — Redis indisponible, mode mémoire : %s", exc)
        return None, False


_redis_client, _USE_REDIS = _get_redis_client()


class ThrottleService:
    """
    Gère le throttle de notifications via Redis (ou dict mémoire si Redis absent).
    """

    def __init__(self) -> None:
        self._redis:     Optional[RedisStrClient] = _redis_client
        self._use_redis: bool                     = _USE_REDIS
        self._mem:       Dict[str, float]          = {}

    def is_throttled(self, key: str, seconds: int = 3600) -> bool:
        """True si la clé est encore dans sa fenêtre de throttle."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                exists: int = self._redis.exists(full_key)
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
        """Atomique : True si déjà throttlé, sinon marque et retourne False."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                result = self._redis.set(full_key, "1", ex=seconds, nx=True)
                return result is None
            except Exception as exc:
                logger.error("ThrottleService.is_throttled_or_mark [%s]: %s", full_key, exc)
                return False
        now = time.monotonic()
        if now < self._mem.get(full_key, 0.0):
            return True
        self._mem[full_key] = now + seconds
        return False

    def clear(self, key: str) -> None:
        """Supprime le throttle."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                self._redis.delete(full_key)
            except redis.RedisError as exc:
                logger.error("ThrottleService.clear [%s]: %s", full_key, exc)
            return
        self._mem.pop(full_key, None)

    def get_ttl(self, key: str) -> int:
        """TTL restant en secondes."""
        full_key = f"throttle:{key}"
        if self._use_redis and self._redis is not None:
            try:
                ttl: int = self._redis.ttl(full_key)
                return ttl
            except redis.RedisError:
                return -2
        remaining = int(self._mem.get(full_key, 0.0) - time.monotonic())
        return max(remaining, -2)


class EscalationService:
    """
    Clés Redis : escalation:{project_key} → "pending"
    Cache local 10s pour éviter le spam Redis.
    """

    ESCALATION_TTL_SECONDS: int  = 3600
    _LOCAL_CACHE_TTL:       float = 10.0

    def __init__(self) -> None:
        self._redis:     Optional[RedisStrClient]                    = _redis_client
        self._use_redis: bool                                        = _USE_REDIS
        self._cache:     Dict[str, Tuple[Optional[str], float]] = {}

    def is_pending(self, project_key: str) -> bool:
        now = time.monotonic()
        cached_val, cached_at = self._cache.get(project_key, (None, 0.0))
        if now - cached_at < self._LOCAL_CACHE_TTL:
            return cached_val == "pending"
        if not self._use_redis or self._redis is None:
            return False
        try:
            val: Optional[str] = self._redis.get(f"escalation:{project_key}")
        except redis.RedisError as exc:
            logger.error("EscalationService.is_pending [%s]: %s", project_key, exc)
            return False
        self._cache[project_key] = (val, now)
        return val == "pending"

    def set_pending(self, project_key: str, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds or self.ESCALATION_TTL_SECONDS
        if self._use_redis and self._redis is not None:
            try:
                self._redis.set(f"escalation:{project_key}", "pending", ex=ttl)
            except redis.RedisError as exc:
                logger.error("EscalationService.set_pending [%s]: %s", project_key, exc)
        self._cache[project_key] = ("pending", time.monotonic())

    def clear_pending(self, project_key: str) -> None:
        if self._use_redis and self._redis is not None:
            try:
                self._redis.delete(f"escalation:{project_key}")
            except redis.RedisError as exc:
                logger.error("EscalationService.clear_pending [%s]: %s", project_key, exc)
        self._cache[project_key] = (None, time.monotonic())

    def invalidate_cache(self, project_key: Optional[str] = None) -> None:
        if project_key is None:
            self._cache.clear()
        else:
            self._cache.pop(project_key, None)