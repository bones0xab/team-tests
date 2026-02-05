from datetime import datetime

def normalize_issue(issue: dict) -> dict:
    f = issue["fields"]
    print("Am here !")
    return {
        "id": issue["id"],
        "key": issue["key"],
        "summary": f["summary"],
        "status": f["status"]["statusCategory"]["key"],
        "assignee": f["assignee"]["displayName"] if f["assignee"] else None,
        "updated_at": datetime.fromisoformat(f["updated"].replace("Z","")),
    }
