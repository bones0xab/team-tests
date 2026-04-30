# metrics.py
from collections import Counter
from typing import Dict, List

UNASSIGNED = "UNASSIGNED"

def compute_signals(tickets: List[Dict], stale_days: int = 5) -> Dict:
    """
    Expects each ticket to be normalized with 7 blocs:
      - t["semantics"]["status_canonical"] : "todo" | "in_progress" | "done" | "unknown"
      - t["temporality"]["days_since_update"] : int | None
      - t["actors"]["assignee"] : {"id": str, "name": str} | None
    """

    total = len(tickets)
    if total == 0:
        return {
            "total": 0,
            "status_counts": {},
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

    # --- Status distribution ---
    status_counts = Counter(
        (t.get("semantics") or {}).get("status_canonical", "unknown")
        for t in tickets
    )
    # ensure canonical keys exist
    for k in ("todo", "in_progress", "done", "unknown"):
        status_counts.setdefault(k, 0)

    wip = status_counts["in_progress"]
    done = status_counts["done"]

    # --- WIP analysis ---
    stale_in_progress = 0
    unassigned_in_progress = 0
    assignee_wip = Counter()

    for t in tickets:
        status = (t.get("semantics") or {}).get("status_canonical", "unknown")
        if status != "in_progress":
            continue

        days = (t.get("temporality") or {}).get("days_since_update")
        if isinstance(days, int) and days > stale_days:
            stale_in_progress += 1

        assignee_obj = (t.get("actors") or {}).get("assignee")
        assignee_id = (assignee_obj or {}).get("id") if isinstance(assignee_obj, dict) else None
        assignee_key = assignee_id if assignee_id else UNASSIGNED

        assignee_wip[assignee_key] += 1

        if assignee_key == UNASSIGNED:
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