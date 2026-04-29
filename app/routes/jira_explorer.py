# app/routes/jira_explorer.py
"""
Jira Explorer endpoints:
  GET /api/jira/issues/search  — filtered JQL search with pagination
  GET /api/jira/meta           — metadata for populating filter dropdowns
"""
import re
from typing import Optional

from datetime import datetime, timezone
import dateutil.parser
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.permissions import require_permission
from app.services.auth_helpers import load_jira_config, build_jira_session

router = APIRouter(prefix="/api/jira", tags=["Jira Explorer"])

# ── JQL sanitisation ──────────────────────────────────────────────────────
_SAFE_IDENTIFIER = re.compile(r'^[\w\s\-\.]+$', re.UNICODE)
_SAFE_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _safe_str(value: str, max_len: int = 100) -> str:
    """Strip characters that could break JQL string literals."""
    return value[:max_len].replace('"', '').replace("'", '').replace(';', '').replace('\\', '')


def _quoted_list(values: list[str]) -> str:
    return ', '.join(f'"{_safe_str(v)}"' for v in values if v.strip())


def _build_jql(
    project_keys: list[str],
    issue_types: list[str],
    statuses: list[str],
    priorities: list[str],
    assignees: list[str],
    reporters: list[str],
    sprints: list[str],
    created_from: Optional[str],
    created_to: Optional[str],
    leads: list[str],
    labels: list[str],
    components: list[str],
) -> str:
    clauses: list[str] = []

    if project_keys:
        safe_keys = [k.upper()[:20] for k in project_keys if re.match(r'^[A-Z0-9_]+$', k.upper()[:20])]
        if safe_keys:
            clauses.append(f'project in ({", ".join(safe_keys)})')

    if issue_types:
        clauses.append(f'issuetype in ({_quoted_list(issue_types)})')

    if statuses:
        clauses.append(f'status in ({_quoted_list(statuses)})')

    if priorities:
        clauses.append(f'priority in ({_quoted_list(priorities)})')

    if assignees:
        safe_assignees = [_safe_str(a, 60) for a in assignees if a.strip()]
        if safe_assignees:
            clauses.append(f'assignee in ({", ".join(f"{chr(34)}{a}{chr(34)}" for a in safe_assignees)})')

    if reporters:
        safe_reporters = [_safe_str(r, 60) for r in reporters if r.strip()]
        if safe_reporters:
            clauses.append(f'reporter in ({", ".join(f"{chr(34)}{r}{chr(34)}" for r in safe_reporters)})')

    if sprints:
        # sprints may be IDs (numeric) or names
        sprint_parts = []
        for s in sprints:
            s = s.strip()
            if s.isdigit():
                sprint_parts.append(s)
            else:
                sprint_parts.append(f'"{_safe_str(s)}"')
        if sprint_parts:
            clauses.append(f'sprint in ({", ".join(sprint_parts)})')

    if created_from and _SAFE_DATE.match(created_from):
        clauses.append(f'created >= "{created_from}"')
    if created_to and _SAFE_DATE.match(created_to):
        clauses.append(f'created <= "{created_to}"')

    # Filtering by Component Leads (translated to component names in route)
    pass

    label_clauses: list[str] = []
    safe_labels = [_safe_str(l, 60) for l in labels if l.strip()]
    safe_components = [_safe_str(c, 60) for c in components if c.strip()]

    if safe_labels:
        label_clauses.append(f'labels in ({", ".join(f"{chr(34)}{l}{chr(34)}" for l in safe_labels)})')
    if safe_components:
        label_clauses.append(f'component in ({", ".join(f"{chr(34)}{c}{chr(34)}" for c in safe_components)})')
    if label_clauses:
        clauses.append(f'({" OR ".join(label_clauses)})')

    return ' AND '.join(clauses) if clauses else 'ORDER BY created DESC'


def _normalize_issue(raw: dict, base_url: str) -> dict:
    f = raw.get('fields', {})
    assignee_obj = f.get('assignee') or {}
    reporter_obj = f.get('reporter') or {}
    project_obj = f.get('project') or {}
    issuetype_obj = f.get('issuetype') or {}
    status_obj = f.get('status') or {}
    priority_obj = f.get('priority') or {}

    # Sprint (Jira stores in a custom field; we look for sprint-related data)
    sprint_name: Optional[str] = None
    for key, value in f.items():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get('sprintName'):
                    sprint_name = item['sprintName']
                    break
        if sprint_name:
            break

    # Get Component Lead (lead of the first component)
    from app.services.jira_fetch import get_project_components
    comp_lead = "—"
    try:
        pkey = project_obj.get('key')
        issue_comps = f.get('components', [])
        if issue_comps and pkey:
            first_comp_name = issue_comps[0].get('name')
            all_project_comps = get_project_components(pkey)
            for c in all_project_comps:
                if c.get('name') == first_comp_name:
                    lead_obj = c.get('lead') or {}
                    comp_lead = lead_obj.get('displayName') or lead_obj.get('name') or "—"
                    break
    except Exception:
        pass

    return {
        'key': raw.get('key', ''),
        'summary': f.get('summary', ''),
        'project': {
            'key': project_obj.get('key', ''),
            'name': project_obj.get('name', ''),
        },
        'issueType': issuetype_obj.get('name', ''),
        'status': status_obj.get('name', ''),
        'priority': priority_obj.get('name', ''),
        'assignee': assignee_obj.get('displayName') or None,
        'reporter': reporter_obj.get('displayName', ''),
        'sprint': sprint_name,
        'labels': f.get('labels') or [],
        'components': [c.get('name', '') for c in (f.get('components') or [])],
        'created': (f.get('created') or '')[:10],
        'lead': comp_lead,
        'url': f'{base_url}/browse/{raw.get("key", "")}',
    }


def _jira_search(jql: str, fields: list[str], start_at: int, max_results: int) -> tuple[dict, str]:
    config = load_jira_config()
    session = build_jira_session(config)
    params = {
        'jql': jql,
        'fields': ','.join(fields),
        'startAt': start_at,
        'maxResults': max_results,
    }
    resp = session.get(f'{config.base_url}/rest/api/2/search', params=params)
    resp.raise_for_status()
    return resp.json(), config.base_url


# ── /api/jira/issues/search ───────────────────────────────────────────────
@router.get('/issues/search')
def search_issues(
    projectKeys: list[str] = Query(default=[]),
    issueTypes: list[str] = Query(default=[]),
    statuses: list[str] = Query(default=[]),
    priorities: list[str] = Query(default=[]),
    assignees: list[str] = Query(default=[]),
    reporters: list[str] = Query(default=[]),
    sprints: list[str] = Query(default=[]),
    createdFrom: Optional[str] = Query(default=None),
    createdTo: Optional[str] = Query(default=None),
    leads: list[str] = Query(default=[]),
    labels: list[str] = Query(default=[]),
    components: list[str] = Query(default=[]),
    page: int = Query(default=0, ge=0),
    pageSize: int = Query(default=25, ge=1, le=100),
    _user=Depends(require_permission('dashboard:view')),
):
    translated_components = list(components)
    if leads:
        from app.services.jira_fetch import get_projects, get_project_components
        try:
            target_leads = [l.lower() for l in leads]
            # If no project keys provided, we have to check all projects (expensive but cached)
            p_to_check = projectKeys if projectKeys else [p['key'] for p in get_projects()]
            for pk in p_to_check:
                comps = get_project_components(pk)
                for c in comps:
                    l_obj = c.get('lead') or {}
                    l_name = (l_obj.get('displayName') or l_obj.get('name') or "").lower()
                    if any(tl in l_name for tl in target_leads):
                        if c.get('name') not in translated_components:
                            translated_components.append(c.get('name'))
        except Exception:
            pass

    jql = _build_jql(
        project_keys=projectKeys,
        issue_types=issueTypes,
        statuses=statuses,
        priorities=priorities,
        assignees=assignees,
        reporters=reporters,
        sprints=sprints,
        created_from=createdFrom,
        created_to=createdTo,
        leads=[],  # already translated
        labels=labels,
        components=translated_components,
    )

    # Append ORDER BY if we have clauses already
    if 'ORDER BY' not in jql:
        jql += ' ORDER BY created DESC'

    fields = [
        'summary', 'project', 'issuetype', 'status', 'priority',
        'assignee', 'reporter', 'labels', 'components', 'created',
        'duedate', 'customfield_10700',  # sprint field common in DC
    ]

    try:
        data, base_url = _jira_search(jql, fields, page * pageSize, pageSize)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Jira search failed: {exc}',
        ) from exc

    issues = [_normalize_issue(raw, base_url) for raw in data.get('issues', [])]

    return {
        'total': data.get('total', 0),
        'page': page,
        'pageSize': pageSize,
        'issues': issues,
    }


# ── /api/jira/meta ────────────────────────────────────────────────────────
@router.get('/meta')
def get_meta(_user=Depends(require_permission('dashboard:view'))):
    """
    Returns data needed to populate filter dropdowns.
    Fetches projects, issue types, statuses, and priorities from Jira.
    """
    try:
        config = load_jira_config()
        session = build_jira_session(config)
        base = config.base_url

        # Projects
        proj_resp = session.get(f'{base}/rest/api/2/project')
        proj_resp.raise_for_status()
        projects = [
            {'key': p['key'], 'name': p.get('name', p['key'])}
            for p in proj_resp.json()
        ]

        # Issue types, statuses, priorities — from createmeta or field endpoints
        fields_resp = session.get(f'{base}/rest/api/2/issuetype')
        fields_resp.raise_for_status()
        issue_types = sorted({t['name'] for t in fields_resp.json()})

        status_resp = session.get(f'{base}/rest/api/2/status')
        status_resp.raise_for_status()
        statuses = sorted({s['name'] for s in status_resp.json()})

        priority_resp = session.get(f'{base}/rest/api/2/priority')
        priority_resp.raise_for_status()
        priorities = [p['name'] for p in priority_resp.json()]

        return {
            'projects': projects,
            'issueTypes': issue_types,
            'statuses': statuses,
            'priorities': priorities,
            # users/sprints/labels require project-specific calls; populated lazily
            'users': [],
            'sprints': [],
            'labels': [],
            'components': [],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Failed to fetch Jira metadata: {exc}',
        ) from exc
