import json
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage  # FIX 1: removed duplicate + unused imports
from langchain_ollama import ChatOllama            # FIX 1: kept only what's used
from langchain_core.tools import tool              # FIX 1: kept only the correct tool import
from langchain.agents import create_tool_calling_agent  # FIX 2: create_agent doesn't exist
from langchain.agents import AgentExecutor         # FIX 3: needed to actually run the agent
from langchain_core.prompts import ChatPromptTemplate   # FIX 4: needed for create_tool_calling_agent

from dotenv import load_dotenv

from app.services.jira_fetch import search_issues
from app.services.normalizer import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules

load_dotenv()


def get_jira_data() -> list:
    jql = "created >= -30d"  # FIX 5: was "-30" missing the "d" unit — invalid JQL
    fields = [
        "summary", "status", "assignee", "reporter",
        "created", "updated", "resolutiondate", "issuetype",
        "priority", "project", "labels", "components",
        "parent", "issuelinks", "comment", "attachment",
    ]
    issues = search_issues(jql, fields)
    return [normalize_issue(i) for i in issues]


@tool
def get_project_metrics() -> Dict[str, Any]:
    """Compute project metrics from Jira issues. Returns counts, aging, and risk indicators."""
    return compute_signals(get_jira_data())


@tool
def get_rules(metrics: Dict[str, Any], thresholds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Deterministically evaluate metrics into health/risks/actions/proof."""
    return evaluate_rules(metrics, thresholds=thresholds)


def run_ai_analysis(metrics: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes pre-computed metrics and rules to generate a structured JSON report.
    Returns a dict with keys: project_health, summary, risks, actions, notify, proof.
    """
    tools = [get_project_metrics, get_rules]  # FIX 6: removed the second `tools = [metrics, rules]`
                                               # which overwrote the real tools with raw dicts

    llm = ChatOllama(
        model="qwen2.5:7b-instruct",
        temperature=0.2,
        format="json",
    )

    SYSTEM_PROMPT = """# ROLE
You are a Senior Project Health Auditor. Your goal is to map raw Jira metrics to business risks using a deterministic rule engine.

# PROTOCOL (Strict)
1. FETCH: Call `get_project_metrics` to get the raw state.
2. EVALUATE: Pass ALL metrics to `get_rules`. Do NOT interpret metrics yourself.
3. FORMAT: Map the `get_rules` output directly into the JSON schema below.

# CONSTRAINTS
- NO hallucinations: If metrics are 0, report 0.
- NO conversational filler: Output starts with '{' and ends with '}'.
- NOTIFICATION: `notify` is TRUE only if `project_health` is "AT_RISK".

# OUTPUT SCHEMA
{{
  "project_health": "HEALTHY | WATCH | AT_RISK",
  "summary": ["max 2 bullets"],
  "risks": ["max 3 bullets"],
  "actions": ["max 3 bullets"],
  "notify": false,
  "proof": []
}}"""

    # FIX 7: create_tool_calling_agent requires a ChatPromptTemplate, not a plain string
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    # FIX 2: create_tool_calling_agent is the correct LangChain function
    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)

    # FIX 3: AgentExecutor is required to actually run the agent with tool loop
    executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    try:
        response = executor.invoke({
            "input": "Please fetch the project metrics, evaluate the rules, and generate the health report JSON."
        })

        # FIX 8: AgentExecutor returns {"output": "..."}, not {"messages": [...]}
        raw = response.get("output", "")

        if isinstance(raw, dict):
            return raw

        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)

    except Exception as e:
        print(f"[AgentV2] AI Analysis failed: {e}")
        return {
            "project_health": "UNKNOWN",
            "summary":        ["AI analysis unavailable"],
            "risks":          [],
            "actions":        ["Check logs for details."],
            "notify":         False,
            "proof":          [],
            "error":          str(e),
        }