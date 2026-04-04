# services/Auth.py

import os
import logging
from typing import Tuple
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests import Session
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import httpx

logger = logging.getLogger(__name__)

class ConfigError(RuntimeError):
    pass

class JiraConfig(BaseSettings):
    base_url: str = Field(alias="JIRA_BASE", default="")
    pat: str = Field(alias="JIRA_DC_PAT", default="")
    user_agent: str = "jira-extractor/3.0-async"
    timeout: Tuple[float, float] = (3.05, 30.0)
    max_retries: int = 5
    backoff_factor: float = 0.5
    pool_connections: int = 10
    pool_maxsize: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    @property
    def clean_base_url(self) -> str:
        return self.base_url.rstrip("/")

def load_jira_config() -> JiraConfig:
    config = JiraConfig()
    if not config.base_url or not config.pat:
        # Fallback to local process OS just in case python env didn't trigger
        config.base_url = os.getenv("JIRA_BASE", "")
        config.pat = os.getenv("JIRA_DC_PAT", "")
    if not config.base_url or not config.pat:
        raise ConfigError("Missing JIRA_BASE or JIRA_DC_PAT environment variables.")
    return config

# Synchronous Legacy Session (Maintained for backwards compatibility)
class JiraSession(Session):
    def __init__(self, default_timeout: Tuple[float, float], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_timeout = default_timeout

    def request(self, method: str, url, *args, **kwargs):
        kwargs.setdefault("timeout", self._default_timeout)
        return super().request(method, url, *args, **kwargs)

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

# Modern Asynchronous HTTPX Client (Fully unblocks event loop!)
def build_async_jira_client(config: JiraConfig) -> httpx.AsyncClient:
    headers = {
        "Authorization": f"Bearer {config.pat}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": config.user_agent,
    }
    limits = httpx.Limits(
        max_connections=config.pool_maxsize,
        max_keepalive_connections=config.pool_connections
    )
    # httpx expects timeout arguments differently
    timeout = httpx.Timeout(30.0, connect=3.05)
    
    return httpx.AsyncClient(
        base_url=config.clean_base_url,
        headers=headers,
        timeout=timeout,
        limits=limits
    )
