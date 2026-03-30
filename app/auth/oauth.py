import os
import httpx
from urllib.parse import urlencode

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("JIRA_REDIRECT_URI")

SCOPES = [
    "read:me",
    "read:jira-user",
    "read:jira-work",
    "write:jira-work",
    "offline_access"
]

def get_authorization_url(state: str) -> str:
    params = {
        "audience": "api.atlassian.com",
        "client_id": CLIENT_ID,
        "scope": " ".join(SCOPES),
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent"
    }
    return f"https://auth.atlassian.com/authorize?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    """Exchange OAuth code for Atlassian access token."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.atlassian.com/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI
            }
        )
        print("CODE : ", code)
        response.raise_for_status()
        return response.json()  # contains access_token