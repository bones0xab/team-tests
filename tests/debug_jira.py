from services.Fetch import search_issues
import json

print("=" * 60)
print("DEBUG: Testing Jira Connection")
print("=" * 60)

# Test 1: Simple query
print("\n1️⃣ Testing: project=KAN")
issues = list(search_issues("project=KAN", ["summary", "status"]))
print(f"   Result: {len(issues)} issues")

if issues:
    print("\n   First issue:")
    print(json.dumps(issues[0], indent=2, default=str))
else:
    print("   ⚠️ No issues returned!")

# Test 2: Even simpler - no JQL
print("\n2️⃣ Testing: Empty JQL")
issues2 = list(search_issues("", ["summary"]))
print(f"   Result: {len(issues2)} issues")

# Test 3: Direct API test
print("\n3️⃣ Testing: Direct API call")
from services.Auth import jira_session
import os
from dotenv import load_dotenv

load_dotenv()

s = jira_session()
base = os.getenv("JIRA_URL")

r = s.get(f"{base}/rest/api/3/search/jql", params={"jql": "project=KAN", "maxResults": 5}, timeout=10)
print(f"   Status: {r.status_code}")
print(f"   Response: {r.text[:500]}")

if r.status_code == 200:
    data = r.json()
    print(f"\n   Total issues in response: {data.get('total', 0)}")
    print(f"   Issues returned: {len(data.get('issues', []))}")