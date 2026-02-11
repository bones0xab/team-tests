# services/normalisation.py
from datetime import datetime, timezone
from adapters.jira import jira_canonical_status


def _jira_to_utc(dt_str: str | None) -> str | None:
    # Jira: "2026-02-08T11:54:12.400+0100"
    if not dt_str:
        return None
    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_issue(raw: dict) -> dict:
    fields = raw.get("fields", {})

    status = fields.get("status") or {}
    status_name = status.get("name")
    jira_status_category = (status.get("statusCategory") or {}).get("name")

    canonical = jira_canonical_status(
        status_name=status_name,
        jira_status_category=jira_status_category,
    )

    # times (UTC strings)
    created_at_utc = _jira_to_utc(fields.get("created"))
    updated_at_utc = _jira_to_utc(fields.get("updated"))
    resolved_at_utc = _jira_to_utc(fields.get("resolutiondate"))

    # compute days_since_update (based on UTC)
    days_since_update = None
    if fields.get("updated"):
        updated_dt = datetime.strptime(fields["updated"], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(timezone.utc)
        days_since_update = (datetime.now(timezone.utc) - updated_dt).days

    assignee = fields.get("assignee") or None
    reporter = fields.get("reporter") or None
    parent = fields.get("parent") or None
    issuelinks = fields.get("issuelinks") or []

    # dependency graph (basic)
    links = []
    for l in issuelinks:
        t = (l.get("type") or {}).get("name")
        inward = l.get("inwardIssue")
        outward = l.get("outwardIssue")
        links.append({
            "type": t,
            "inward": {"id": inward.get("id"), "key": inward.get("key")} if inward else None,
            "outward": {"id": outward.get("id"), "key": outward.get("key")} if outward else None,
        })

    # resilience report (basic)
    missing = []
    if not raw.get("id"): missing.append("id")
    if not raw.get("key"): missing.append("key")
    if not fields.get("summary"): missing.append("fields.summary")
    if not fields.get("updated"): missing.append("fields.updated")
    if status_name and canonical == "unknown": missing.append(f"status_map:{status_name}")

    return {
        # 1) Identité
        "identity": {
            "provider": "jira",
            "issue_id": raw.get("id"),
            "issue_key": raw.get("key"),
            "self_url": raw.get("self"),
            "summary": fields.get("summary"),
            "project": {
                "id": (fields.get("project") or {}).get("id"),
                "key": (fields.get("project") or {}).get("key"),
                "name": (fields.get("project") or {}).get("name"),
            },
            "issue_type": {
                "id": (fields.get("issuetype") or {}).get("id"),
                "name": (fields.get("issuetype") or {}).get("name"),
                "is_subtask": (fields.get("issuetype") or {}).get("subtask"),
                "hierarchy_level": (fields.get("issuetype") or {}).get("hierarchyLevel"),
            },
            "priority": {
                "id": (fields.get("priority") or {}).get("id"),
                "name": (fields.get("priority") or {}).get("name"),
            },
        },

        # 2) Temporalité
        "temporality": {
            "created_at_utc": created_at_utc,
            "updated_at_utc": updated_at_utc,
            "resolved_at_utc": resolved_at_utc,
            "days_since_update": days_since_update,
        },

        # 3) Sémantique
        "semantics": {
            "status_raw": status_name,
            "jira_status_category_raw": jira_status_category,
            "status_canonical": canonical,  # todo / in_progress / done / unknown
        },

        # 4) Acteurs (IDs)
        "actors": {
            "assignee": {
                "id": assignee.get("accountId"),
                "name": assignee.get("displayName"),
            } if assignee else None,
            "reporter": {
                "id": reporter.get("accountId"),
                "name": reporter.get("displayName"),
                # emailAddress intentionally NOT included
            } if reporter else None,
        },

        # 5) Hiérarchie
        "hierarchy": {
            "parent": {
                "issue_id": parent.get("id"),
                "issue_key": parent.get("key"),
            } if parent else None,
            "epic": None,  # add later when you know epic custom field
        },

        # 6) Graphe de dépendances
        "dependency_graph": {
            "links": links,
        },

        # 7) Résilience
        "resilience": {
            "missing_fields": missing,
            "pii_redacted": True,
        },
    }
