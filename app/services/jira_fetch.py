# services/Fetch.py
import requests
import time
import concurrent.futures
from typing import Iterator, List, Dict, Optional
import logging
import asyncio
import json


import httpx
import redis.asyncio as redis
import redis as sync_redis_lib
import hashlib
import os
from requests import Session as RequestsSession
from app.services.auth_helpers import JiraConfig, build_jira_session, load_jira_config, build_async_jira_client

logger = logging.getLogger(__name__)

# ── Singleton session & config (Legacy Sync) ──────────────────────────────
_SESSION: Optional[RequestsSession] = None
_CONFIG:  Optional[JiraConfig]      = None
_SYNC_REDIS_CLIENT = None

def _get_sync_redis():
    global _SYNC_REDIS_CLIENT
    if _SYNC_REDIS_CLIENT is None:
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", 6379))
        _SYNC_REDIS_CLIENT = sync_redis_lib.Redis(host=host, port=port, db=0, decode_responses=True)
    return _SYNC_REDIS_CLIENT

def _get_session():
    global _SESSION, _CONFIG
    if _SESSION is None:
        _CONFIG = load_jira_config()
        _SESSION = build_jira_session(_CONFIG)
    assert _CONFIG is not None and _SESSION is not None
    return _CONFIG, _SESSION


# ── Singleton Async Config ────────────────────────────────────────────────
_ASYNC_CLIENT = None
_REDIS_CLIENT = None

async def _get_async_client() -> tuple[httpx.AsyncClient, redis.Redis]:
    global _ASYNC_CLIENT, _CONFIG, _REDIS_CLIENT
    if _CONFIG is None:
        _CONFIG = load_jira_config()
    if _ASYNC_CLIENT is None:
        _ASYNC_CLIENT = build_async_jira_client(_CONFIG)
    if _REDIS_CLIENT is None:
        import os
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", 6379))
        _REDIS_CLIENT = redis.Redis(host=host, port=port, db=0)
    return _ASYNC_CLIENT, _REDIS_CLIENT


def _fetch_page(session, base_url: str, jql: str, fields: List[str],
                start: int, batch: int) -> List[Dict]:
    """Fetch a single page and return its issues list."""
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
            wait = int(response.headers.get("Retry-After", 5 if response.status_code == 503 else 2))
            backoff = wait * (2 ** attempt)
            logger.warning(f"Hit {response.status_code}. Retrying in {backoff}s...")
            time.sleep(backoff)
            continue

        response.raise_for_status()

        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) < 15:
            logger.warning(f"Quota low ({remaining} left). Pausing 10 s...")
            time.sleep(10)

        return response.json().get("issues", [])
    return []

# ── Legacy Synchronous Methods ────────────────────────────────────────────

def get_issue_count(jql: str) -> int:
    config, session = _get_session()
    for attempt in range(5):
        try:
            response = session.get(
                f"{config.base_url}/rest/api/2/search",
                params={"jql": jql, "maxResults": 0},
                timeout=10
            )

            if response.status_code in (429, 503):
                wait = int(response.headers.get("Retry-After", 5 if response.status_code == 503 else 2))
                time.sleep(wait * (2 ** attempt))
                continue

            response.raise_for_status()
            return response.json().get("total", 0)
        except Exception as e:
            if attempt == 4:
                return 0
            time.sleep(2 ** attempt)
    return 0

def search_issues(jql: str, fields: List[str], batch: int = 200) -> Iterator[Dict]:
    config, session = _get_session()
    base_url = config.base_url
    response: Optional[requests.Response] = None 
    
    for attempt in range(5):
        response = session.get(
            f"{base_url}/rest/api/2/search",
            params={"jql": jql, "fields": ",".join(fields), "startAt": 0, "maxResults": batch},
        )
        if response.status_code in (429, 503):
            wait = int(response.headers.get("Retry-After", 5 if response.status_code == 503 else 2))
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
        future_map = {pool.submit(_fetch_page, session, base_url, jql, fields, s, batch): s for s in starts}
        for future in sorted(future_map, key=lambda f: future_map[f]):
            for issue in future.result():
                yield issue

def get_projects(ttl: int = 900) -> List[Dict]:
    redis_db = _get_sync_redis()
    cache_key = "jira_projects_sync"
    
    try:
        cached = redis_db.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Sync Redis cache fetch failed: {e}")

    config, session = _get_session()
    response = session.get(f"{config.base_url}/rest/api/2/project", params={"expand": "description,lead"})
    response.raise_for_status()
    data = response.json()

    try:
        redis_db.setex(cache_key, ttl, json.dumps(data))
    except Exception:
        pass
    
    return data

def get_project_components(project_key: str, ttl: int = 900) -> List[Dict]:
    redis_db = _get_sync_redis()
    cache_key = f"jira_comps_{project_key}"
    
    try:
        cached = redis_db.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    config, session = _get_session()
    response = session.get(f"{config.base_url}/rest/api/2/project/{project_key}/components")
    if response.status_code != 200:
        return []
    data = response.json()

    try:
        redis_db.setex(cache_key, ttl, json.dumps(data))
    except Exception:
        pass
        
    return data


# ── Modern Asynchronous API (Ready for Routers!) ──────────────────────────

async def get_projects_async(ttl: int = 900) -> List[Dict]:
    client, redis_db = await _get_async_client()
    cache_key = "jira_projects"
    
    # 1. Try Redis Cache
    try:
        cached = await redis_db.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache fetch failed: {e}")

    # 2. Re-fetch via HTTPX
    response = await client.get("/rest/api/2/project", params={"expand": "description,lead"})
    response.raise_for_status()
    data = response.json()

    # 3. Save to Redis securely
    try:
        await redis_db.setex(cache_key, ttl, json.dumps(data))
    except Exception:
        pass
    
    return data

async def get_project_components_async(project_key: str, ttl: int = 900) -> List[Dict]:
    client, redis_db = await _get_async_client()
    cache_key = f"jira_components_{project_key}"
    
    try:
        cached = await redis_db.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    response = await client.get(f"/rest/api/2/project/{project_key}/components")
    if response.status_code != 200:
        return []
    data = response.json()

    try:
        await redis_db.setex(cache_key, ttl, json.dumps(data))
    except Exception:
        pass
        
    return data

async def search_issues_async(jql: str, fields: List[str], batch: int = 200) -> List[Dict]:
    """Native async version of search_issues using httpx and asyncio.gather."""
    client, redis_db = await _get_async_client()
    
    # Generate unique cache key based on JQL and fields
    key_string = f"{jql}_fields:{','.join(sorted(fields))}_batch:{batch}"
    cache_key = f"jira_issues_{hashlib.md5(key_string.encode('utf-8')).hexdigest()}"

    # 0. Try Redis Cache
    try:
        cached = await redis_db.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache fetch failed for search_issues_async: {e}")
    
    # 1. Fetch first page to get total stats
    resp = await client.get(
        "/rest/api/2/search",
        params={
            "jql": jql,
            "fields": ",".join(fields),
            "startAt": 0,
            "maxResults": batch,
        }
    )
    resp.raise_for_status()
    data = resp.json()
    issues = data.get("issues", [])
    total = data.get("total", 0)

    if len(issues) < total:
        # 2. Fetch remaining pages in parallel
        async def fetch_page(start):
            r = await client.get(
                "/rest/api/2/search",
                params={
                    "jql": jql,
                    "fields": ",".join(fields),
                    "startAt": start,
                    "maxResults": batch,
                }
            )
            r.raise_for_status()
            return r.json().get("issues", [])

        starts = list(range(batch, total, batch))
        results = await asyncio.gather(*(fetch_page(s) for s in starts))
        for page in results:
            issues.extend(page)
            
    # 3. Save to Redis securely (Cache for 15 minutes)
    try:
        await redis_db.setex(cache_key, 900, json.dumps(issues))
    except Exception:
        pass
        
    return issues