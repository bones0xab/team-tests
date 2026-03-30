from fastapi import APIRouter, Depends, HTTPException, Query, status
import requests
import time
import logging
from app.auth.permissions import require_permission
from orchestration.agentV2 import graph, get_jira_data_issues
from services.Fetch import get_projects
from services.Normalisation import normalize_projects

router = APIRouter(prefix="/api", tags=["AI"])

AI_CACHE: dict[str, dict[str, float | dict]] = {}
CACHE_TTL = 300


@router.get("/ai/projects")
async def list_ai_projects(
    _user=Depends(require_permission("dashboard:view")),
):
    try:
        projects = get_projects()
        return [
            {"key": proj.get("key"), "name": proj.get("name")}
            for proj in projects
            if proj.get("key") and proj.get("name")
        ]
    except requests.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jira projects unavailable.",
        ) from exc

@router.get("/ai/insights")
async def generate_ai_insights(
    project_key: str | None = Query(default=None),
    _user=Depends(require_permission("dashboard:view")),
):
    try:
        cache_key = project_key or "__all__"
        entry = AI_CACHE.get(cache_key)
        if entry and time.time() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]

        from app.services.services import fetch_dashboard_data
        data = fetch_dashboard_data(project_key, days_back=30)
        logging.info("Generating AI insights for project: %s", project_key)
        if not data or not data.get("issues"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No issues found for AI analysis.",
            )

        result = graph.invoke({"project_key": project_key, "issues": data["issues"]})
        llm_output = result.get("llm_output")
        if not llm_output:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI failed to generate insights.",
            )

        response = {
            "project_health": llm_output.get("project_health", "UNKNOWN"),
            "risks": llm_output.get("risks"),
            "actions": llm_output.get("actions"),
        }

        AI_CACHE[cache_key] = {"data": response, "timestamp": time.time()}
        return response

    except requests.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jira service unavailable.",
        )

    except Exception as exc:
        logging.exception("AI insights failed for project %s", project_key)  # ← add this line
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI analysis service unavailable: {str(exc)}",  # ← change detail to show the real error
        ) from exc
