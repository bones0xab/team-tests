import inspect
import os
import pytest
from unittest.mock import MagicMock, patch

# Real project constants — must match Fetch.py and .env exactly
JIRA_BASE_URL = "https://derraznour.atlassian.net"
JIRA_EMAIL    = "derraznour@gmail.com"


# ─── Helper: detect real Jira credentials from .env ───────────────────────────

def _jira_creds_available() -> bool:
    from dotenv import load_dotenv
    load_dotenv()
    return bool(os.getenv("JIRA_EMAIL") and os.getenv("JIRA_API_TOKEN"))


SKIP_JIRA = pytest.mark.skipif(
    not _jira_creds_available(),
    reason="JIRA_EMAIL / JIRA_API_TOKEN not found in .env — skipping real Jira tests"
)


# ─── 1. Structural tests — no network ─────────────────────────────────────────

class TestFetchStructure:

    def test_search_issues_is_importable(self):
        from services.Fetch import search_issues
        assert callable(search_issues)

    def test_search_issues_is_generator_function(self):
        from services.Fetch import search_issues
        assert inspect.isgeneratorfunction(search_issues), \
            "search_issues must use 'yield' — it must be a generator function"

    def test_search_issues_signature(self):
        from services.Fetch import search_issues
        sig = inspect.signature(search_issues)
        params = list(sig.parameters.keys())
        assert "jql" in params, "Must accept 'jql' parameter"
        assert "fields" in params, "Must accept 'fields' parameter"

    def test_jira_base_url_is_correct(self):
        from services import Fetch
        assert hasattr(Fetch, "JIRA_BASE"), "JIRA_BASE must be defined in Fetch.py"
        assert Fetch.JIRA_BASE == JIRA_BASE_URL, \
            f"JIRA_BASE must be '{JIRA_BASE_URL}', got '{Fetch.JIRA_BASE}'"

    def test_auth_session_is_importable(self):
        from services.Auth import jira_session
        assert callable(jira_session)

class TestFetchUnit:

    def _make_response(self, issues: list, status: int = 200) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = {"issues": issues}
        mock_resp.text = "error body" if status >= 400 else ""
        return mock_resp

    @patch('services.Fetch.jira_session')
    def test_returns_issues_single_page(self, mock_session_fn):
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_session.get.side_effect = [
            self._make_response([
                {"id": "1", "key": "TEST-1", "fields": {"summary": "Bug A"}},
                {"id": "2", "key": "TEST-2", "fields": {"summary": "Bug B"}},
            ]),
            self._make_response([]),  # empty page → generator stops
        ]

        result = list(search_issues("project = TEST", ["summary", "status"]))

        assert len(result) == 2
        assert result[0]["key"] == "TEST-1"
        assert result[1]["key"] == "TEST-2"

    @patch('services.Fetch.jira_session')
    def test_paginates_across_multiple_pages(self, mock_session_fn):
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session

        page1 = [{"id": str(i), "key": f"T-{i}", "fields": {}} for i in range(50)]
        page2 = [{"id": str(i), "key": f"T-{i}", "fields": {}} for i in range(50, 80)]
        mock_session.get.side_effect = [
            self._make_response(page1),
            self._make_response(page2),
            self._make_response([]),
        ]

        result = list(search_issues("project = BIG", ["summary"], batch=50))

        assert len(result) == 80
        # Verify startAt was incremented correctly across pages
        calls = mock_session.get.call_args_list
        assert calls[0][1]["params"]["startAt"] == 0
        assert calls[1][1]["params"]["startAt"] == 50
        assert calls[2][1]["params"]["startAt"] == 80

    @patch('services.Fetch.jira_session')
    def test_empty_jira_response_returns_empty_list(self, mock_session_fn):
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_session.get.return_value = self._make_response([])

        result = list(search_issues("project = EMPTY", ["summary"]))
        assert result == []

    @patch('services.Fetch.jira_session')
    def test_stops_immediately_on_http_401(self, mock_session_fn):
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_session.get.return_value = self._make_response([], status=401)

        result = list(search_issues("project = ANY", ["summary"]))

        assert result == []
        assert mock_session.get.call_count == 1, "Must NOT retry on 401"

    @patch('services.Fetch.jira_session')
    def test_stops_immediately_on_http_400(self, mock_session_fn):
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_session.get.return_value = self._make_response([], status=400)

        result = list(search_issues("INVALID JQL !!!", ["summary"]))

        assert result == []

    @patch('services.Fetch.jira_session')
    def test_calls_correct_jira_api_url(self, mock_session_fn):
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_session.get.return_value = self._make_response([])

        list(search_issues("project = TEST", ["summary"]))

        called_url = mock_session.get.call_args[0][0]
        assert called_url == f"{JIRA_BASE_URL}/rest/api/3/search/jql", \
            f"Expected URL '{JIRA_BASE_URL}/rest/api/3/search/jql', got '{called_url}'"

    @patch('services.Fetch.jira_session')
    def test_fields_list_joined_as_comma_string(self, mock_session_fn):
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_session.get.return_value = self._make_response([])

        list(search_issues("project = TEST", ["summary", "status", "assignee"]))

        params = mock_session.get.call_args[1]["params"]
        assert params["fields"] == "summary,status,assignee"

    @patch('services.Fetch.jira_session')
    def test_timeout_is_set_on_every_request(self, mock_session_fn):
        """CRITICAL: Every request must have a timeout — prevents hanging forever."""
        from services.Fetch import search_issues
        mock_session = MagicMock()
        mock_session_fn.return_value = mock_session
        mock_session.get.return_value = self._make_response([])

        list(search_issues("project = TEST", ["summary"]))

        call_kwargs = mock_session.get.call_args[1]
        assert "timeout" in call_kwargs, \
            "search_issues MUST pass timeout= to prevent infinite hanging"
        assert call_kwargs["timeout"] > 0


# ─── 3. Auth unit tests ────────────────────────────────────────────────────────

class TestAuthUnit:

    # Real credentials from .env — used so jira_session() doesn't crash on missing env vars
    REAL_ENV = {
        "JIRA_EMAIL": JIRA_EMAIL,
        "JIRA_API_TOKEN": "test-token-no-network-call-made",
    }

    @patch.dict(os.environ, {"JIRA_EMAIL": JIRA_EMAIL, "JIRA_API_TOKEN": "test-token"})
    def test_session_uses_basic_auth(self):
        """Session must authenticate with the correct Jira email."""
        from services.Auth import jira_session
        from requests.auth import HTTPBasicAuth

        s = jira_session()

        assert isinstance(s.auth, HTTPBasicAuth), "Must use HTTPBasicAuth"
        assert s.auth.username == JIRA_EMAIL, \
            f"Username must be '{JIRA_EMAIL}', got '{s.auth.username}'"
        # Password comes from env — we just verify it's not empty
        assert s.auth.password, "API token must not be empty"

    @patch.dict(os.environ, {"JIRA_EMAIL": JIRA_EMAIL, "JIRA_API_TOKEN": "test-token"})
    def test_session_sends_json_headers(self):
        """Session must send JSON headers — required by Jira REST API v3."""
        from services.Auth import jira_session

        s = jira_session()

        assert s.headers.get("Accept") == "application/json"
        assert s.headers.get("Content-Type") == "application/json"

    @patch.dict(os.environ, {"JIRA_EMAIL": JIRA_EMAIL, "JIRA_API_TOKEN": "test-token"})
    def test_session_has_retry_adapter(self):
        """
        Session must mount an HTTPAdapter with retries on https://.
        This protects against transient Jira 429/500/502/503/504 errors.

        Fix for 'Cannot access attribute max_retries for class _BaseAdapter':
        get_adapter() is typed as returning _BaseAdapter in requests stubs,
        but Auth.py mounts an HTTPAdapter — so we assert isinstance first,
        then access max_retries on the correctly-typed variable.
        """
        from services.Auth import jira_session
        from requests.adapters import HTTPAdapter

        s = jira_session()
        adapter = s.get_adapter(JIRA_BASE_URL)

        # Step 1: assert it IS an HTTPAdapter (real runtime check)
        assert isinstance(adapter, HTTPAdapter), \
            f"Adapter for {JIRA_BASE_URL} must be HTTPAdapter, got {type(adapter)}"

        # Step 2: now type-checker knows it's HTTPAdapter — no more attribute error
        assert adapter.max_retries is not None, "Retry policy must be configured"
        assert (adapter.max_retries.total or 0) >= 1, \
            f"Must have at least 1 retry, got {adapter.max_retries.total}"
        assert 429 in adapter.max_retries.status_forcelist, \
            "Must retry on 429 (rate limit)"
        assert 503 in adapter.max_retries.status_forcelist, \
            "Must retry on 503 (service unavailable)"

    @patch.dict(os.environ, {"JIRA_EMAIL": JIRA_EMAIL, "JIRA_API_TOKEN": "test-token"})
    def test_session_user_agent_is_set(self):
        """Session must identify itself with a User-Agent."""
        from services.Auth import jira_session

        s = jira_session()

        assert "User-Agent" in s.headers
        assert len(s.headers["User-Agent"]) > 0


# ─── 4. Real integration tests — require .env credentials ─────────────────────
@pytest.mark.integration
class TestFetchIntegration:
    """
    Tests d'intégration avec Jira RÉEL.
    Nécessite des credentials Jira valides dans .env
    """

    @SKIP_JIRA
    @pytest.mark.jira
    @pytest.mark.timeout(20)
    def test_real_jira_authentication(self):
        """
        Credentials from .env must authenticate successfully.
        Calls GET /rest/api/3/myself — the standard Jira auth check endpoint.
        """
        from services.Auth import jira_session

        s = jira_session()
        r = s.get(f"{JIRA_BASE_URL}/rest/api/3/myself", timeout=10)

        assert r.status_code == 200, (
            f"Jira authentication failed (HTTP {r.status_code}). "
            f"Check JIRA_EMAIL={JIRA_EMAIL} and JIRA_API_TOKEN in .env\n"
            f"Response: {r.text[:200]}"
        )
        data = r.json()
        assert "accountId" in data or "emailAddress" in data, \
            f"Unexpected /myself response: {data}"

        # Verify the authenticated user matches the expected email
        if "emailAddress" in data:
            assert data["emailAddress"] == JIRA_EMAIL, \
                f"Authenticated as '{data['emailAddress']}' but expected '{JIRA_EMAIL}'"

    @SKIP_JIRA
    @pytest.mark.jira
    @pytest.mark.timeout(60)
    def test_real_search_returns_valid_structure(self):
        """
        Real JQL search against derraznour.atlassian.net.
        Fetches up to 3 issues from the last 30 days.
        """
        from services.Fetch import search_issues

        issues = list(search_issues(
            "created >= -30 ORDER BY created DESC",
            ["summary", "status"],
            batch=3
        ))

        assert isinstance(issues, list), "Must return a list"

        if issues:
            first = issues[0]
            assert "id" in first,     "Issue must have 'id'"
            assert "key" in first,    "Issue must have 'key'"
            assert "fields" in first, "Issue must have 'fields'"
            assert "summary" in first["fields"], "Fields must include 'summary'"
            # Key format must be PROJECT-NUMBER (e.g. KAN-1)
            assert "-" in first["key"], \
                f"Key '{first['key']}' does not look like a valid Jira key"

    @SKIP_JIRA
    @pytest.mark.jira
    @pytest.mark.timeout(20)
    def test_real_search_plus_normalisation(self):
        """
        Full pipeline: Fetch.py → Normalisation.py → valid normalized dict.
        Tests the exact data flow used by the AI agent.
        """
        from services.Fetch import search_issues
        from services.Normalisation import normalize_issue

        raw_issues = list(search_issues(
            "created >= -30 ORDER BY created DESC",
            ["summary", "status", "assignee", "updated"],
            batch=3
        ))

        if not raw_issues:
            pytest.skip("No issues in last 30 days in this Jira workspace")

        for raw in raw_issues:
            normalized = normalize_issue(raw)

            assert "id" in normalized
            assert "key" in normalized
            assert "summary" in normalized
            assert "status_name" in normalized
            assert "status_category" in normalized
            assert isinstance(normalized["days_since_update"], int)
            assert normalized["days_since_update"] >= 0, \
                f"days_since_update must be >= 0, got {normalized['days_since_update']}"

    @SKIP_JIRA
    @pytest.mark.jira
    @pytest.mark.timeout(20)
    def test_real_invalid_jql_returns_empty(self):
        """
        Jira returns 400 on invalid JQL.
        The generator must return an empty list instead of crashing.
        """
        from services.Fetch import search_issues

        result = list(search_issues("INVALID JQL SYNTAX !!!", ["summary"]))

        assert result == [], \
            f"Expected empty list on invalid JQL, got {len(result)} issues"