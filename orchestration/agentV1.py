# orchestration/agentV1.py
import json
from typing import Dict, Any, Optional

from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain.agents import AgentExecutor
from langchain.agents import create_tool_calling_agent
from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules


def get_jira_data():
    """Fetch and normalize Jira issues from last 30 days"""
    jql = "created >= -30"
    fields = ["summary", "status", "assignee", "updated", "created", "reporter"]
    issues = search_issues(jql, fields)
    normalized = [normalize_issue(i) for i in issues]
    print(f"[DEBUG] Fetched {len(normalized)} issues")
    return normalized


@tool
def get_project_metrics() -> Dict[str, Any]:
    """
    Compute project metrics from Jira issues.
    Returns counts, aging, and risk indicators.
    """
    data = get_jira_data()
    metrics = compute_signals(data)
    print(f"[DEBUG] Metrics computed: {metrics.get('total', 0)} total issues")
    return metrics


@tool
def get_rules(metrics: Dict[str, Any], thresholds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Deterministically evaluate metrics into health/risks/actions/proof.
    
    Args:
        metrics: Dictionary of project metrics from get_project_metrics
        thresholds: Optional custom thresholds for evaluation
        
    Returns:
        Dictionary containing project_health, risks, actions, and proof
    """
    result = evaluate_rules(metrics, thresholds=thresholds)
    print(f"[DEBUG] Project health: {result.get('project_health', 'UNKNOWN')}")
    return result

 
llm = ChatOllama(model="qwen2.5:7b-instruct", temperature=0.2)

tools = [get_project_metrics, get_rules]

SYSTEM_PROMPT = """...(keep your exact same text)..."""

prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
    ("human", "{input}")
])

agent = create_tool_calling_agent(llm, tools, prompt_template)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)

def run_ai_analysis():
    """
    Run AI analysis using Ollama to generate project health report.
    
    Returns:
        Dictionary with project health report in JSON format
    """
    print(f"\n{'='*60}")
    print("🤖 AGENT V1 (OLLAMA) STARTED")
    print(f"{'='*60}\n")
    
    # Configure LLM
    llm = ChatOllama(
        model="qwen2.5:7b-instruct",
        temperature=0.2
    )
    
    # Define tools
    tools = [get_project_metrics, get_rules]
    
    # System prompt
    SYSTEM_PROMPT = """You are a Jira project health analysis agent.

    Your job is to analyze a Jira project and provide a health report in JSON format.

    WORKFLOW (follow these steps IN ORDER):
    1. First, call the get_project_metrics() tool to get current project metrics
    2. Then, call the get_rules() tool with the metrics you received in step 1
    3. Finally, construct a JSON response using the output from get_rules()

    When constructing the final JSON response:
    - Copy "project_health" EXACTLY from get_rules output (must be: HEALTHY, WATCH, or AT_RISK)
    - Copy "risks" array from get_rules output
    - Copy "actions" array from get_rules output  
    - Copy "proof" array from get_rules output
    - Create "summary" as 1-2 short bullet points based on the risks/actions
    - Set "notify" to true ONLY if project_health is "AT_RISK", otherwise false

    Final JSON structure:
    {{
    "project_health": "HEALTHY|WATCH|AT_RISK",
    "summary": ["brief summary point 1", "brief summary point 2"],
    "risks": ["risk 1", "risk 2"],
    "actions": ["action 1", "action 2"],
    "notify": true/false,
    "proof": [{{"rule": "...", "severity": "...", "signal": "...", "value": 0, "threshold": 0, "why": "..."}}]
    }}

    IMPORTANT RULES:
    - You MUST call BOTH tools (get_project_metrics AND get_rules) before providing final answer
    - Do NOT return the tool calls themselves as your final answer
    - Your final answer must be ONLY the JSON object (no extra text, no markdown)
    - Do NOT make up or modify values from get_rules output - copy them exactly
    """
    
    # Create prompt template
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ("human", "{input}")
    ])
    
    # Create agent
    agent = create_tool_calling_agent(llm, tools, prompt_template)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)
    
    try:
        # Execute agent
        result = executor.invoke({
            "input": "Analyze the Jira project health and provide a JSON report"
        })
        
        # Extract output
        output = result.get("output", "")
        
        print(f"\n{'='*60}")
        print("✅ AGENT V1 COMPLETED")
        print(f"{'='*60}\n")
        
        # Clean and parse JSON
        if isinstance(output, str):
            clean_json = output.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(clean_json)
            except json.JSONDecodeError as e:
                print(f"[WARNING] JSON parse error: {e}")
                print(f"[WARNING] Raw output: {clean_json}")
                # Return a safe fallback
                return {
                    "project_health": "UNKNOWN",
                    "summary": ["Could not parse AI response"],
                    "risks": ["JSON parsing failed"],
                    "actions": ["Check agent output format"],
                    "notify": False,
                    "proof": []
                }
        
        return output
    
    except Exception as e:
        print(f"\n[ERROR] Agent execution failed: {e}")
        return {
            "project_health": "UNKNOWN",
            "summary": ["AI Analysis Unavailable"],
            "risks": ["System error occurred"],
            "actions": ["Check logs for details"],
            "notify": False,
            "proof": []
        }


# Alias pour compatibilité
run_agent = run_ai_analysis


# Run when executed directly
if __name__ == "__main__":
    result = run_ai_analysis()
    
    print("\n" + "="*60)
    print("📊 FINAL OUTPUT")
    print("="*60)
    print(json.dumps(result, indent=2))