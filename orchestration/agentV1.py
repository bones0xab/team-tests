import json
from typing import Dict, Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM, ChatOllama
from langchain_core.messages import ToolMessage
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules
from langchain_core.tools import tool





def get_jira_data() :
    jql = "created >= -30"
    fields = ["summary", "status", "assignee", "updated"]
    issues = search_issues(jql, fields)
    return [normalize_issue(i) for i in issues]



@tool
def get_project_metrics() -> Dict[str, Any]:
    """
    Compute project metrics from Jira issues.
        Returns counts, aging, and risk indicators.
        """
    return compute_signals(get_jira_data())


@tool
def get_rules(metrics: Dict[str, Any], thresholds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Deterministically evaluate metrics into health/risks/actions/proof.
    """
    return evaluate_rules(metrics, thresholds=thresholds)

llm = ChatOllama(
    model="qwen2.5:7b-instruct",
    temperature=0.2
)
tools = [get_project_metrics, get_rules]
llm_with_tools = llm.bind_tools(tools)


SYSTEM_PROMPT = """You are a Jira project health agent.
You MUST use tools to get metrics and rules.
You MUST NOT invent metrics, tickets, dates, or thresholds.
Return ONLY valid JSON with this schema:
{
  "project_health": "HEALTHY|WATCH|AT_RISK",
  "summary": ["string"],
  "risks": ["string"],
  "actions": ["string"],
  "notify": boolean,
  "proof": [{"rule": "string", "severity": "string", "signal": "string", "value": number, "threshold": number, "why": "string"}]
}
Rules:
- You MUST call get_project_metrics, then call get_rules with the returned metrics.
- notify=true ONLY if project_health == AT_RISK.
- summary max 2 bullets, risks max 3, actions max 3.
- proof must come from get_rules output (copy it)."""

agent = create_agent(model=llm, tools=tools , system_prompt=SYSTEM_PROMPT)

res = agent.invoke({"messages" : [HumanMessage(content="Response with Report JSON")]})

print(res["messages"][-1].content)
