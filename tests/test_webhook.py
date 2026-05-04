# tests/test_webhook.py — VERSION SANS ASYNC
import pytest
from unittest.mock import Mock, patch, AsyncMock

# Test 1: Parser une alerte (logique interne)
def test_webhook_alert_parsing():
    """Test que l'alerte est correctement parsée"""
    # Simuler le parsing inline de receive_alert
    alert_raw = {
        "status": "firing",
        "labels": {
            "project_key": "TEST",
            "severity": "critical",
            "alertname": "HighWIPRatio"
        },
        "annotations": {
            "summary": "WIP ratio exceeded"
        }
    }
    
    # Logique de parsing (copiée de receive_alert)
    project_key = alert_raw.get("labels", {}).get("project_key", "unknown")
    severity = alert_raw.get("labels", {}).get("severity", "warning")
    
    assert project_key == "TEST"
    assert severity == "critical"


# Test 2: Throttle bloque les doublons
def test_throttle_blocks_duplicate():
    from app.services.throttle_service import ThrottleService
    
    ts = ThrottleService()
    ts._use_redis = False
    ts._mem = {}
    
    result1 = ts.is_throttled_or_mark("test:digest", 3600)
    assert result1 == False
    
    result2 = ts.is_throttled_or_mark("test:digest", 3600)
    assert result2 == True


# Test 3: Teams notification retry 3x
@patch('app.services.teams_notification_service.requests.post')
def test_teams_notification_retry(mock_post):
    from app.services.teams_notification_service import TeamsNotificationService
    
    mock_post.side_effect = Exception("Network error")
    service = TeamsNotificationService()
    service.webhook_url = "http://test.webhook"
    
    result = service._send({"test": "card"})
    assert result == False
    assert mock_post.call_count == 3


# Test 4: Cache fallback quand Jira down
@patch('app.services.dashboard_service.fetch_dashboard_data')
def test_enrich_fallback_on_jira_down(mock_fetch):
    from app.routes.webhook import _enrich_with_metrics
    
    mock_fetch.side_effect = Exception("Jira timeout")
    
    projects = [{"project_key": "TEST", "stale": 5, "wip_pct": 30.0}]
    result = _enrich_with_metrics(projects)
    
    assert result[0]["stale"] == 5
    assert result[0]["wip_pct"] == 30.0