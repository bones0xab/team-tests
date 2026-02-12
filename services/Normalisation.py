# services/Normalisation.py
from adapters.jira import jira_canonical_status
from datetime import datetime, timezone

def normalize_issue(raw: dict) -> dict:
    """Normalize a Jira issue into standard format"""
    fields = raw["fields"]
    status = fields["status"]

    status_name = status["name"]
    jira_status_category = status["statusCategory"]["name"]

    canonical = jira_canonical_status(
        status_name=status_name,
        jira_status_category=jira_status_category,
    )

    updated_str = fields["updated"]

    # Fix timezone formats
    # 1. UTC format with 'Z' → '+00:00'
    if updated_str.endswith("Z"):
        updated_str = updated_str[:-1] + "+00:00"
    
    # 2. Jira format without colon (+0100 → +01:00 ou -0500 → -05:00)
    elif ("+" in updated_str or "-" in updated_str[10:]):  # Ignorer le "-" dans la date
        if updated_str[-3] != ":":  # Si pas déjà au bon format
            updated_str = updated_str[:-2] + ":" + updated_str[-2:]

    updated_at = datetime.fromisoformat(updated_str)
    
    # Fix: days_since_update ne peut pas être négatif
    days_since_update = (datetime.now(timezone.utc) - updated_at).days
    days_since_update = max(0, days_since_update)

    return {
        "id": raw["id"],
        "key": raw["key"],
        "summary": fields["summary"],
        "status_name": status_name,
        "status_category": canonical,
        "assignee": (
            fields["assignee"]["displayName"]
            if fields.get("assignee")
            else None
        ),
        "updated_at": updated_at,
        "days_since_update": days_since_update,
    }