# services/Fetch.py
import time
import concurrent.futures
from typing import Iterator, List, Dict, Optional

from services.Auth import build_jira_session, load_jira_config, JiraConfig
from requests import Session

_SESSION: Optional[Session] = None
_CONFIG: Optional[JiraConfig] = None

def _get_session() -> tuple[JiraConfig, Session]:
    global _SESSION, _CONFIG
    if _SESSION is None or _CONFIG is None:
        _CONFIG = load_jira_config()
        _SESSION = build_jira_session(_CONFIG)
    return _CONFIG, _SESSION


def _fetch_page(session: Session, base_url: str, jql: str, fields: List[str],
                start: int, batch: int) -> List[Dict]:
    for attempt in range(5):
        response = session.get(
            f"{base_url}/rest/api/2/search",
            params={
                "jql": jql,
                "fields": ",".join(fields),
                "startAt": start,
                "maxResults": batch,
            },
        )
        if response.status_code in (429, 503):
            wait = int(response.headers.get(
                "Retry-After", 5 if response.status_code == 503 else 2
            ))
            time.sleep(wait * (2 ** attempt))
            continue
        response.raise_for_status()
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) < 15:
            print(f"🚨 Quota low ({remaining} left). Pausing 10s...")
            time.sleep(10)
        return response.json().get("issues", [])
    return []


def search_issues(jql: str, fields: List[str], batch: int = 200) -> Iterator[Dict]:
    config, session = _get_session()
    base_url = config.base_url

    response = None  # ← ensure always bound
    for attempt in range(5):
        response = session.get(
            f"{base_url}/rest/api/2/search",
            params={"jql": jql, "fields": ",".join(fields), "startAt": 0, "maxResults": batch},
        )
        if response.status_code in (429, 503):
            wait = int(response.headers.get(
                "Retry-After", 5 if response.status_code == 503 else 2
            ))
            time.sleep(wait * (2 ** attempt))
            continue
        response.raise_for_status()
        break

    if response is None:
        return

    data = response.json()
    first_page = data.get("issues", [])
    total = data.get("total", 0)

    for issue in first_page:
        yield issue

    if not first_page or len(first_page) >= total:
        return

    starts = list(range(batch, total, batch))
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(starts))) as pool:
        future_map = {
            pool.submit(_fetch_page, session, base_url, jql, fields, s, batch): s
            for s in starts
        }
        for future in sorted(future_map, key=lambda f: future_map[f]):
            for issue in future.result():
                yield issue


# ── Module-level caches ──────────────────────────────────────────────────────
_projects_cache: Dict = {"data": None, "expires_at": 0}
_components_cache: Dict = {}


def get_projects(ttl: int = 300) -> List[Dict]:
    global _projects_cache
    now = time.time()
    if _projects_cache["data"] is not None and _projects_cache["expires_at"] > now:
        return _projects_cache["data"]

    config, session = _get_session()
    response = session.get(
        f"{config.base_url}/rest/api/2/project",
        params={"expand": "description,lead"}
    )
    response.raise_for_status()
    data = response.json()

    _projects_cache = {"data": data, "expires_at": now + ttl}
    return data


def get_project_components(project_key: str, ttl: int = 300) -> List[Dict]:
    global _components_cache
    now = time.time()
    if project_key in _components_cache and _components_cache[project_key]["expires_at"] > now:
        return _components_cache[project_key]["data"]

    config, session = _get_session()
    response = session.get(f"{config.base_url}/rest/api/2/project/{project_key}/components")
    if response.status_code != 200:
        return []
    data = response.json()

    _components_cache[project_key] = {"data": data, "expires_at": now + ttl}
    return data


def get_clean_issues():
    config, session = _get_session()
    import json
    r = session.get(
        f"{config.base_url}/rest/api/2/search",
        params={"jql": "project=FELTRI", "maxResults": 50, "fields": "summary,assignee"},
    )
    r.raise_for_status()
    issues = r.json()["issues"]
    clean_output = [
        {
            "key": issue["key"],
            "summary": issue["fields"]["summary"],
            "assignee": (
                issue["fields"]["assignee"]["displayName"]
                if issue["fields"]["assignee"]
                else None
            ),
        }
        for issue in issues
    ]
    return json.dumps(clean_output, indent=4, ensure_ascii=False)