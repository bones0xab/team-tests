# app/services/incident_service.py

import time
from typing import Optional
from app.services.auth_helpers import build_jira_session, load_jira_config


class IncidentService:

    def __init__(self):
        self.config  = load_jira_config()
        self.session = build_jira_session(self.config)

    def create_incident(
        self,
        project_key: str,
        summary: str,
        description: str,
        severity: str = "CRITICAL",
        assignee: Optional[str] = None,
    ) -> Optional[str]:
        payload = {
            "fields": {
                "project":     {"key": project_key},
                "summary":     summary,
                "description": description,
                "issuetype":   {"name": "Task"},
                "priority":    {"name": "Critical" if severity == "CRITICAL" else "High"},
                "labels":      ["auto-incident", "observability", severity.lower()],
            }
        }

        if assignee:
            payload["fields"]["assignee"] = {"name": assignee}

        try:
            time.sleep(1)  # space out Jira requests to avoid 429 rate limiting
            response = self.session.post(
                f"{self.config.base_url}/rest/api/2/issue",
                json=payload,
            )
            response.raise_for_status()
            ticket_key = response.json().get("key")
            print(f"[INCIDENT] Created ticket: {ticket_key}")
            return ticket_key

        except Exception as e:
            print(f"[INCIDENT] Failed to create ticket: {e}")
            return None

    def get_issue_url(self, ticket_key: str) -> str:
        return f"{self.config.base_url}/browse/{ticket_key}"