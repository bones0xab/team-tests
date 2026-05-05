from app.services.throttle_service import ThrottleService
from app.services.teams_notification_service import TeamsNotificationService

throttle = ThrottleService()
notifier = TeamsNotificationService()

def send_alert_throttled(
    project_key: str,
    summary: str,
    description: str = "",
    severity: str = "CRITICAL",
    throttle_seconds: int = 3600,
) -> bool:
    throttle_key = f"{project_key}:{severity}:alert"
    if throttle.is_throttled_or_mark(throttle_key, throttle_seconds):
        print(f"[ALERT] SKIP (throttled) - {project_key} {severity}")
        return False
    notifier.send_critical_alert(
        project_key=project_key,
        summary=summary,
        description=description,
    )
    print(f"[ALERT] SENT - {project_key} {severity}")
    return True
