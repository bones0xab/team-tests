# orchestration/agentV1.py
import json
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain.agents import create_agent 

from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules


def get_jira_data():
    """Fetch and normalize Jira issues from last 30 days"""
    jql = "created >= -30"
    fields = ["summary", "status", "assignee", "updated"]
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
    print("[DEBUG] Metrics:", json.dumps(metrics, indent=2, default=str))
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
    print("[DEBUG] Rules result:", json.dumps(result, indent=2, default=str))
    return result


# Configuration LLM
llm = ChatOllama(
    model="qwen2.5:7b-instruct",
    temperature=0.2
)

# Tools available to the agent
tools = [get_project_metrics, get_rules]

# System prompt - instructs the agent how to use the tools
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
{
  "project_health": "HEALTHY|WATCH|AT_RISK",
  "summary": ["brief summary point 1", "brief summary point 2"],
  "risks": ["risk 1", "risk 2"],
  "actions": ["action 1", "action 2"],
  "notify": true/false,
  "proof": [{"rule": "...", "severity": "...", "signal": "...", "value": 0, "threshold": 0, "why": "..."}]
}

IMPORTANT RULES:
- You MUST call BOTH tools (get_project_metrics AND get_rules) before providing final answer
- Do NOT return the tool calls themselves as your final answer
- Your final answer must be ONLY the JSON object (no extra text, no markdown)
- Do NOT make up or modify values from get_rules output - copy them exactly
"""

# Create the agent with LangChain (nouvelle API)
agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)


def run_agent(prompt: str = "Analyze the Jira project health and provide a JSON report") -> str:
    """
    Execute the agent with proper multi-step tool execution.
    
    Args:
        prompt: The user's request (default asks for health report)
        
    Returns:
        Final JSON response from the agent as a string
    """
    print(f"\n{'='*60}")
    print("🤖 AGENT EXECUTION STARTED")
    print(f"{'='*60}\n")
    
    # Invoke the agent
    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    
    # Extract all messages
    messages = result["messages"]
    
    # Debug: show execution trace
    print("\n[DEBUG] Execution trace:")
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        if hasattr(msg, 'content') and msg.content:
            content_preview = str(msg.content)[:100]
            print(f"  {i}. {msg_type}: {content_preview}...")
        elif hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"  {i}. {msg_type}: Calling {len(msg.tool_calls)} tool(s)")
    
    # Find the final AI response (skip tool messages)
    final_response: str = ""
    
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            # Check if it's a tool call or actual content
            if msg.content and not msg.tool_calls:
                final_response = str(msg.content)
                break
            elif msg.content and msg.tool_calls:
                # Has both content and tool calls - keep looking
                continue
    
    # Fallback: get last message with content
    if not final_response:
        for msg in reversed(messages):
            if hasattr(msg, 'content') and msg.content:
                final_response = str(msg.content)
                break
    
    # Last resort
    if not final_response:
        final_response = '{"error": "No response generated"}'
    
    print(f"\n{'='*60}")
    print("✅ AGENT EXECUTION COMPLETED")
    print(f"{'='*60}\n")
    print("Final response:")
    print(final_response)
    
    return final_response


# Run when executed directly
if __name__ == "__main__":
    result = run_agent()
    
    print("\n" + "="*60)
    print("📊 FINAL OUTPUT (parsed)")
    print("="*60)
    
    try:
        # Try to parse and pretty-print the JSON
        parsed = json.loads(result)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print("⚠️ Output is not valid JSON:")
        print(result)