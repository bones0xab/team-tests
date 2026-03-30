# services/Auth.py

import os
import logging
from dataclasses import dataclass
from typing import Tuple

from requests import Session
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    pat: str
    user_agent: str = "jira-extractor/2.0"
    timeout: Tuple[float, float] = (3.05, 30.0)
    max_retries: int = 5
    backoff_factor: float = 0.5
    pool_connections: int = 10
    pool_maxsize: int = 50


def load_jira_config() -> JiraConfig:
    base_url = os.getenv("JIRA_BASE")
    pat = os.getenv("JIRA_DC_PAT")

    if not base_url or not pat:
        raise ConfigError("JIRA_BASE or JIRA_DC_PAT is not set")

    return JiraConfig(
        base_url=base_url.rstrip("/"),
        pat=pat,
    )


class JiraSession(Session):
    def __init__(self, default_timeout:  Tuple[float, float], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_timeout = default_timeout

    def request(self, method, url,*args, **kwargs):
        kwargs.setdefault("timeout", self._default_timeout)
        return super().request(method, url,*args, **kwargs)


def build_jira_session(config: JiraConfig) -> Session:
    session = JiraSession(default_timeout=config.timeout)

    session.headers.update({
        "Authorization": f"Bearer {config.pat}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": config.user_agent,
    })

    retry = Retry(
        total=config.max_retries,
        connect=config.max_retries,
        read=config.max_retries,
        status=config.max_retries,
        backoff_factor=config.backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS", "PUT", "DELETE"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=config.pool_connections,
        pool_maxsize=config.pool_maxsize,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session
