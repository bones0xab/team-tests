import os
import threading
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict, Dict, Any, List, Optional
from dotenv import load_dotenv
import re
from langchain_openai import ChatOpenAI          # ✅ correct import
from langgraph.graph import StateGraph, END
from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules

# ── TypedDict with required keys ─────────────────────────────────────────────
# total=True (default) = all keys required → no more TypedDict access warnings
class ProjectState(TypedDict):
    project_key: str
    issues:      List[Dict[str, Any]]
    metrics:     Dict[str, Any]
    rules:       Dict[str, Any]
    llm_output:  Dict[str, Any]


# ── Cache config ──────────────────────────────────────────────────────────────
CACHE_TTL             = int(os.environ.get("ISSUES_CACHE_TTL_SECONDS", "1800"))   # ✅ was 300 (5 min) → now 30 min default
AI_ANALYSIS_TTL_SECONDS = int(os.environ.get("AI_ANALYSIS_TTL_SECONDS", "1800"))

ISSUES_CACHE:      Dict[str, Dict[str, Any]] = {}
AI_ANALYSIS_CACHE: Dict[str, Dict]           = {}


# ── Jira fetch with cache ─────────────────────────────────────────────────────
def get_jira_data_issues(project_key: Optional[str] = None) -> List[Dict[str, Any]]:
    cache_key = project_key or "__all__"
    cached    = ISSUES_CACHE.get(cache_key)
    now       = time.time()

    if cached and now - cached["timestamp"] < CACHE_TTL:
        print(f"[CACHE] HIT for '{cache_key}' (age {int(now - cached['timestamp'])}s)")
        return cached["issues"]

    print(f"[CACHE] MISS for '{cache_key}' — fetching from Jira")
    jql    = "created >= -30d"
    if project_key:
        safe = project_key.replace('"', '\\"')
        jql += f' AND project = "{safe}"'
    fields     = ["summary", "status", "assignee", "project"]
    issues     = search_issues(jql, fields)
    normalized = [normalize_issue(i) for i in issues]

    ISSUES_CACHE[cache_key] = {"issues": normalized, "timestamp": now}
    return normalized


# ── Snapshot helpers ──────────────────────────────────────────────────────────
def _snapshot_save(metrics: Dict, rules: Dict) -> None:
    snapshot = {
        "schema_version":   "1.0",
        "snapshot_time_utc": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        "metrics": metrics,
        "rules":   rules,
    }
    Path("snapshots").mkdir(exist_ok=True)
    tmp   = "snapshots/latest.json.tmp"
    final = "snapshots/latest.json"
    with open(tmp, "w") as f:
        json.dump(snapshot, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, final)


def _load_previous_snapshot() -> Optional[Dict]:
    try:
        with open("snapshots/latest.json") as f:
            return json.load(f)
    except Exception:
        return None


# ── LangGraph nodes ───────────────────────────────────────────────────────────
def fetch_node(state: ProjectState) -> Dict:
    p_key  = state.get("project_key")
    issues = get_jira_data_issues(str(p_key) if p_key else None)
    return {"issues": issues}


def metrics_node(state: ProjectState) -> Dict:
    return {"metrics": compute_signals(state["issues"])}


def rules_node(state: ProjectState) -> Dict:
    return {"rules": evaluate_rules(state["metrics"])}


def snapshot_node(state: ProjectState) -> Dict:
    _snapshot_save(state["metrics"], state["rules"])
    return {}


# ── LLM helpers ───────────────────────────────────────────────────────────────
def _extract_json_payload(content: str) -> Any:
    if not content:
        raise ValueError("Empty response content from LLM")
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$",          "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end   = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start: end + 1])
    raise ValueError("No valid JSON object found in LLM response")


def _normalize_project_analysis(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    risks = payload.get("risks", [])
    if not isinstance(risks, list):
        risks = [str(risks)] if risks else []
    actions = payload.get("actions", [])
    if not isinstance(actions, list):
        actions = [str(actions)] if actions else []
    return {
        "risks":          [str(r) for r in risks],
        "actions":        [str(a) for a in actions],
        "speed_analysis": str(payload.get("speed_analysis", "Not analyzed")),
        "team_insights":  str(payload.get("team_insights",  "Not analyzed")),
        "sprint_health":  str(payload.get("sprint_health",  "Not analyzed")),
    }


def _summarize_issues(issues: List[Dict]) -> Dict:
    by_status:   Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    by_assignee: Dict[str, int] = {}
    unassigned_count = 0
    overdue: List[Dict] = []

    for i in issues:
        st = i.get("status", "Unknown")
        by_status[st] = by_status.get(st, 0) + 1

        pr = i.get("priority", "Unknown")
        by_priority[pr] = by_priority.get(pr, 0) + 1

        assignee = i.get("assignee")
        if assignee and assignee != "Unassigned":
            by_assignee[assignee] = by_assignee.get(assignee, 0) + 1
        else:
            unassigned_count += 1

        do = i.get("days_overdue")
        if do and isinstance(do, (int, float)) and do > 0 and len(overdue) < 30:
            overdue.append({
                "key":         i.get("key", i.get("issue_key", "")),
                "summary":     i.get("summary", ""),
                "days_overdue": do,
            })

    sorted_assignees = dict(
        sorted(by_assignee.items(), key=lambda item: item[1], reverse=True)[:10]
    )
    recent_activity = [
        {
            "key":     i.get("key", i.get("issue_key", "")),
            "summary": i.get("summary", ""),
            "status":  i.get("status", "Unknown"),
        }
        for i in issues[:20]
    ]
    return {
        "total":            len(issues),
        "by_status":        by_status,
        "by_priority":      by_priority,
        "by_assignee":      sorted_assignees,
        "overdue":          overdue,
        "unassigned_count": unassigned_count,
        "recent_activity":  recent_activity,
    }


# ── LLM node ──────────────────────────────────────────────────────────────────
def llm_node(state: ProjectState) -> Dict:
    client = ChatOpenAI(                                        # ✅ was undefined
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://102.54.244.89:8088/ollama/api/v1"),
        api_key =os.environ.get("OLLAMA_API_KEY", "ollama"),
        model   =os.environ.get("OLLAMA_MODEL", "mistral"),
        timeout =float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120")),
    )
    model_name = os.environ.get("OLLAMA_MODEL", "mistral")     # ✅ separate variable for .invoke()

    prompt = f"""
You are a senior project manager and Agile coach analyzing a Jira project.
Your mission is to map Jira metrics and business rules into CONCRETE risks and CONCRETE actions.

You receive three inputs:
- Rules triggered: {json.dumps(state["rules"])}
- Metrics: {json.dumps(state["metrics"])}
- Issues summary: {json.dumps(_summarize_issues(state["issues"]))}

Your job is:

1) COMPARE METRICS TO RULES
- Carefully compare the metrics with the rules.
- Detect every place where a metric violates a rule or is close to violating it.
- Focus on WIP, stale issues, bugs/defects, throughput, cycle time, and overdue work.

2) TURN VIOLATIONS INTO RISKS
For each important violation or near-violation:
- Create a clear risk.
- Explain WHY it is a risk using concrete numbers from the metrics and the relevant rule.
- When possible, cite example issue keys from the issues summary to illustrate the problem.

3) GENERATE ACTIONS TO REDUCE THE RISKS
For the most important risks:
- Propose specific, practical actions that the team can do within the next sprint or two.
- Each action must:
  - target a concrete risk,
  - have a suggested owner role (e.g. Tech Lead, Product Owner, Scrum Master),
  - have a realistic timeframe (e.g. this sprint, next sprint),
  - include a rationale explaining how it reduces the risk.

4) WRITE THE GLOBAL INSIGHTS
Based on the same metrics and rules:
- speed_analysis: comment on delivery speed (throughput, cycle time, aging) and what it means.
- team_insights: comment on workload balance and bottlenecks.
- sprint_health: assess sprint predictability and risk based on overdue work, velocity, and scope changes.

Respond ONLY in valid JSON with this exact structure:

{{
  "risks": [
    {{
      "title": "Short, concrete risk title",
      "severity": "HIGH|MEDIUM|LOW",
      "explanation": "Data-driven explanation citing metrics and rules (with numbers)",
      "affected_issues": ["PROJ-123", "PROJ-456"]
    }}
  ],
  "actions": [
    {{
      "priority": 1,
      "action": "Very specific actionable step",
      "owner": "Suggested role",
      "deadline": "Suggested timeframe",
      "rationale": "Why this action reduces the risk"
    }}
  ],
  "speed_analysis": "Short analysis of delivery speed",
  "team_insights":  "Short analysis of team workload and bottlenecks",
  "sprint_health":  "Short assessment of sprint predictability and risk"
}}
"""

    prev = _load_previous_snapshot()
    if prev:
        prompt += f"\nPREVIOUS SNAPSHOT (compare trends): {json.dumps(prev['metrics'])}"

    start_time = time.time()
    try:
        response   = client.invoke(prompt)                      # ✅ use .invoke() for LangChain ChatOpenAI
        latency    = time.time() - start_time
        raw_content = response.content or ""

        parsed_raw = _extract_json_payload(raw_content)
        parsed     = _normalize_project_analysis(parsed_raw)

        parsed["project_health"]   = state["rules"].get("project_health", "UNKNOWN")
        parsed["technical_speed"]  = {
            "latency_seconds":  round(latency, 3),
            "tokens_per_second": None,
        }
    except Exception as exc:
        latency = time.time() - start_time
        parsed  = {
            "project_health":  state["rules"].get("project_health", "UNKNOWN"),
            "risks":           state["rules"].get("risks",   []),
            "actions":         state["rules"].get("actions", []),
            "speed_analysis":  "Error during analysis",
            "team_insights":   "Error during analysis",
            "sprint_health":   "Error during analysis",
            "raw_llm_error":   str(exc),
            "technical_speed": {"latency_seconds": round(latency, 3)},
        }

    return {"llm_output": parsed}


# ── Build graph ───────────────────────────────────────────────────────────────
load_dotenv()

builder = StateGraph(ProjectState)
builder.add_node("fetch",           fetch_node)
builder.add_node("compute_metrics", metrics_node)
builder.add_node("evaluate_rules",  rules_node)
builder.add_node("generate_llm",    llm_node)
builder.add_node("snapshot",        snapshot_node)

builder.set_entry_point("fetch")
builder.add_edge("fetch",           "compute_metrics")
builder.add_edge("compute_metrics", "evaluate_rules")
builder.add_edge("evaluate_rules",  "generate_llm")
builder.add_edge("generate_llm",    "snapshot")
builder.add_edge("snapshot",        END)

graph = builder.compile()


# ── Public API ────────────────────────────────────────────────────────────────
def run_ai_analysis(project_key: Optional[str] = None) -> Dict:
    """Run the LangGraph pipeline once (for scripts or app.services.ai_service)."""
    return graph.invoke({"project_key": project_key or ""})


def _get_all_project_keys() -> List[str]:
    issues = get_jira_data_issues()
    keys   = list({i.get("project_key") or i.get("project", "") for i in issues})
    return [k for k in keys if k]


def _run_analysis_for_project(project_key: str) -> None:
    AI_ANALYSIS_CACHE[project_key] = {
        "status":       "running",
        "generated_at": time.time(),
        "project_key":  project_key,
        "result":       None,
    }
    try:
        result = graph.invoke({"project_key": project_key})
        AI_ANALYSIS_CACHE[project_key] = {
            "status":       "ok",
            "generated_at": time.time(),
            "project_key":  project_key,
            "result":       result.get("llm_output", {}),
        }
    except Exception as exc:
        AI_ANALYSIS_CACHE[project_key] = {
            "status":       "error",
            "generated_at": time.time(),
            "project_key":  project_key,
            "result":       None,
            "error":        str(exc),
        }


def _background_analysis_loop() -> None:
    """Runs forever: analyses all projects, then sleeps until TTL expires."""
    while True:
        try:
            project_keys = _get_all_project_keys()
            print(f"[AI Background] Starting analysis for {len(project_keys)} projects")
            for key in project_keys:
                print(f"[AI Background] Analysing project: {key}")
                _run_analysis_for_project(key)
                time.sleep(2)
            print(f"[AI Background] All done. Next run in {AI_ANALYSIS_TTL_SECONDS}s.")
        except Exception as e:
            print(f"[AI Background] Error: {e}")
        time.sleep(AI_ANALYSIS_TTL_SECONDS)


def start_background_analysis() -> None:
    """Call this once at app startup."""
    t = threading.Thread(target=_background_analysis_loop, daemon=True)
    t.start()


def get_cached_analysis(project_key: str) -> Optional[Dict]:
    """
    Returns cached AI analysis for a project.
    None if not yet computed, {"status": "running"} if in progress.
    """
    return AI_ANALYSIS_CACHE.get(project_key)