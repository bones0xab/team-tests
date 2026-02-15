# orchestration/agentV2.py
import json
from typing import Dict, Any, Optional

from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool
from dotenv import load_dotenv

# Gemini import (uncomment when ready to test)
# from langchain_google_genai import ChatGoogleGenerativeAI

# Fallback to Ollama for testing
from langchain_ollama import ChatOllama

from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules

load_dotenv()


def get_jira_data():
    """Fetch and normalize Jira issues from last 30 days"""
    jql = "created >= -30"
    fields = [
        "summary", "status", "assignee", "reporter",
        "created", "updated", "resolutiondate",
        "issuetype", "priority", "project",
        "labels", "components", "parent",
        "issuelinks", "comment", "attachment"
    ]
    issues = search_issues(jql, fields)
    return [normalize_issue(i) for i in issues]


@tool
def get_project_metrics() -> Dict[str, Any]:
    """
    Compute project metrics from Jira issues.
    Returns counts, aging, and risk indicators.
    """
    data = get_jira_data()
    metrics = compute_signals(data)
    print(f"[DEBUG] V2 Metrics computed: {metrics.get('total', 0)} total issues")
    return metrics


@tool
def get_rules(metrics: Dict[str, Any], thresholds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Deterministically evaluate metrics into health/risks/actions/proof.
    """
    result = evaluate_rules(metrics, thresholds=thresholds)
    print(f"[DEBUG] V2 Project health: {result.get('project_health', 'UNKNOWN')}")
    return result


def run_ai_analysis_gemini():
    """
    Run AI analysis using Gemini (when ready) or Ollama (fallback).
    
    Returns:
        Dictionary with project health report in JSON format
    """
    print(f"\n{'='*60}")
    print("🤖 AGENT V2 (GEMINI/OLLAMA) STARTED")
    print(f"{'='*60}\n")
    
    # OPTION 1: Gemini (uncomment when ready to test)
    # llm = ChatGoogleGenerativeAI(
    #     model="gemini-2.5-flash",
    #     temperature=0.2
    # )
    # print("🔹 Using Gemini model")
    
    # OPTION 2: Ollama (current fallback)
    llm = ChatOllama(
        model="qwen2.5:7b-instruct",
        temperature=0.2
    )
    print("🔹 Using Ollama fallback")
    
    tools = [get_project_metrics, get_rules]
    
    SYSTEM_PROMPT = """# ROLE
    You are a Senior Project Health Auditor. Your goal is to map raw Jira metrics to business risks using a deterministic rule engine.

    # PROTOCOL (Strict)
    1. FETCH: Call `get_project_metrics` to get the raw state
    2. EVALUATE: Pass ALL metrics to `get_rules`. Do NOT interpret metrics yourself
    3. FORMAT: Map the `get_rules` output directly into the JSON schema below

    # CONSTRAINTS
    - NO hallucinations: If metrics are 0, report 0
    - NO conversational filler: Output starts with '{{' and ends with '}}'
    - NOTIFICATION: `notify` is TRUE only if `project_health` is "AT_RISK"

    # OUTPUT SCHEMA
    {{
    "project_health": "HEALTHY | WATCH | AT_RISK",
    "summary": ["max 2 bullets"],
    "risks": ["max 3 bullets"],
    "actions": ["max 3 bullets"],
    "notify": boolean,
    "proof": []
    }}
    """
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ("human", "{input}")
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt_template)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)
    
    try:
        result = executor.invoke({"input": "Generate the project health report JSON now."})
        output = result.get("output", "")
        
        print(f"\n{'='*60}")
        print("✅ AGENT V2 COMPLETED")
        print(f"{'='*60}\n")
        
        # Clean and parse
        if isinstance(output, str):
            clean = output.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError as e:
                print(f"[WARNING] JSON parse error: {e}")
                return {
                    "project_health": "UNKNOWN",
                    "summary": ["Could not parse response"],
                    "risks": [],
                    "actions": [],
                    "notify": False,
                    "proof": []
                }
        
        return output
    
    except Exception as e:
        print(f"[ERROR] AgentV2 failed: {e}")
        return {
            "project_health": "UNKNOWN",
            "summary": ["AI analysis unavailable"],
            "risks": ["System error"],
            "actions": ["Check logs"],
            "notify": False,
            "proof": []
        }


if __name__ == "__main__":
    print("🤖 Testing AgentV2 (Gemini/Ollama)...")
    result = run_ai_analysis_gemini()
    print(json.dumps(result, indent=2))