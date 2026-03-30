import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules

_DASHBOARD_CACHE = {}
_PORTFOLIO_CACHE = {}
_DASHBOARD_CACHE_TTL = 600
_PORTFOLIO_CACHE_TTL = 300
_NORM_WORKERS = 8


class _RecordsWrapper(list):
    def to_dict(self, orient="records"):
        if orient != "records":
            raise ValueError("Only 'records' orient is supported")
        return list(self)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _build_daily_update_activity(rows):
    counts = Counter()
    for row in rows:
        dt = _parse_iso(row.get("updated_at"))
        if not dt:
            continue
        counts[dt.date().isoformat()] += 1
    return [{"date": date, "count": counts[date]} for date in sorted(counts)]


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _build_team_activity_heatmap(rows):
    buckets = defaultdict(lambda: defaultdict(int))
    for row in rows:
        assignee = row.get("assignee") or "Unassigned"
        dt = _parse_iso(row.get("updated_at"))
        if not dt:
            continue
        buckets[assignee][(WEEKDAYS[dt.weekday()], dt.hour)] += 1

    heatmap = []
    for assignee, counts in buckets.items():
        cells = []
        for weekday in WEEKDAYS:
            for hour in range(24):
                cells.append({
                    "weekday": weekday,
                    "hour": hour,
                    "count": counts.get((weekday, hour), 0),
                })
        heatmap.append({"assignee": assignee, "cells": cells})
    return heatmap


def fetch_dashboard_data(project_key, days_back):
    cache_key = (project_key, days_back)
    now = time.time()
    cached = _DASHBOARD_CACHE.get(cache_key)

    if cached and cached["expires_at"] > now:
        return cached["payload"]

    jql = f'''
    project = "{project_key}"
    AND updated >= -{days_back}d
    ORDER BY updated DESC
    '''
    fields = ["summary", "status", "assignee", "updated"]

    # ── Parallel normalization (team's optimization) ───────────────────────
    raw_issues = list(search_issues(jql, fields))
    if not raw_issues:
        return None

    with ThreadPoolExecutor(max_workers=_NORM_WORKERS) as pool:
        data = list(pool.map(normalize_issue, raw_issues))

    table_rows = _RecordsWrapper()
    for normalized in data:
        table_rows.append({
            "key": normalized["identity"].get("issue_key"),
            "summary": normalized["identity"].get("summary"),
            "status_name": normalized["semantics"].get("status_canonical"),
            "assignee": (
                normalized["actors"]["assignee"]["name"]
                if normalized["actors"].get("assignee")
                else None
            ),
            "updated_at": normalized["temporality"].get("updated_at_utc"),
            "days_since_update": normalized["temporality"].get("days_since_update"),
        })

    metrics = compute_signals(data)
    rules = evaluate_rules(metrics)

    # ── Prometheus metrics update (your addition) ──────────────────────────
    try:
        from app.metrics.prometheus_metrics import update_project_metrics
        if project_key:
            update_project_metrics(project_key, metrics, rules)
    except Exception:
        pass

    daily_update_activity = _build_daily_update_activity(table_rows)
    team_activity_heatmap = _build_team_activity_heatmap(table_rows)

    payload = {
        "issues": data,
        "data": data,
        "metrics": metrics,
        "rules": rules,
        "df": table_rows,
        "daily_update_activity": daily_update_activity,
        "team_activity_heatmap": team_activity_heatmap,
    }

    _DASHBOARD_CACHE[cache_key] = {
        "expires_at": now + _DASHBOARD_CACHE_TTL,
        "payload": payload,
    }

    return payload


def fetch_portfolio_summary(days_back: int) -> list:
    now = time.time()
    if days_back in _PORTFOLIO_CACHE:
        entry = _PORTFOLIO_CACHE[days_back]
        if entry["expires_at"] > now:
            return entry["payload"]

    from services.Fetch import get_projects, search_issues
    from services.Normalisation import normalize_projects

    projects_list = normalize_projects(get_projects())
    if not projects_list:
        return []

    project_keys = [p["identity"]["project_key"] for p in projects_list]
    keys_string = ",".join(f'"{k}"' for k in project_keys)
    jql = f"project IN ({keys_string}) AND updated >= -{days_back}d ORDER BY project ASC, updated DESC"
    fields = ["summary", "status", "assignee", "updated"]

    # ── Parallel normalization (team's optimization) ───────────────────────
    raw_issues = list(search_issues(jql, fields))
    with ThreadPoolExecutor(max_workers=_NORM_WORKERS) as pool:
        normalized_issues = list(pool.map(normalize_issue, raw_issues))

    project_data_map = defaultdict(list)
    for raw, normalized in zip(raw_issues, normalized_issues):
        pkey = raw["key"].split("-")[0]
        project_data_map[pkey].append(normalized)

    results = []
    for p in projects_list:
        pkey = p["identity"]["project_key"]
        pname = p["identity"]["project_name"]
        data = project_data_map.get(pkey, [])

        if not data:
            results.append({
                "project_key": pkey, "project_name": pname,
                "health": "UNKNOWN", "total_issues": 0, "wip_count": 0, "stale_count": 0
            })
            continue

        metrics = compute_signals(data)
        rules = evaluate_rules(metrics)

        # ── Prometheus metrics update (your addition) ──────────────────────
        try:
            from app.metrics.prometheus_metrics import update_project_metrics
            update_project_metrics(pkey, metrics, rules)
        except Exception:
            pass

        results.append({
            "project_key": pkey,
            "project_name": pname,
            "health": rules["project_health"],
            "total_issues": len(data),
            "wip_count": metrics["wip"],
            "stale_count": metrics.get("stale_in_progress_count", 0)
        })

    _PORTFOLIO_CACHE[days_back] = {
        "expires_at": now + _PORTFOLIO_CACHE_TTL,
        "payload": results
    }
    return results