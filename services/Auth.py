import os
from requests import Session
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv


load_dotenv()


def jira_session() -> Session:
    s = Session()
    s.auth = HTTPBasicAuth(
        os.environ["JIRA_EMAIL"],
        os.environ["JIRA_API_TOKEN"],
    )
    s.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "jira-extractor/1.0"
    })

    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET","POST"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


