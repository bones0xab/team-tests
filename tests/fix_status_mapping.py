"""Debug and fix status category mapping"""
from app.services.jira_fetch import search_issues
import json

# Fetch one issue with all status info
issues = list(search_issues('project=KAN', ['summary', 'status'], batch=10))

print("=" * 60)
print("🔍 STATUS CATEGORY ANALYSIS")
print("=" * 60)

statuses_found = {}
for issue in issues:
    status = issue['fields']['status']
    status_name = status['name']
    status_category = status.get('statusCategory', {}).get('key', 'UNKNOWN')
    
    if status_name not in statuses_found:
        statuses_found[status_name] = status_category
        print(f"\n📌 {status_name}")
        print(f"   Category: {status_category}")
        print(f"   Raw: {json.dumps(status, indent=2)}")

print("\n" + "=" * 60)
print("STATUS MAPPING FOR NORMALISATION.PY:")
print("=" * 60)
print("\nAdd this to your Normalisation.py:\n")
print("STATUS_CATEGORY_MAP = {")
for name, cat in statuses_found.items():
    print(f'    "{name}": "{cat}",')
print("}")