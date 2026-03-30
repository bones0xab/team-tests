from services.Fetch import search_issues
import json
jql = 'project = "MSC1" AND sprint is not EMPTY'
issues = list(search_issues(jql, ['*all'], batch=2))
if issues:
    for k, v in issues[0].get('fields', {}).items():
        print(k, type(v))
        if isinstance(v, list) and v and isinstance(v[0], str) and 'id=' in v[0]:
            print('FOUND SPRINT FIELD!', k, v)

