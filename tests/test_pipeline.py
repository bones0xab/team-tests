"""Test the full data pipeline with friend's Jira"""
from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules
import json

print("=" * 60)
print("🧪 TESTING FULL PIPELINE")
print("=" * 60)

# Step 1: Fetch data
print("\n1️⃣ Fetching issues from Jira...")
issues = list(search_issues('project=KAN', ['summary', 'status', 'assignee', 'updated']))
print(f"   ✅ Fetched: {len(issues)} issues")

# Step 2: Normalize
print("\n2️⃣ Normalizing data...")
normalized = [normalize_issue(i) for i in issues]
print(f"   ✅ Normalized: {len(normalized)} issues")

# Show first issue
if normalized:
    print(f"\n   📋 Sample issue:")
    sample = normalized[0]
    print(f"      Key: {sample['key']}")
    print(f"      Summary: {sample['summary']}")
    print(f"      Status: {sample['status_name']} ({sample['status_category']})")
    print(f"      Assignee: {sample.get('assignee', 'Unassigned')}")
    print(f"      Days since update: {sample['days_since_update']}")

# Step 3: Compute metrics
print("\n3️⃣ Computing metrics...")
metrics = compute_signals(normalized)
print(f"   ✅ Metrics computed:")
print(f"      Total issues: {metrics['total']}")
print(f"      WIP: {metrics['wip']}")
print(f"      WIP ratio: {metrics['wip_ratio']:.1%}")
print(f"      Done ratio: {metrics['done_ratio']:.1%}")
print(f"      Stale in-progress: {metrics['stale_in_progress_count']}")
print(f"      Unassigned WIP: {metrics['unassigned_in_progress_count']}")

# Step 4: Evaluate rules
print("\n4️⃣ Evaluating rules...")
rules = evaluate_rules(metrics)
print(f"   ✅ Rules evaluated:")
print(f"      🚦 Project Health: {rules['project_health']}")
print(f"      ⚠️  Risks: {len(rules['risks'])}")
for risk in rules['risks']:
    print(f"         - {risk}")
print(f"      💡 Actions: {len(rules['actions'])}")
for action in rules['actions']:
    print(f"         - {action}")

# Step 5: Show full report
print("\n5️⃣ Full Report JSON:")
print("-" * 60)
print(json.dumps(rules, indent=2))
print("-" * 60)

print("\n" + "=" * 60)
print("✅ PIPELINE TEST COMPLETE!")
print("=" * 60)