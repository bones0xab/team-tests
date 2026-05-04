import pytest
pytest.skip("Obsolete - tests old services/Fetch.py API", allow_module_level=True)

import inspect
import os
from unittest.mock import MagicMock, patch
from app.services.auth_helpers import build_jira_session
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from app.services.jira_fetch import search_issues
from app.services.normalizer import normalize_issue