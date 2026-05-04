# tests/test_throttle.py — VERSION FINALE
import pytest
from unittest.mock import MagicMock

def test_throttle_with_redis():
    """Test throttle avec Redis simulé"""
    from app.services.throttle_service import ThrottleService
    
    ts = ThrottleService()
    
    # Mock Redis et forcer mode Redis
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0  # int, pas False
    mock_redis.set.return_value = True
    
    ts._redis = mock_redis
    ts._use_redis = True  # ← FORCER ICI
    
    result = ts.is_throttled_or_mark("alert:TEST", 3600)
    assert result == False
    mock_redis.set.assert_called_once()


def test_throttle_memory_fallback():
    """Test throttle fallback mémoire quand Redis down"""
    from app.services.throttle_service import ThrottleService
    
    ts = ThrottleService()
    
    # Forcer mode mémoire
    ts._use_redis = False
    ts._mem = {}  # ← Vider le cache mémoire
    
    result = ts.is_throttled_or_mark("alert:TEST2", 3600)
    assert result == False  # Premier appel passe
    
    result2 = ts.is_throttled_or_mark("alert:TEST2", 3600)
    assert result2 == True  # Deuxième appel throttle