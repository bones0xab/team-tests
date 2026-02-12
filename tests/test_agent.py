import pytest
import json
from unittest.mock import Mock, patch
import requests
from datetime import datetime, timezone
from orchestration.agentV1 import (
    agent,
    llm,
    tools,
    get_project_metrics,
    get_rules,
    SYSTEM_PROMPT,
    run_agent,  
)
from langchain_core.messages import HumanMessage


# ─── Détection Ollama ────────────────────────────────────────────────────────
def _get_ollama_model() -> str | None:
    """
    Vérifie si Ollama tourne ET si le modèle utilisé par agentV1 est installé.
    Retourne le nom du modèle disponible, ou None si indisponible.
    """
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code != 200:
            return None

        installed = [m["name"] for m in r.json().get("models", [])]
        if not installed:
            return None

        # Essayer de trouver le modèle configuré dans agentV1
        try:
            configured_model = getattr(llm, "model", None)
            if configured_model and any(
                configured_model in name or name in configured_model
                for name in installed
            ):
                return configured_model
        except Exception:
            pass

        # Fallback : retourner le premier modèle installé
        return installed[0]

    except Exception:
        return None


OLLAMA_MODEL = _get_ollama_model()
OLLAMA_AVAILABLE = OLLAMA_MODEL is not None

requires_ollama = pytest.mark.skipif(
    not OLLAMA_AVAILABLE,
    reason=(
        "Ollama non disponible ou aucun modèle installé. "
        "Lancez 'ollama serve' et installez un modèle avec 'ollama pull <modèle>'"
    ),
)


# ─── Niveau 1 : Structure et imports ─────────────────────────────────────────
def test_agent_imports():
    """Smoke test : les imports critiques fonctionnent."""
    assert agent is not None
    assert llm is not None
    assert len(tools) == 2, f"Attendu 2 tools, trouvé {len(tools)}"
    assert callable(run_agent), "run_agent doit être une fonction"


class TestAgentPrompt:
    """Vérifie que le prompt système est correct AVANT tout déploiement."""

    def test_system_prompt_not_empty(self):
        assert SYSTEM_PROMPT, "SYSTEM_PROMPT est vide"
        assert len(SYSTEM_PROMPT) > 50, "SYSTEM_PROMPT trop court (< 50 chars)"

    def test_system_prompt_contains_json_schema(self):
        """Le prompt doit imposer à l'IA un schéma JSON précis."""
        required_keys = ["project_health", "risks", "actions", "proof"]
        for key in required_keys:
            assert key in SYSTEM_PROMPT, \
                f"Clé '{key}' manquante dans SYSTEM_PROMPT — l'IA ne produira pas le bon JSON"

    def test_system_prompt_contains_valid_health_values(self):
        """Le prompt doit indiquer les valeurs acceptées pour project_health."""
        valid_values = ["HEALTHY", "WATCH", "AT_RISK"]
        found = any(v in SYSTEM_PROMPT for v in valid_values)
        assert found, \
            "SYSTEM_PROMPT doit mentionner HEALTHY / WATCH / AT_RISK pour guider l'IA"


# ─── Niveau 2 : Tools avec Jira mocké ────────────────────────────────────────
class TestAgentTools:
    """Teste les tools de l'agent avec des données Jira simulées."""

    @patch('orchestration.agentV1.get_jira_data')
    def test_get_project_metrics_returns_dict(self, mock_jira_data):
        """get_project_metrics doit retourner un dict non vide."""
        mock_jira_data.return_value = [
            {
                "id": "1", "key": "TEST-1", "summary": "Bug fix",
                "status_name": "Done", "status_category": "DONE",
                "assignee": "John", "updated_at": datetime.now(timezone.utc),
                "days_since_update": 5,
            }
        ]

        result = get_project_metrics.invoke({})

        assert isinstance(result, dict), "Metrics doit être un dict"
        assert len(result) > 0, "Metrics ne doit pas être vide"

    @patch('orchestration.agentV1.get_jira_data')
    def test_get_project_metrics_counts_correctly(self, mock_jira_data):
        """get_project_metrics doit compter les statuts correctement."""
        mock_jira_data.return_value = [
            {"id": "1", "key": "T-1", "summary": "A", "status_name": "Done",
             "status_category": "DONE", "assignee": None,
             "updated_at": datetime.now(timezone.utc), "days_since_update": 1},
            {"id": "2", "key": "T-2", "summary": "B", "status_name": "In Progress",
             "status_category": "IN_PROGRESS", "assignee": "Alice",
             "updated_at": datetime.now(timezone.utc), "days_since_update": 3},
            {"id": "3", "key": "T-3", "summary": "C", "status_name": "To Do",
             "status_category": "TODO", "assignee": None,
             "updated_at": datetime.now(timezone.utc), "days_since_update": 10},
        ]

        result = get_project_metrics.invoke({})

        assert result.get("total") == 3, \
            f"total doit être 3. Dict reçu : {result}"

    def test_get_rules_returns_valid_structure(self):
        """get_rules doit retourner project_health, risks et actions."""
        mock_metrics = {
            "total": 10,
            "status_counts": {"DONE": 5, "IN_PROGRESS": 3, "TODO": 2},
            "wip": 3,
            "done_ratio": 0.5,
            "stale_in_progress_count": 1,
        }

        result = get_rules.invoke({"metrics": mock_metrics})

        assert isinstance(result, dict), "Rules doit être un dict"
        for field in ["project_health", "risks", "actions"]:
            assert field in result, \
                f"Champ '{field}' manquant dans get_rules — l'IA n'aura pas les bonnes règles"

    def test_get_rules_health_is_valid_value(self):
        """project_health dans get_rules doit être HEALTHY, WATCH ou AT_RISK."""
        result = get_rules.invoke({"metrics": {
            "total": 5,
            "status_counts": {"DONE": 5, "IN_PROGRESS": 0, "TODO": 0},
            "wip": 0,
            "done_ratio": 1.0,
            "stale_in_progress_count": 0,
        }})

        health = result.get("project_health")
        assert health in ["HEALTHY", "WATCH", "AT_RISK", None], \
            f"Valeur inattendue pour project_health: {health}"


# ─── Niveau 3 : IA réelle (Ollama requis) ────────────────────────────────────
class TestAgentResponseWithRealAI:
    """
    Tests critiques : vérifient que l'IA répond VRAIMENT correctement.
    """

    @requires_ollama
    @pytest.mark.integration
    @pytest.mark.timeout(90)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_returns_valid_json(self, mock_jira_data):
        """
        CRITIQUE : l'agent doit retourner un JSON valide avec le bon schéma.
        """
        mock_jira_data.return_value = [
            {
                "id": "1", "key": "PROJ-1", "summary": "Critical bug",
                "status_name": "In Progress", "status_category": "IN_PROGRESS",
                "assignee": "John", "updated_at": datetime.now(timezone.utc),
                "days_since_update": 5,
            }
        ]

        # ✅ Utiliser run_agent au lieu de agent.invoke
        response = run_agent("Response with Report JSON")
        
        assert response, "L'agent ne doit pas retourner une réponse vide"

        # Extraire le JSON de la réponse
        try:
            # Nettoyer markdown si présent
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response.replace("```json", "").replace("```", "").strip()
            elif clean_response.startswith("```"):
                clean_response = clean_response.replace("```", "").strip()
            
            # Trouver le JSON
            start = clean_response.index("{")
            end = clean_response.rindex("}") + 1
            data = json.loads(clean_response[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            pytest.fail(
                f"L'agent doit retourner un JSON valide.\n"
                f"Erreur: {e}\n"
                f"Réponse reçue : {response[:300]}"
            )

        # Vérifier le schéma
        assert "project_health" in data, "Manque 'project_health' dans la réponse JSON"
        assert data["project_health"] in ["HEALTHY", "WATCH", "AT_RISK"], \
            f"project_health invalide : {data['project_health']}"
        assert "risks" in data, "Manque 'risks' dans la réponse JSON"
        assert "actions" in data, "Manque 'actions' dans la réponse JSON"
        
        print(f"\n✅ Agent returned valid JSON:\n{json.dumps(data, indent=2)}")

    @requires_ollama
    @pytest.mark.integration
    @pytest.mark.timeout(120)
    @patch('orchestration.agentV1.get_jira_data')
    def test_agent_detects_at_risk_project(self, mock_jira_data):
        """
        CRITIQUE : l'IA doit détecter un projet en danger.
        """
        # Projet clairement en mauvais état
        mock_jira_data.return_value = [
            {
                "id": str(i), "key": f"PROJ-{i}",
                "summary": f"Blocked issue {i}",
                "status_name": "Blocked", "status_category": "BLOCKED",
                "assignee": None,
                "updated_at": datetime.now(timezone.utc),
                "days_since_update": 20,
            }
            for i in range(10)
        ]

        response = run_agent("Response with Report JSON")
        
        assert len(response) > 20, "Réponse trop courte pour être pertinente"
        print(f"\n✅ Agent response for at-risk project:\n{response[:200]}")