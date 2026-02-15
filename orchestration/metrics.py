# orchestration/metrics.py
from collections import Counter
from typing import Dict, List, Any

UNASSIGNED = "UNASSIGNED"


def compute_signals(tickets: List[Dict], stale_days: int = 7) -> Dict[str, Any]:
    """
    Compute project metrics from normalized tickets.
    
    Supports TWO structures:
    1. New structure: direct keys (status_category, days_since_update, assignee)
    2. Old structure: nested (semantics, temporality, actors)
    
    Args:
        tickets: List of normalized issue dictionaries
        stale_days: Number of days to consider an issue stale
        
    Returns:
        Dictionary with project metrics
    """
    total = len(tickets)
    
    if total == 0:
        return {
            "total": 0,
            "status_counts": {"TODO": 0, "IN_PROGRESS": 0, "DONE": 0, "BLOCKED": 0},
            "wip": 0,
            "wip_ratio": 0.0,
            "done_ratio": 0.0,
            "stale_in_progress_count": 0,
            "stale_in_progress_ratio": 0.0,
            "unassigned_in_progress_count": 0,
            "assignee_wip": {},
            "top_assignees": [],
            "top1_wip_share": 0.0,
        }
    
    # --- Detect structure and extract status ---
    status_list = []
    for t in tickets:
        # Try new structure first
        if "status_category" in t:
            status_list.append(t["status_category"])
        # Fallback to old structure
        elif "semantics" in t and isinstance(t["semantics"], dict):
            canonical = t["semantics"].get("status_canonical", "unknown")
            # Map old names to new names
            mapping = {
                "todo": "TODO",
                "in_progress": "IN_PROGRESS",
                "done": "DONE",
                "unknown": "BLOCKED"
            }
            status_list.append(mapping.get(canonical, "BLOCKED"))
        else:
            status_list.append("BLOCKED")
    
    status_counts = Counter(status_list)
    
    # Ensure all keys exist
    for k in ("TODO", "IN_PROGRESS", "DONE", "BLOCKED"):
        status_counts.setdefault(k, 0)
    
    wip = status_counts["IN_PROGRESS"]
    done = status_counts["DONE"]
    
    # --- WIP analysis ---
    stale_in_progress = 0
    unassigned_in_progress = 0
    assignee_wip = Counter()
    
    for t in tickets:
        # Get status
        if "status_category" in t:
            status = t["status_category"]
        elif "semantics" in t:
            canonical = t.get("semantics", {}).get("status_canonical", "unknown")
            mapping = {"todo": "TODO", "in_progress": "IN_PROGRESS", "done": "DONE", "unknown": "BLOCKED"}
            status = mapping.get(canonical, "BLOCKED")
        else:
            status = "BLOCKED"
        
        if status != "IN_PROGRESS":
            continue
        
        # Get days_since_update
        if "days_since_update" in t:
            days = t["days_since_update"]
        elif "temporality" in t:
            days = t.get("temporality", {}).get("days_since_update")
        else:
            days = None
        
        if isinstance(days, int) and days > stale_days:
            stale_in_progress += 1
        
        # Get assignee
        if "assignee" in t:
            assignee_name = t["assignee"] if t["assignee"] else UNASSIGNED
        elif "actors" in t:
            assignee_obj = t.get("actors", {}).get("assignee")
            if isinstance(assignee_obj, dict):
                assignee_name = assignee_obj.get("name") or assignee_obj.get("id") or UNASSIGNED
            else:
                assignee_name = UNASSIGNED
        else:
            assignee_name = UNASSIGNED
        
        assignee_wip[assignee_name] += 1
        
        if assignee_name == UNASSIGNED:
            unassigned_in_progress += 1
    
    top_assignees = [[name, count] for name, count in assignee_wip.most_common(5)]
    top1 = top_assignees[0][1] if top_assignees else 0
    top1_share = (top1 / wip) if wip else 0.0
    
    return {
        "total": total,
        "status_counts": dict(status_counts),
        "wip": wip,
        "wip_ratio": wip / total,
        "done_ratio": done / total,
        "stale_in_progress_count": stale_in_progress,
        "stale_in_progress_ratio": (stale_in_progress / wip) if wip else 0.0,
        "unassigned_in_progress_count": unassigned_in_progress,
        "assignee_wip": dict(assignee_wip),
        "top_assignees": top_assignees,
        "top1_wip_share": top1_share,
    }