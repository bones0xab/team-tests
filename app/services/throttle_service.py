# app/services/throttle_service.py

import os
import time
from typing import Optional, Any

_USE_REDIS = False
_redis_client: Any = None
_fallback_throttle: dict[str, float] = {}
_fallback_escalation: dict[str, str] = {}

# Try to connect to Redis — if unavailable, fall back to in-memory
def _connect_redis(retries: int = 5, delay: float = 2.0):
    global _USE_REDIS, _redis_client
    try:
        from redis import Redis  # type: ignore[import-untyped]
        for attempt in range(retries):
            try:
                _client = Redis(
                    host=os.getenv("REDIS_HOST", "redis"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    db=0,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                _client.ping()
                _redis_client = _client
                _USE_REDIS = True
                print("[THROTTLE] Using Redis for throttling")
                return
            except Exception as e:
                print(f"[THROTTLE] Redis attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(delay)
        print("[THROTTLE] Redis unavailable — using in-memory fallback")
    except ImportError:
        print("[THROTTLE] Redis package not installed — using in-memory fallback")

_connect_redis()

class ThrottleService:

    def is_throttled(self, key: str, seconds: int) -> bool:
        if _USE_REDIS and _redis_client is not None:
            return bool(_redis_client.exists(f"throttle:{key}"))
        last = _fallback_throttle.get(key, 0.0)
        return (time.time() - last) < seconds

    def mark(self, key: str, seconds: int) -> None:
        if _USE_REDIS and _redis_client is not None:
            _redis_client.setex(f"throttle:{key}", seconds, "1")
        else:
            _fallback_throttle[key] = time.time()

    def clear(self, key: str) -> None:
        if _USE_REDIS and _redis_client is not None:
            _redis_client.delete(f"throttle:{key}")
        else:
            _fallback_throttle.pop(key, None)


class EscalationService:

    def set_pending(self, project_key: str, alert_id: int, timeout_seconds: int = 900) -> None:
        if _USE_REDIS and _redis_client is not None:
            _redis_client.setex(f"escalation:{project_key}", timeout_seconds, str(alert_id))
        else:
            _fallback_escalation[project_key] = str(alert_id)

    def get_pending(self, project_key: str) -> Optional[str]:
        if _USE_REDIS and _redis_client is not None:
            return _redis_client.get(f"escalation:{project_key}")
        return _fallback_escalation.get(project_key)

    def clear_pending(self, project_key: str) -> None:
        if _USE_REDIS and _redis_client is not None:
            _redis_client.delete(f"escalation:{project_key}")
        else:
            _fallback_escalation.pop(project_key, None)

    def is_pending(self, project_key: str) -> bool:
        return self.get_pending(project_key) is not None