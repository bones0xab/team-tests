from fastapi import APIRouter, Depends, HTTPException, Query, status
import requests
from app.auth.permissions import require_permission
from app.services.dashboard_service import fetch_dashboard_data
from app.services.teams_notification_service import TeamsNotificationService
from app.metrics.prometheus_metrics import update_project_metrics
from app.services.jira_fetch import get_projects
from app.services.normalizer import normalize_projects
import logging
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dashboard"])

_PROJECTS_CACHE: dict = {}
_PROJECTS_CACHE_TTL = 300

def _get_cached_projects() -> list:
    now = time.time()
    if _PROJECTS_CACHE.get("data") and _PROJECTS_CACHE.get("expires_at", 0) > now:
        return _PROJECTS_CACHE["data"]
    fetch_result = get_projects()
    projects = normalize_projects(fetch_result)
    _PROJECTS_CACHE["data"] = projects
    _PROJECTS_CACHE["expires_at"] = now + _PROJECTS_CACHE_TTL
    return projects


def _jira_error(exc: requests.HTTPError, generic_detail: str) -> HTTPException:
    code = exc.response.status_code if exc.response is not None else None
    if code == 429:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jira rate limit reached. Please retry in a few moments.",
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=generic_detail,
    )


@router.get("/api/dashboard")
async def dashboard(
    project_key: str = Query(default=None),
    days_back: int = Query(default=30),
    page: int = Query(default=1),
    page_size: int = Query(default=25),
    _user=Depends(require_permission("dashboard:view")),
):
    try:
        projects = _get_cached_projects()
    except requests.HTTPError as exc:
        raise _jira_error(exc, "Failed to fetch projects from Jira.") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard data source is currently unavailable.",
        ) from exc

    if not projects:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No projects available.",
        )

    if not project_key:
        project_key = projects[0]["identity"]["project_key"]

    try:
        data = fetch_dashboard_data(project_key, days_back)
    except requests.HTTPError as exc:
        raise _jira_error(exc, "Failed to fetch dashboard issues from Jira.") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to compute dashboard data.",
        ) from exc

    if not data:
        return {
            "project_key": project_key,
            "days_back": days_back,
            "metrics": None,
            "chart_data": None,
            "assignee_chart_data": None,
            "issues_table": [],
            "projects": projects,
            "error": "No data found.",
        }

    metrics = data["metrics"]
    rules_result = data["rules"]
    project_health = rules_result["project_health"]

    try:
        update_project_metrics(project_key, metrics, rules_result)
    except Exception as exc:
        print(f"[METRICS] Failed to update Prometheus for {project_key}: {exc}")


    chart_data = {
        "labels": list(metrics["status_counts"].keys()),
        "values": list(metrics["status_counts"].values()),
    }

    assignee_chart_data = {
        "labels": list(metrics["assignee_wip"].keys()),
        "values": list(metrics["assignee_wip"].values()),
    }

    total_issues = len(data["df"])
    if page < 1:
        page = 1
    start = (page - 1) * page_size
    end = start + page_size
    paginated_issues = data["df"][start:end]

    return {
        "project_key": project_key,
        "days_back": days_back,
        "metrics": metrics,
        "chart_data": chart_data,
        "assignee_chart_data": assignee_chart_data,
        "daily_update_activity": data.get("daily_update_activity"),
        "team_activity_heatmap": data.get("team_activity_heatmap"),
        "issues_table": paginated_issues,
        "total_issues": total_issues,
        "page": page,
        "page_size": page_size,
        "projects": projects,
        "project_health": project_health,
        "rules": rules_result,
        "error": None,
    }


@router.get("/api/portfolio")
async def portfolio(
    days_back: int = Query(default=30),
    _user=Depends(require_permission("dashboard:view")),
):
    from app.services.dashboard_service import fetch_portfolio_summary
    try:
        return fetch_portfolio_summary(days_back)
    except Exception as exc:
        logger.error(f"Portfolio fetch failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to fetch portfolio data.",
        ) from exc


# Remove this entire endpoint, or replace send_project_health with:
@router.post("/api/alerts/send")
async def send_alert(
    project_key: str = Query(...),
    _user=Depends(require_permission("alerts:send")),   # tighten permission
):
    # Don't call send_project_health() — that's the spam path
    # Just return the health status for manual inspection
    data = fetch_dashboard_data(project_key, days_back=30)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for '{project_key}'.")
    return {
        "status": "read_only",
        "project_key": project_key,
        "health": data["rules"]["project_health"],
        "message": "Notifications are handled by Alertmanager pipeline only."
    }