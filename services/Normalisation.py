# services/normalisation.py

from adapters.jira import jira_canonical_status
from datetime import datetime, timezone

def normalize_issue(raw: dict) -> dict:
    fields = raw["fields"]
    status = fields["status"]

    status_name = status["name"]
    jira_status_category = status["statusCategory"]["name"]

    canonical = jira_canonical_status(
        status_name=status_name,
        jira_status_category=jira_status_category,
    )

    updated_str = fields["updated"]

    # Fix timezone Jira (+0100 → +01:00)
    if "+" in updated_str:
        updated_str = updated_str[:-2] + ":" + updated_str[-2:]

    updated_at = datetime.fromisoformat(updated_str)


    return {
        "id": raw["id"],
        "key": raw["key"],
        "summary": fields["summary"],
        "status_name": status_name,
        "status_category": canonical,  # 🔥 FIXED
        "assignee": (
            fields["assignee"]["displayName"]
            if fields.get("assignee")
            else None
        ),
        "updated_at": updated_at,
        "days_since_update": (datetime.now(timezone.utc) - updated_at).days,
    }
