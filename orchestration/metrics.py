# metrics.py
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List


UNASSIGNED = "UNASSIGNED"


def compute_signals(tickets: List[Dict], stale_days: int = 5) -> Dict:
    """
    Expects each ticket to already contain:
    - status_category : "todo" | "in_progress" | "done"
    - assignee        : str | None
    - days_since_update : int
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
    status_counts = Counter(t["status_category"] for t in tickets)
    for k in ("todo", "in_progress", "done"):
        status_counts.setdefault(k, 0)

    wip = status_counts["in_progress"]
    done = status_counts["done"]

    # --- WIP analysis ---
    stale_in_progress = 0
    unassigned_in_progress = 0
    assignee_wip = Counter()

    for t in tickets:
        if t["status_category"] != "in_progress":
            continue

        if t["days_since_update"] > stale_days:
            stale_in_progress += 1

        assignee = t["assignee"] if t["assignee"] else UNASSIGNED
        assignee_wip[assignee] += 1

        if assignee == UNASSIGNED:
            unassigned_in_progress += 1

    top_assignees = [[name, count] for name, count in assignee_wip.most_common(5)]
    top1 = top_assignees[0][1] if top_assignees else 0
    top1_share = (top1 / wip) if wip else 0.0

    return {
        # Total number of tickets analyzed (scope of this snapshot).
        # Used as the denominator for all ratios.
        "total": total,

        # Count of tickets per canonical status.
        # Example: {"todo": 4, "in_progress": 3, "done": 2}
        # Shows overall flow distribution.
        "status_counts": dict(status_counts),

        # Work In Progress (WIP):
        # Number of tickets currently being actively worked on.
        # High WIP usually slows delivery due to context switching.
        "wip": wip,

        # Ratio of WIP to total tickets.
        # Indicates how much of the system is currently "open".
        # Typical interpretation:
        #   < 0.4  → underutilized or blocked upstream
        #   0.4–0.6 → healthy flow
        #   > 0.6  → congestion risk
        "wip_ratio": wip / total,

        # Ratio of completed tickets to total tickets.
        # This is a snapshot completion ratio, NOT velocity.
        # Useful when tracked over time to observe delivery trend.
        "done_ratio": done / total,

        # Number of in-progress tickets that have exceeded the staleness threshold.
        # Stale WIP often indicates blockers, review bottlenecks, or hidden dependencies.
        "stale_in_progress_count": stale_in_progress,

        # Ratio of stale in-progress tickets to total WIP.
        # Shows how unhealthy the active work is.
        #   0.0  → clean flow
        #   ~0.2 → warning zone
        #   >0.3 → high risk of delivery slowdown
        "stale_in_progress_ratio": (stale_in_progress / wip) if wip else 0.0,

        # Number of in-progress tickets with no assignee.
        # Unassigned WIP is a strong predictor of delay.
        # In healthy systems, this should be zero.
        "unassigned_in_progress_count": unassigned_in_progress,

        # Distribution of WIP per assignee.
        # Example: {"Alice": 2, "Bob": 1}
        # Used to detect overload, imbalance, and knowledge silos.
        "assignee_wip": dict(assignee_wip),

        # List of top assignees by WIP count (sorted descending).
        # Example: [["Alice", 2], ["Bob", 1]]
        # Makes ownership concentration visible at a glance.
        "top_assignees": top_assignees,

        # Share of WIP owned by the top assignee.
        # This is a key risk indicator:
        #   < 0.4 → healthy distribution
        #   0.4–0.6 → dependency risk
        #   > 0.6 → single point of failure
        "top1_wip_share": top1_share,
    }
