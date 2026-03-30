import os
import requests

JIRA_BASE = os.getenv("JIRA_BASE")
JIRA_PAT = os.getenv("JIRA_DC_PAT")

def get_jira_session():
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {JIRA_PAT}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    return session
