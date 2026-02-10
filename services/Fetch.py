from typing import Iterator
from services.Auth import jira_session

print("BANANA")
JIRA_BASE = "https://derraznour.atlassian.net"



def search_issues(jql: str, fields: list[str], batch=50) -> Iterator[dict]:
    s = jira_session()
    start = 0

    r = s.get(
        f"{JIRA_BASE}/rest/api/3/search/jql",
        params={
            "jql": jql,
            "fields": ",".join(fields),
            "startAt": start,
            "maxResults": batch,
        },
        timeout=15,
    )
    if r.status_code >= 400:
        print("ERROR", r.status_code)
        print(r.text[:500])
        return  # stop generator
    data = r.json()
    issues = data["issues"]

    yield from issues
    start += len(issues)



