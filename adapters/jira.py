# adapters/jira_status_adapter.py

from typing import Optional

DEFAULT_STATUS_MAP = {
    "To Do": "todo",
    "Backlog": "todo",
    "New": "todo",
    "Selected for Development": "todo",

    # IN PROGRESS
    "In Progress": "in_progress",
    "In Review": "in_progress",
    "Code Review": "in_progress",
    "Testing": "in_progress",

    # DONE
    "Done": "done",
    "Closed": "done",
    "Resolved": "done",
}


def jira_canonical_status(status_name: Optional[str],jira_status_category: Optional[str]) -> str:
    # 1️⃣ Prefer Jira statusCategory (already semantic)
    if jira_status_category in ("To Do", "In Progress", "Done"):
        mapped = DEFAULT_STATUS_MAP.get(jira_status_category)
        if mapped:
            return mapped

    # 2️⃣ Fallback to explicit status name
    if status_name:
        mapped = DEFAULT_STATUS_MAP.get(status_name)
        if mapped:
            return mapped

    # 3️⃣ Guardrail
    return "unknown"
