from typing import Iterator
from services.Auth import jira_session
import os
from dotenv import load_dotenv

load_dotenv()

print("BANANA")

JIRA_BASE = os.getenv("JIRA_URL", "https://abdlkbirdacosta12.atlassian.net")

def search_issues(jql: str, fields: list[str], batch=50) -> Iterator[dict]:
    """Fetch issues from Jira using new JQL API endpoint"""
    s = jira_session()
    start = 0
    
    while True:
        print(f"🔍 Fetching from {JIRA_BASE} (start={start})...")
        
        # Use the NEW /search/jql endpoint (not /search)
        r = s.get(
            f"{JIRA_BASE}/rest/api/3/search/jql",  # ✅ New endpoint
            params={
                "jql": jql,
                "fields": ",".join(fields),  # Comma-separated string
                "startAt": start,
                "maxResults": batch,
            },
            timeout=15,
        )
        
        print(f"📡 Status: {r.status_code}")
        
        if r.status_code >= 400:
            print(f"❌ ERROR {r.status_code}")
            print(f"Response: {r.text[:500]}")
            return
        
        data = r.json()
        issues = data.get("issues", [])
        total = data.get("total", 0)
        
        print(f"✅ Got {len(issues)} issues (total available: {total})")
        
        if not issues:
            break
        
        yield from issues
        start += len(issues)
        