
from services.Fetch import search_issues
from services.Normalisation import normalize_issue

if __name__ == '__main__':
    jql = "created >= -30 AND status != Done"
    fields = ["summary","status","assignee","updated"]

    issues = search_issues(jql, fields)
    for i in issues:
        print(normalize_issue(i))
