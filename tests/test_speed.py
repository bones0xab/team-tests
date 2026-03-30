import os
import json
import sys
import time
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.getcwd())

load_dotenv()

from orchestration.agentV2 import llm_node, ProjectState

def test_llm_node_speed():
    state: ProjectState = {
        "issues": [
            {"key": "TEST-1", "summary": "Test issue 1", "status": "In Progress"},
            {"key": "TEST-2", "summary": "Test issue 2", "status": "To Do"}
        ],
        "metrics": {"wip": 1, "stale": 0},
        "rules": {"project_health": "YELLOW", "risks": ["Risk 1"], "actions": ["Action 1"]}
    }

    print("Running llm_node to verify speed information...")
    result = llm_node(state)
    
    print("\nResult:")
    print(json.dumps(result, indent=2))
    
    output = result.get("llm_output", {})
    assert "speed_analysis" in output
    assert "technical_speed" in output
    assert "latency_seconds" in output["technical_speed"]
    print("\nVerification successful: speed_analysis and technical_speed are present.")

if __name__ == "__main__":
    try:
        test_llm_node_speed()
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
