# services/Normalisation.py

from datetime import timezone
from typing import Dict, List, Optional
from dateutil import parser
from adapters.jira import jira_canonical_status


def _jira_to_utc(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    dt = parser.parse(dt_str)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _extract_user(user: Optional[Dict]) -> Optional[Dict]:
    if not user:
        return None
    return {
        "id": user.get("accountId") or user.get("name") or user.get("key"),
        "name": user.get("displayName"),
    }


def normalize_issue(raw: Dict) -> Dict:
    fields = raw.get("fields", {})

    status = fields.get("status") or {}
    status_name = status.get("name")
    jira_status_category = (status.get("statusCategory") or {}).get("name")

    canonical = jira_canonical_status(
        status_name=status_name,
        jira_status_category=jira_status_category,
    )

    # ── Parse the timestamp exactly once ─────────────────────────────────
    updated_raw = fields.get("updated")
    updated_at_utc = None
    days_since_update = None

    if updated_raw:
        from datetime import datetime
        updated_dt = parser.parse(updated_raw).astimezone(timezone.utc)
        updated_at_utc = (
            updated_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )
        days_since_update = (datetime.now(timezone.utc) - updated_dt).days

    assignee = _extract_user(fields.get("assignee"))
    issuelinks = fields.get("issuelinks") or []

    links = []
    for l in issuelinks:
        t = (l.get("type") or {}).get("name")
        inward = l.get("inwardIssue")
        outward = l.get("outwardIssue")
        links.append({
            "type": t,
            "inward": {
                "id": inward.get("id"),
                "key": inward.get("key"),
            } if inward else None,
            "outward": {
                "id": outward.get("id"),
                "key": outward.get("key"),
            } if outward else None,
        })

    missing = []
    if not raw.get("id"):
        missing.append("id")
    if not raw.get("key"):
        missing.append("key")
    if not fields.get("summary"):
        missing.append("fields.summary")
    if not updated_raw:
        missing.append("fields.updated")
    if status_name and canonical == "unknown":
        missing.append(f"status_map:{status_name}")

    return {
        "identity": {
            "issue_id": raw.get("id"),
            "issue_key": raw.get("key"),
            "summary": fields.get("summary"),
        },
        "temporality": {
            "updated_at_utc": updated_at_utc,
            "days_since_update": days_since_update,
        },
        "semantics": {
            "status_canonical": canonical,
        },
        "actors": {
            "assignee": assignee,
        },
    }



def normalize_project(raw: Dict) -> Dict:
    category = raw.get("projectCategory") or {}

    missing = []
    if not raw.get("id"):
        missing.append("id")
    if not raw.get("key"):
        missing.append("key")
    if not raw.get("name"):
        missing.append("name")


    return {
        "identity": {
            "provider": "jira",
            "project_id": raw.get("id"),
            "project_key": raw.get("key"),
            "project_name": raw.get("name"),
            "self_url": raw.get("self")
        },
        "classification": {
            "type": raw.get("projectTypeKey"),
            "category": {
                "id": category.get("id"),
                "name": category.get("name"),
                "description": category.get("description"),
            } if category else None,
        },
        "governance": {
            "archived": raw.get("archived", False),
        },
        "metadata": {
            "avatar_urls": raw.get("avatarUrls"),
        },
        "resilience": {
            "missing_fields": missing,
        },
    }

def normalize_projects(raw_list: List[Dict]) -> List[Dict]:
    return [normalize_project(p) for p in raw_list]
