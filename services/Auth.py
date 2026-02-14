import os
from requests import Session
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv


load_dotenv()


def jira_session() -> Session:
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")

    if not email or not token:
        raise ValueError("Missing JIRA credentials in .env")

    session = Session()
    session.auth = HTTPBasicAuth(email, token)

    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "jira-extractor/1.0"
    })

    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)

    return session
