# services/Normalisation.py
from typing import Dict, Any
from adapters.jira import jira_canonical_status
from datetime import datetime, timezone
from dateutil import parser
#French status mapping for your friend's Jira
STATUS_CATEGORY_MAP = {
    "Revue en cours": "indeterminate",  # In review
    "En cours": "indeterminate",         # In progress
    "À faire": "new",                    # To do
    "Terminé(e)": "done",                # Done
}

# Standard Jira category mapping to our internal format
CATEGORY_TO_INTERNAL = {
    "new": "todo",
    "indeterminate": "in_progress",  #  THIS IS THE KEY FIX
    "done": "done",
}

def normalize_issue(raw: dict) -> Dict[str, Any]:
    """
    Normalize a Jira issue from API format to our internal format.
    Handles French statuses and custom workflows.
    """
    fields = raw.get("fields", {})
    
    # Extract status information
    status = fields.get("status", {})
    status_name = status.get("name", "Unknown")
    
    # Get Jira's category key (new, indeterminate, done)
    jira_category = status.get("statusCategory", {}).get("key", "unknown")
    
    # Map to our internal format (todo, in_progress, done)
    status_category = CATEGORY_TO_INTERNAL.get(jira_category, "unknown")
    
    # Extract assignee
    assignee_obj = fields.get("assignee")
    assignee = assignee_obj.get("displayName") if assignee_obj else None
    
    # Calculate days since last update
    updated_str = fields.get("updated", "")
    updated_dt = None
    days_since_update = 0
    
    if updated_str:
        # Handle timezone formats: both "2024-01-15T10:30:00.000+0100" and "+01:00"
        if updated_str[-3] == ":":
            updated_str = updated_str[:-3] + updated_str[-2:]
        
        try:
            updated_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - updated_dt
            days_since_update = max(0, delta.days)
        except (ValueError, AttributeError):
            days_since_update = 0
    else:
        days_since_update = 0
    
    return {
        "id": raw.get("id"),
        "key": raw.get("key"),
        "summary": fields.get("summary", ""),
        "status_name": status_name,
        "status_category": status_category,  # Now correctly mapped!
        "assignee": assignee,
        "updated_at": updated_dt,
        "days_since_update": days_since_update,
    }