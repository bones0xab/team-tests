import json
import os
from typing import TypedDict, Dict, List, Any
from groq import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from app.orchestration.agentV2 import get_jira_data_issues, _snapshot_save
from app.orchestration.metrics import compute_signals
from app.orchestration.rules import evaluate_rules
from dotenv import load_dotenv

load_dotenv()


class ProjectState(TypedDict, total=False):
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    rules: Dict[str, Any]
    llm_insights: Dict[str, Any]


# ----------------------------
# Pure Processing Nodes
# ----------------------------

def compute_metrics_node(state: ProjectState):
    metrics = compute_signals(state["issues"])
    return {"metrics": metrics}


def evaluate_rules_node(state: ProjectState):
    rules = evaluate_rules(state["metrics"])
    return {"rules": rules}


class LLMInsight(BaseModel):
    project_health: str
    risks: List[str]
    actions: List[str]


def llm_insight_node(state: ProjectState):
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("groq_API"),
        temperature=0
    )

    structured_llm = llm.with_structured_output(LLMInsight)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a senior project analyst."),
        ("human",
         "Here are the project metrics:\n{metrics}\n\n"
         "Here are the evaluated rules:\n{rules}\n\n"
         "Provide structured project insights.")
    ])

    chain = prompt | structured_llm

    result = chain.invoke({
        "metrics": state["metrics"],
        "rules": state["rules"]
    })

    insight_dict = result.model_dump()
    from app.services.ws_manager import manager
    manager.broadcast_sync({"type": "AI_UPDATE", "data": insight_dict}, "global")

    return {"llm_insights": insight_dict}


def persist_node(state: ProjectState):
    _snapshot_save(state["metrics"], state["rules"])
    return {}


# ----------------------------
# Build Graph (NO FETCH NODE)
# ----------------------------

builder = StateGraph(ProjectState)

builder.add_node("compute_metrics", compute_metrics_node)
builder.add_node("evaluate_rules", evaluate_rules_node)
builder.add_node("generate_llm_insight", llm_insight_node)
builder.add_node("persist_snapshot", persist_node)

builder.set_entry_point("compute_metrics")

builder.add_edge("compute_metrics", "evaluate_rules")
builder.add_edge("evaluate_rules", "generate_llm_insight")
builder.add_edge("generate_llm_insight", "persist_snapshot")
builder.add_edge("persist_snapshot", END)

graph = builder.compile()


# ----------------------------
# Fetch Outside the Graph
# ----------------------------

if __name__ == "__main__":
    issues = get_jira_data_issues()
    result = graph.invoke({"issues": issues})
    print(result["llm_insights"])
