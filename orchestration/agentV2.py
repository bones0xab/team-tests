import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict, Dict, Any, List
from dotenv import load_dotenv
load_dotenv()

import re
from openai import OpenAI
from langgraph.graph import StateGraph, END
from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules


class ProjectState(TypedDict):
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    rules: Dict[str, Any]
    llm_output: Dict[str, Any]
    project_key: str


CACHE_TTL = 300
ISSUES_CACHE: Dict[str, Dict[str, Any]] = {}


def get_jira_data_issues(project_key: str | None = None):
    cache_key = project_key or "__all__"
    cached = ISSUES_CACHE.get(cache_key)
    now = time.time()
    if cached and now - cached["timestamp"] < CACHE_TTL:
        return cached["issues"]

    jql = "created >= -30d"
    if project_key:
        safe = project_key.replace('"', '\\"')
        jql += f' AND project = "{safe}"'
    fields = ["summary", "status", "assignee", "project"]
    issues = search_issues(jql, fields)
    normalized = [normalize_issue(i) for i in issues]

    ISSUES_CACHE[cache_key] = {"issues": normalized, "timestamp": now}
    return normalized


def _snapshot_save(metrics, rules):
    snapshot = {
        "schema_version": "1.0",
        "snapshot_time_utc": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "metrics": metrics,
        "rules": rules,
    }

    Path("snapshots").mkdir(exist_ok=True)
    tmp = "snapshots/latest.json.tmp"
    final = "snapshots/latest.json"

    with open(tmp, "w") as f:
        json.dump(snapshot, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, final)


from app.services.services import fetch_dashboard_data

def fetch_node(state: ProjectState):
    # Fetches real Jira data and computes ONE consistent scoring logic using the shared service.
    data = fetch_dashboard_data(state.get("project_key"), days_back=30)
    if not data:
        return {"issues": [], "metrics": {}, "rules": {}}
    return {
        "issues": data["issues"],
        "metrics": data["metrics"],
        "rules": data["rules"]
    }

def metrics_node(state: ProjectState):
    # Shared service already computed metrics.
    return {}

def rules_node(state: ProjectState):
    # Shared service already computed rules.
    return {}

    
#   base_url = "http://102.54.244.89:8088/ollama/api/v1",
#     api_key = "sk-Df7Qw4Ln2Tp9Hy5Km8Br3Zv6Uc1AsXeJ"
# )
 
# resp = client.chat.completions.create(
#     model = "mistral",
 
#     messages = [{"role": "user", "content": "Hi! Who are you, and how you can help me?"}],)
 
# print(resp.choices[0].message.content)

def _extract_json_payload(content: str) -> Any:
    if not content:
        raise ValueError("Empty response content from OLLAMA")

    # Remove markdown fences if present.
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])

    raise ValueError("No valid JSON object found in OLLAMA response")


def _normalize_project_analysis(payload: Any) -> Dict[str, Any]:
    """Ensures the output is a dictionary with risks, actions, and speed_analysis."""
    if not isinstance(payload, dict):
        payload = {}
    
    risks = payload.get("risks", [])
    if not isinstance(risks, list):
        risks = [str(risks)] if risks else []
    
    actions = payload.get("actions", [])
    if not isinstance(actions, list):
        actions = [str(actions)] if actions else []
        
    return {
        "risks": [str(r) for r in risks],
        "actions": [str(a) for a in actions],
        "speed_analysis": str(payload.get("speed_analysis", "Not analyzed")),
    }


def llm_node(state: ProjectState):
    # Direct OpenAI-compatible call to Ollama/Mistral
    client = OpenAI(
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://102.54.244.89:8088/ollama/api/v1"),
        api_key=os.environ.get("OLLAMA_API_KEY"),
        timeout=float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120")),
    )
    model = os.environ.get("OLLAMA_MODEL", "mistral")

    prompt = f"""
Analyse ces données Jira. RÉPONDS UNIQUEMENT JSON valide.

ISSUES (Sample): {json.dumps(state.get("issues", [])[:50])}
METRICS: {json.dumps(state["metrics"])}
RULES: {json.dumps(state["rules"])}

Format EXACT :
{{
  "risks": ["..."], 
  "actions": ["..."],
  "speed_analysis": "Évaluation du rythme du projet (vélocité, délais, accélération)"
}}
"""

    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        latency = time.time() - start_time
        raw_content = response.choices[0].message.content or ""
        
        # Robust parsing logic from AIService
        parsed_raw = _extract_json_payload(raw_content)
        parsed = _normalize_project_analysis(parsed_raw)
        
        # Enforce deterministic project health instead of letting LLM guess
        parsed["project_health"] = state["rules"].get("project_health", "UNKNOWN")
        
        # Add technical speed information
        parsed["technical_speed"] = {
            "latency_seconds": round(latency, 3),
            "tokens_per_second": None # No token count in basic OpenAI response
        }
    except Exception as exc:
        latency = time.time() - start_time
        # Fallback/error handling: fallback to rules-based data
        parsed = {
            "project_health": state["rules"].get("project_health", "UNKNOWN"),
            "risks": state["rules"].get("risks", []),
            "actions": state["rules"].get("actions", []),
            "speed_analysis": "Error during analysis",
            "raw_llm_error": str(exc),
            "technical_speed": {
                "latency_seconds": round(latency, 3)
            }
        }

    return {"llm_output": parsed}


def snapshot_node(state: ProjectState):
    _snapshot_save(state["metrics"], state["rules"])
    return {}


load_dotenv()

builder = StateGraph(ProjectState)

builder.add_node("fetch", fetch_node)
builder.add_node("compute_metrics", metrics_node)
builder.add_node("evaluate_rules", rules_node)
builder.add_node("generate_llm", llm_node)
builder.add_node("snapshot", snapshot_node)

builder.set_entry_point("fetch")

builder.add_edge("fetch", "compute_metrics")
builder.add_edge("compute_metrics", "evaluate_rules")
builder.add_edge("evaluate_rules", "generate_llm")
builder.add_edge("generate_llm", "snapshot")
builder.add_edge("snapshot", END)

graph = builder.compile()


def run_ai_analysis(project_key: str | None = None):
    """Run the LangGraph pipeline once (for scripts or app.services.ai_service)."""
    return graph.invoke({"project_key": project_key})
