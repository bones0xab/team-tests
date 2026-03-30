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
from langchain.tools import tool
# from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

def get_jira_data() :
    jql = "created >= -30"
    fields = [
        "summary",
        "status",
        "assignee",
        "reporter",
        "created",
        "updated",
        "resolutiondate",
        "issuetype",
        "priority",
        "project",
        "labels",
        "components",
        "parent",
        "issuelinks",
        "comment",
        "attachment",
    ]
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


def run_ai_analysis(metrics: Dict[str, Any], rules: Dict[str, Any]) :
        """
        Analyzes pre-computed metrics and rules to generate a structured JSON report.
        Returns a Python dict with keys: headline, analysis, recommended_actions, confidence.
        """
        #We can use the gemini pro , just google limit us with 2 requests in 1 min , so we use this flash we have 50 request in 1 min but not for complex thinking 
        # llm = ChatGoogleGenerativeAI(
        #     model="gemini-2.5-flash",temperature=0.2,
        # )
        tools = [get_project_metrics, get_rules]

        llm = ChatOllama(
            model="qwen2.5:7b-instruct",
            temperature=0.2,
            format="json"  # Enforce JSON mode on the model side
        )
        tools = [metrics, rules]

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
        {
          "project_health": "HEALTHY | WATCH | AT_RISK",
          "summary": ["max 2 bullets"],
          "risks": ["max 3 bullets"],
          "actions": ["max 3 bullets"],
          "notify": boolean,
          "proof": [] 
        }
        """

        agent = create_agent(model=llm, tools=tools ,system_prompt=SYSTEM_PROMPT)

        try:
            response = agent.invoke({"messages": [HumanMessage(content="Please fetch the project metrics, evaluate the rules, and generate the health report JSON.")]})
            #response GEMINI format 
            last_message = response["messages"][-1]

# If the model returned a proper string
            if isinstance(last_message.content, str):
                report_content = last_message.content
                return report_content
            else:
                # Handle cases where content is a list of blocks (common in Gemini)
                report_content = last_message.content[0].get("text", "")

            # Clean potential Markdown backticks if Gemini wraps JSON in ```json
                clean_json = report_content.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_json)

        except Exception as e:
            print(f"AI Analysis failed: {e}")
            return {
                "headline": "AI Analysis Unavailable",
                "analysis": ["Could not generate insights due to a parsing error."],
                "recommended_actions": ["Check logs for details."],
                "confidence": "low"
            }


