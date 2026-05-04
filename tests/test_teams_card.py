import os
from dotenv import load_dotenv
load_dotenv()

from app.services.teams_notification_service import TeamsNotificationService

notifier = TeamsNotificationService()

fake_projects = [
    {
        "project_key": "HPCMOROCCO",
        "severity": "CRITICAL",
        "summary": "High WIP ratio detected",
        "total": 2213,
        "stale": 126,
        "wip_pct": 15.8,
        "jira_ticket": None,
    },
    {
        "project_key": "DEVTEAM",
        "severity": "WARNING",
        "summary": "Stale issues accumulating",
        "total": 450,
        "stale": 40,
        "wip_pct": 22.1,
        "jira_ticket": None,
    },
]

notifier.send_consolidated_digest(fake_projects)
print("Done — check Teams!")