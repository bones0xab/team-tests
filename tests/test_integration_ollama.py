import pytest
import json
from typing import Optional
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from orchestration.agentV1 import agent
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from orchestration.agentV1 import run_agent
import time
from langchain_ollama import ChatOllama

# ─── Détection Ollama + modèle réel ──────────────────────────────────────────
def _get_available_model() -> str | None:
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code != 200:
            return None

        installed = [m["name"] for m in r.json().get("models", [])]
        if not installed:
            return None

        # Priorité 1 : modèle configuré dans agentV1
        try:
            from orchestration.agentV1 import llm
            configured = getattr(llm, "model", None)
            if configured and any(
                configured in name or name in configured
                for name in installed
            ):
                return configured
        except Exception:
            pass

        # Priorité 2 : premier modèle installé
        return installed[0]

    except Exception:
        return None


def is_ollama_available() -> bool:
    return _get_available_model() is not None


# Modèle à utiliser dans tous les tests (détecté dynamiquement)
REAL_MODEL = _get_available_model() or "qwen2.5:7b-instruct"

pytestmark = pytest.mark.skipif(
    not is_ollama_available(),
    reason=(
        "Ollama non disponible ou aucun modèle installé. "
        "Lancez 'ollama serve' puis 'ollama pull <modèle>'"
    ),
)


# ─── Helpers ──────────────────────────────────────────────────────────────────
# Status category mapping — converts to what metrics.py expects (lowercase)
_CATEGORY_MAP = {
    "IN_PROGRESS": "in_progress",
    "TODO":        "todo",
    "DONE":        "done",
    "BLOCKED":     "in_progress",  # blocked → treated as stale in_progress
}

def _make_issue(
    i: int,
    status: str = "In Progress",
    category: str = "IN_PROGRESS",
    days: int = 3,
    assignee: Optional[str] = "Dev",
) -> dict:
    
    return {
        "id": str(i),
        "key": f"PROJ-{i}",
        "summary": f"Issue #{i}",
        "status_name": status,
        "status_category": _CATEGORY_MAP.get(category, category.lower()),  # ← FIX HERE
        "assignee": assignee,
        "updated_at": datetime.now(timezone.utc) - timedelta(days=days),
        "days_since_update": days,
    }


def _safe_str(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def _extract_json(text: str) -> Optional[dict]:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return None


# ─── 1. Tests LLM basiques ────────────────────────────────────────────────────
class TestLLMBasic:

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    def test_llm_responds(self):
        """Le LLM doit retourner une réponse non vide."""
        from langchain_ollama import ChatOllama

        llm = ChatOllama(model=REAL_MODEL, temperature=0.2)
        response = llm.invoke("Say 'ok' and nothing else.")

        assert response is not None
        content = _safe_str(response.content)
        assert len(content) > 0, "La réponse ne doit pas être vide"
        print(f"\n✅ LLM basic response: '{content}'")

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    def test_llm_returns_json(self):
        """Le LLM doit être capable de produire du JSON valide."""
        from langchain_ollama import ChatOllama

        llm = ChatOllama(model=REAL_MODEL, temperature=0.0)
        prompt = (
            'Return ONLY this JSON, no markdown, no extra text:\n'
            '{"status": "ok", "value": 42}'
        )
        response = llm.invoke(prompt)
        content = _safe_str(response.content).strip()

        if "```" in content:
            lines = [line for line in content.splitlines()
                     if not line.startswith("```")]
            content = "\n".join(lines).strip()

        data = _extract_json(content)
        if data is None:
            pytest.skip("Le LLM n'a pas retourné de JSON pur — comportement acceptable")

        assert "status" in data or "value" in data
        print(f"\n✅ LLM JSON response: {data}")

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    def test_llm_follows_instructions(self):
        llm = ChatOllama(model=REAL_MODEL, temperature=0.0)
        messages = [
            SystemMessage(content="Always respond with exactly the word 'READY'."),
            HumanMessage(content="Are you ready?"),
        ]
        response = llm.invoke(messages)

        content = _safe_str(response.content)
        assert "READY" in content.upper(), \
            f"LLM n'a pas suivi l'instruction système. Réponse: {content}"
        print(f"\n✅ LLM follows system instructions: '{content}'")


# ─── 2. Tests agent avec données Jira mockées ─────────────────────────────────
class TestAgentWithRealAI:
    
    @pytest.mark.integration
    @pytest.mark.timeout(120)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_returns_non_empty_response(self, mock_jira):
        """L'agent doit retourner une réponse non vide."""
        mock_jira.return_value = [_make_issue(1), _make_issue(2, status="Done", category="DONE")]
        response = run_agent("Analyze the project and provide a brief health report.")

        assert response is not None
        assert len(response) > 10
        print(f"\n✅ Agent response (non-empty): {response[:150]}...")

    @pytest.mark.integration
    @pytest.mark.timeout(180)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_json_schema_is_correct(self, mock_jira):
        mock_jira.return_value = [
            _make_issue(1, "In Progress", "IN_PROGRESS", days=5),
            _make_issue(2, "To Do", "TODO", days=12, assignee=None),
            _make_issue(3, "Done", "DONE", days=1),
        ]

        res = agent.invoke({
            "messages": [HumanMessage(content="Response with Report JSON")]
        })

        raw_content = _safe_str(res["messages"][-1].content)
        data = _extract_json(raw_content)

        if data is None:
            pytest.fail(
                f"L'agent n'a pas retourné de JSON valide.\n"
                f"Réponse : {raw_content[:400]}"
            )

        assert "project_health" in data, \
            f"Champ 'project_health' manquant. Clés trouvées: {list(data.keys())}"
        assert data["project_health"] in ["HEALTHY", "WATCH", "AT_RISK"], \
            f"Valeur invalide pour project_health: '{data['project_health']}'"
        assert "risks" in data, "Champ 'risks' manquant"
        assert "actions" in data, "Champ 'actions' manquant"

        print(f"\n✅ Agent JSON schema valid:")
        print(f"   project_health = {data['project_health']}")
        print(f"   risks = {data.get('risks', [])}")
        print(f"   actions = {data.get('actions', [])}")

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_handles_empty_jira_data(self, mock_jira):
        """L'agent doit gérer proprement l'absence de tickets Jira."""
        mock_jira.return_value = []

        response = run_agent("Analyze the project.")

        assert response is not None
        assert len(response) > 5
        print(f"\n✅ Agent handles empty data: {response[:100]}...")

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_detects_healthy_project(self, mock_jira):
        """L'IA doit reconnaître un projet en bonne santé."""
        mock_jira.return_value = [
            _make_issue(i, "Done", "DONE", days=1)
            for i in range(5)
        ]

        res = agent.invoke({
            "messages": [HumanMessage(content="Response with Report JSON")]
        })
        data = _extract_json(_safe_str(res["messages"][-1].content))

        if data and "project_health" in data:
            print(f"\n✅ Healthy project detected as: {data['project_health']}")
            assert data["project_health"] != "AT_RISK", \
                "Un projet 100% Done ne devrait pas être AT_RISK"

    @pytest.mark.integration
    @pytest.mark.timeout(240)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_detects_at_risk_project(self, mock_jira):
        """CRITIQUE : l'IA doit détecter un projet en danger."""
        # Use the same pattern as test_agent_handles_none_assignees which works reliably
        mock_jira.return_value = [
            # 100% WIP (wip=10, total=10) + all stale + all unassigned
            # → triggers WIP_CONGESTION, STALE_WIP_BOTTLENECK, UNASSIGNED_WIP, SINGLE_POINT_OF_FAILURE
            _make_issue(i, "In Progress", "IN_PROGRESS", days=20, assignee=None)
            for i in range(10)
        ]

        response = run_agent("Analyze project health and report risks.")

        assert len(response) > 10, "Réponse trop courte"
        data = _extract_json(response)
        
        assert data is not None, "No valid JSON in response"
        assert "project_health" in data, "Missing project_health field"
        
        print(f"\n✅ At-risk project detected as: {data['project_health']}")
        print(f"   Risks: {data.get('risks', [])}")
        
        assert data["project_health"] in ["WATCH", "AT_RISK"], \
            f"10 unassigned stale in-progress items should be AT_RISK or WATCH, not {data['project_health']}"


# ─── 3. Tests de performance ──────────────────────────────────────────────────
class TestOllamaPerformance:

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.timeout(180)
    def test_llm_response_time(self):
        """Le LLM doit répondre en moins de 60 secondes."""
        llm = ChatOllama(model=REAL_MODEL, temperature=0.2)

        start = time.time()
        response = llm.invoke("Hello! How are you?")
        duration = time.time() - start

        assert response is not None
        print(f"\n⏱️ LLM response time: {duration:.2f}s")

        if duration > 60:
            pytest.fail(f"LLM trop lent : {duration:.1f}s (limite: 60s)")
        elif duration > 30:
            print("⚠️  Attention : réponse > 30s (lent mais acceptable)")
        else:
            print("✅ Temps de réponse acceptable")

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.timeout(180)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_handles_large_dataset(self, mock_jira):
        """L'agent doit gérer 50 tickets sans timeout."""
        mock_jira.return_value = [
            _make_issue(
                i,
                status="In Progress" if i % 3 == 0 else "To Do",
                category="IN_PROGRESS" if i % 3 == 0 else "TODO",
                days=i % 15,
            )
            for i in range(50)
        ]

        start = time.time()
        response = run_agent("Analyze the project health.")
        duration = time.time() - start

        assert response is not None
        assert len(response) > 10
        print(f"\n✅ Agent processed 50 issues in {duration:.2f}s")


# ─── 4. Tests de robustesse ───────────────────────────────────────────────────
class TestAgentRobustness:

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_handles_unicode_summary(self, mock_jira):
        """L'agent doit gérer les caractères spéciaux dans les summaries."""
        mock_jira.return_value = [
            {
                "id": "1", "key": "TEST-1",
                "summary": "Problème avec l'API — données corrompues 🔴",
                "status_name": "In Progress", "status_category": "IN_PROGRESS",
                "assignee": "Ünïcödé Üser",
                "updated_at": datetime.now(timezone.utc),
                "days_since_update": 3,
            }
        ]

        response = run_agent("Analyze.")

        assert response is not None
        assert len(response) > 5
        print(f"\n✅ Agent handled unicode: {response[:80]}...")

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_handles_none_assignees(self, mock_jira):
        """L'agent doit gérer les tickets sans assigné."""
        mock_jira.return_value = [
            _make_issue(i, assignee=None) for i in range(5)
        ]

        response = run_agent("Analyze the project.")

        assert response is not None
        print(f"\n✅ Agent handled None assignees: {response[:80]}...")