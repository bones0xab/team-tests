from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.auth.permissions import require_permission
from services.Fetch import search_issues
from datetime import datetime, timezone
import dateutil.parser
import json
import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import re

router = APIRouter(prefix="/api/team", tags=["Team Scorecard"])

@router.get("/sprints")
def get_sprints(projectKey: str, _user=Depends(require_permission("dashboard:view"))):
    jql = f'project = "{projectKey}" AND sprint is not EMPTY ORDER BY created DESC'
    fields = ["customfield_10700"] # Sprint custom field
    sprints_seen = {}
    
    count = 0
    for issue in search_issues(jql, fields, batch=50):
        # We only need to parse the first few issues to find recent sprints
        f = issue.get("fields", {})
        sprint_data_list = []
        for key, value in f.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'sprintName' in item:
                        sprint_data_list.append(item)
                    elif isinstance(item, str) and 'id=' in item and 'name=' in item:
                        # Jira string representation of Sprint
                        # com.atlassian.greenhopper.service.sprint.Sprint@1bd[id=123,rapidViewId=45,state=ACTIVE,name=Sprint 1,startDate=...]
                        match_id = re.search(r'id=(\d+)', item)
                        match_name = re.search(r'name=([^,]+)', item)
                        match_state = re.search(r'state=([^,]+)', item)
                        if match_id and match_name:
                            sprints_seen[match_id.group(1)] = {
                                "id": match_id.group(1),
                                "name": match_name.group(1),
                                "state": match_state.group(1) if match_state else "UNKNOWN"
                            }
        count += 1
        if count > 200:
            break
            
    return {"sprints": list(sprints_seen.values())}


@router.get("/scorecard")
def get_scorecard(
    projectKey: str,
    sprintId: str,
    _user=Depends(require_permission("dashboard:view"))
):
    # 1. Fetch exact issues for the selected sprint
    jql = f'project = "{projectKey}" AND sprint = {sprintId}'
    fields = ["summary", "status", "assignee", "created", "resolutiondate", "updated", "duedate", "customfield_10700", "sprint"]
    
    issues = list(search_issues(jql, fields, batch=200))
    if not issues:
        return {"members": [], "project": {"key": projectKey, "name": projectKey}, "sprint": {"id": sprintId, "name": sprintId}, "generated_at": datetime.now(timezone.utc).isoformat()}

    # Group issues by assignee
    assignee_issues = {}
    sprint_name = sprintId
    
    # helper to extract sprints from an issue
    def extract_sprint_ids(issue):
        f = issue.get("fields", {})
        ids = set()
        for key, value in f.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'id' in item:
                        ids.add(str(item['id']))
                    elif isinstance(item, str) and 'id=' in item:
                        match_id = re.search(r'id=(\d+)', item)
                        if match_id:
                            ids.add(match_id.group(1))
        return ids
        
    def extract_sprint_names(issue):
        f = issue.get("fields", {})
        names = set()
        for key, value in f.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'name' in item:
                        names.add(item['name'])
                    elif isinstance(item, dict) and 'sprintName' in item:
                        names.add(item['sprintName'])
                    elif isinstance(item, str) and 'name=' in item:
                        match_name = re.search(r'name=([^,]+)', item)
                        if match_name:
                            names.add(match_name.group(1))
        return names

    # Gather sprint history ordered by ID (assuming higher ID = newer sprint)
    all_sprints = set()
    for issue in issues:
        all_sprints.update(extract_sprint_ids(issue))
        all_sprints.update(extract_sprint_names(issue))
        
    # We will just treat sprintId / sprint names as valid strings.
    # To get last 4 sprints, let's sort all sprint strings we saw for DONE issues.
    
    for issue in issues:
        f = issue.get("fields", {})
        assignee = f.get("assignee")
        if not assignee:
            continue
            
        acc_id = assignee.get("accountId") or assignee.get("key") or assignee.get("name")
        if not acc_id:
            continue
            
        if acc_id not in assignee_issues:
            assignee_issues[acc_id] = {
                "accountId": acc_id,
                "displayName": assignee.get("displayName", acc_id),
                "avatarUrl": assignee.get("avatarUrls", {}).get("48x48", ""),
                "issues": []
            }
        assignee_issues[acc_id]["issues"].append(issue)

    # Process metrics per assignee
    results = []
    
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("groq_API"),
        temperature=0.0,
        max_tokens=400,
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    prompt = ChatPromptTemplate.from_template("""You are a team performance analyst. Based on the following Jira metrics for a developer, give a performance score from 0 to 100, a label (Excellent/Good/Needs Attention/At Risk), a 1-2 sentence summary, and the biggest flag. Be honest and data-driven. Return ONLY valid JSON with keys: performance_score, performance_label, ai_summary, ai_flag.

Metrics for {name}:
{metrics}
""")

    now = datetime.now(timezone.utc)
    
    for acc_id, data in assignee_issues.items():
        user_issues = data["issues"]
        
        tasks_completed: int = 0
        tasks_in_progress: int = 0
        tasks_todo: int = 0
        
        # velocity calculation: map sprint_id -> completed count
        sprint_completed: Dict[Any, int] = {}
        
        overdue_count: int = 0
        total_assigned: int = len(user_issues)
        
        resolution_days_sum: float = 0.0
        resolved_count: int = 0
        
        blocked_tasks: int = 0
        
        for issue in user_issues:
            f = issue.get("fields", {})
            status_name = (f.get("status") or {}).get("name", "").lower()
            
            s_ids = extract_sprint_ids(issue)
            s_names = extract_sprint_names(issue)
            
            is_in_sprint = (sprintId in s_ids) or (sprintId in s_names)
            
            is_done = status_name in ["done", "resolved", "closed"]
            is_in_prog = status_name in ["in progress", "in review"]
            is_todo = status_name in ["to do", "open", "backlog"]
            
            if is_in_sprint:
                if is_done:
                    tasks_completed += 1
                elif is_in_prog:
                    tasks_in_progress += 1
                elif is_todo:
                    tasks_todo += 1
                    
            if not is_done:
                # check overdue
                due = f.get("duedate")
                if due:
                    due_date = dateutil.parser.isoparse(due)
                    if due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=timezone.utc)
                    if due_date < now:
                        overdue_count += 1
                        
                # check blocked
                updated = f.get("updated")
                if updated:
                    updated_date = dateutil.parser.isoparse(updated)
                    if updated_date.tzinfo is None:
                        updated_date = updated_date.replace(tzinfo=timezone.utc)
                    if (now - updated_date).days >= 3:
                        blocked_tasks += 1
                        
            # Resolution time for THIS sprint's done issues
            if is_done and is_in_sprint:
                created = f.get("created")
                resolved = f.get("resolutiondate") or f.get("updated")
                if created and resolved:
                    c_date = dateutil.parser.isoparse(created)
                    r_date = dateutil.parser.isoparse(resolved)
                    resolution_days_sum += (r_date - c_date).total_seconds() / 86400
                    resolved_count += 1
                    
            # For velocity trend, we tally done issues by sprint
            if is_done:
                # Add to all sprints it participated in? Or just latest?
                for sid in s_ids:
                    sprint_completed[sid] = sprint_completed.get(sid, 0) + 1
                for sname in s_names:
                    sprint_completed[sname] = sprint_completed.get(sname, 0) + 1

        avg_resolution_time = round(resolution_days_sum / resolved_count, 1) if resolved_count > 0 else None
        overdue_rate = round((overdue_count / total_assigned) * 100, 1) if total_assigned > 0 else 0.0
        
        # velocity trend: sort sprint_completed keys and take last 4?
        # Sprint IDs are usually numeric strings
        numeric_sprints = {int(k): v for k, v in sprint_completed.items() if str(k).isdigit()}
        sorted_sprints = sorted(numeric_sprints.items(), key=lambda x: x[0])
        last_4_sprints = sorted_sprints[-4:]
        velocity_trend = [count for _, count in last_4_sprints]
        while len(velocity_trend) < 4:
            velocity_trend.insert(0, 0)  # pad with 0
            
        metrics_dict = {
            "tasks_completed": tasks_completed,
            "tasks_in_progress": tasks_in_progress,
            "tasks_todo": tasks_todo,
            "overdue_rate": overdue_rate,
            "avg_resolution_time": avg_resolution_time,
            "blocked_tasks": blocked_tasks,
            "velocity_trend": velocity_trend
        }
        
        # AI call
        try:
            chain = prompt | llm
            res = chain.invoke({"name": data["displayName"], "metrics": json.dumps(metrics_dict)})
            ai_data = json.loads(res.content)
            # validate schema
            val_score = ai_data.get("performance_score", 50)
            val_label = ai_data.get("performance_label", "Good")
            if val_label not in ["Excellent", "Good", "Needs Attention", "At Risk"]:
                val_label = "Good"
            val_summary = ai_data.get("ai_summary", "")
            val_flag = ai_data.get("ai_flag")
            ai_dict = {
                "performance_score": val_score,
                "performance_label": val_label,
                "ai_summary": val_summary,
                "ai_flag": val_flag
            }
        except Exception as e:
            ai_dict = {
                "performance_score": 0,
                "performance_label": "Needs Attention",
                "ai_summary": "AI generation failed.",
                "ai_flag": None
            }

        from services.WebSocketManager import manager
        manager.broadcast_sync({
            "type": "SCORECARD_TOKEN",
            "user": data["displayName"],
            "data": ai_dict
        }, "global")

        if (tasks_completed + tasks_in_progress + tasks_todo) > 0:
            results.append({
                "accountId": data["accountId"],
                "displayName": data["displayName"],
                "avatarUrl": data["avatarUrl"],
                "metrics": metrics_dict,
                "ai": ai_dict
            })
            
    # sort by score desc initially
    results.sort(key=lambda x: x["ai"]["performance_score"], reverse=True)
    
    return {
        "project": {"key": projectKey, "name": projectKey},
        "sprint": {"id": sprintId, "name": sprintId, "startDate": "", "endDate": ""},
        "members": results,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
