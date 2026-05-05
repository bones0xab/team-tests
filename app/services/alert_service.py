from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

import redis

from app.services.redis_typing import RedisStrClient

logger = logging.getLogger(__name__)


class AlertService:
    """
    Déduplication d'alertes via Redis Distributed Lock.

    PRINCIPE :
      1. should_send_alert() → SET NX EX : 1 seul thread gagne, les autres skip.
      2. mark_alert_sent()   → stocke le hash du contenu pour éviter les doublons
                               même si le lock est expiré.
    """

    LOCK_TTL_SECONDS:  int = 300   # fenêtre de lock (5 min)
    DEDUP_TTL_SECONDS: int = 600   # fenêtre de déduplication (10 min)

    def __init__(self, redis_host: str = "redis", redis_port: int = 6379) -> None:
        self._memory_mode = False
        self._memory_locks: Dict[str, float] = {}
        self._memory_dedup: Dict[str, Tuple[str, float]] = {}
        try:
            _raw = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self.redis: RedisStrClient = cast(RedisStrClient, _raw)
            self._verify_redis()
        except Exception as exc:  
            logger.warning("⚠️ AlertService — Redis indisponible, mode mémoire : %s", exc)
            self._memory_mode = True

    def _verify_redis(self) -> None:
        try:
            self.redis.ping()
            logger.info("✅ AlertService — Redis opérationnel")
        except Exception as exc:  # ← CATCH TOUT
            logger.error("❌ AlertService — Redis inaccessible : %s", exc)

    # ─── Hash de contenu ──────────────────────────────────────────────────────

    def _compute_payload_hash(self, report_data: Dict[str, Any]) -> str:
        """Hash stable des métriques clés — indépendant du timestamp."""
        key_data = {
            "at_risk_count":  report_data.get("at_risk_count"),
            "warning_count":  report_data.get("warning_count"),
            "total_stale":    report_data.get("total_stale"),
            "total_projects": report_data.get("total_projects"),
            "critical_projects": sorted(
                p.get("key", p.get("project_key", ""))
                for p in report_data.get("critical_projects", [])
            ),
        }
        return hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()[:16]

    # ─── Lock distribué ───────────────────────────────────────────────────────

    def should_send_alert(
        self,
        report_type: str,
        report_data: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """(True, raison) → envoyer | (False, raison) → skip."""
        payload_hash = self._compute_payload_hash(report_data)
        lock_key  = f"alert_lock:{report_type}"
        dedup_key = f"alert_dedup:{report_type}:{payload_hash}"

        # 1. Déduplication par contenu
        if self.redis.exists(dedup_key):             # int ✅
            ttl: int = self.redis.ttl(dedup_key)     # int ✅
            logger.info("⏭️  SKIP doublon — %s hash=%s TTL=%ss", report_type, payload_hash, ttl)
            return False, f"duplicate_content (expires in {ttl}s)"

        # 2. Lock distribué SET NX EX
        # Avec le Protocol, .set() → Optional[str] ✅ (pas Awaitable)
        lock_result: Optional[str] = self.redis.set(
            lock_key,
            f"locked_at:{datetime.now(timezone.utc).isoformat()}",
            nx=True,
            ex=self.LOCK_TTL_SECONDS,
        )
        acquired = lock_result is not None

        if not acquired:
            ttl = self.redis.ttl(lock_key)
            logger.info("⏭️  SKIP lock-actif — %s TTL=%ss", report_type, ttl)
            return False, f"lock_active (expires in {ttl}s)"

        logger.info("🔒 Lock acquis — %s hash=%s", report_type, payload_hash)
        return True, f"ok (hash={payload_hash})"

    def mark_alert_sent(self, report_type: str, report_data: Dict[str, Any]) -> None:
        """Enregistre le hash après envoi réussi."""
        payload_hash = self._compute_payload_hash(report_data)
        dedup_key    = f"alert_dedup:{report_type}:{payload_hash}"
        now = datetime.now(timezone.utc).timestamp()
        if self._memory_mode:
            self._memory_dedup[dedup_key] = (payload_hash, now + self.DEDUP_TTL_SECONDS)
        else:
            self.redis.set(
                dedup_key,
                json.dumps({
                    "sent_at":     datetime.now(timezone.utc).isoformat(),
                    "at_risk":     report_data.get("at_risk_count"),
                    "total_stale": report_data.get("total_stale"),
                    "hash":        payload_hash,
                }),
                ex=self.DEDUP_TTL_SECONDS,
            )
        logger.info("✅ Alerte enregistrée — %s hash=%s TTL=%ss",
                    report_type, payload_hash, self.DEDUP_TTL_SECONDS)

    def release_lock(self, report_type: str) -> None:
        """Libère le lock manuellement après erreur."""
        lock_key = f"alert_lock:{report_type}"
        if self._memory_mode:
            self._memory_locks.pop(lock_key, None)
            deleted = 1
        else:
            deleted: int = self.redis.delete(lock_key)
        logger.info("🔓 Lock libéré — %s (deleted=%s)", report_type, deleted)

    # ─── Diagnostic ───────────────────────────────────────────────────────────

    def get_redis_status(self) -> Dict[str, Any]:
        """GET /api/debug/redis — état complet pour debug équipe."""
        try:
            info: Dict[str, Any] = self.redis.info()                    # Dict ✅
            alert_keys:      List[str] = self.redis.keys("alert_*")     # List[str] ✅
            throttle_keys:   List[str] = self.redis.keys("throttle:*")  # List[str] ✅
            escalation_keys: List[str] = self.redis.keys("escalation:*")

            key_details: Dict[str, Any] = {}
            for k in alert_keys:
                val: Optional[str] = self.redis.get(k)   # str|None ✅
                ttl: int           = self.redis.ttl(k)   # int ✅
                key_details[k] = {
                    "value":       val,
                    "ttl_seconds": ttl,
                    "expires_in":  f"{ttl}s" if ttl > 0 else "persistent",
                }

            return {
                "status":                 "ok",
                "redis_version":          info.get("redis_version"),
                "connected_clients":      info.get("connected_clients"),
                "used_memory_human":      info.get("used_memory_human"),
                "uptime_in_seconds":      info.get("uptime_in_seconds"),
                "alert_keys":             key_details,
                "total_alert_keys":       len(alert_keys),
                "total_throttle_keys":    len(throttle_keys),
                "total_escalation_keys":  len(escalation_keys),
                "throttle_keys_sample":   throttle_keys[:10],
                "escalation_keys_sample": escalation_keys[:10],
            }
        except Exception as exc:
            logger.exception("get_redis_status error")
            return {"status": "error", "message": str(exc)}

    def get_throttle_details(self) -> Dict[str, Any]:
        """GET /api/debug/redis/throttle — détail throttle + escalation."""
        try:
            all_keys: List[str] = (
                self.redis.keys("throttle:*") + self.redis.keys("escalation:*")
            )
            result: Dict[str, Any] = {}
            for k in all_keys:
                result[k] = {
                    "value":       self.redis.get(k),   # str|None ✅
                    "ttl_seconds": self.redis.ttl(k),   # int ✅
                }
            return {"status": "ok", "total": len(result), "keys": result}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}