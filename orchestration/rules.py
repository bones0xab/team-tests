from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class RuleHit:
    rule: str
    severity: str  # "info" | "warn" | "risk"
    signal: str
    value: float | int
    threshold: float | int
    why: str


DEFAULT_THRESHOLDS = {
    # Flow / congestion
    "WIP_RATIO_WARN": 0.60,
    "WIP_RATIO_RISK": 0.70,

    # Aging / staleness
    "STALE_WIP_RATIO_WARN": 0.15,
    "STALE_WIP_RATIO_RISK": 0.30,

    # Ownership / dependency
    "TOP1_WIP_SHARE_WARN": 0.40,
    "TOP1_WIP_SHARE_RISK": 0.60,

    # Hygiene
    "UNASSIGNED_WIP_RISK": 1,  # >=1 unassigned in-progress is a risk
}

def evaluate_rules(metrics: Dict[str, Any], thresholds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    hits: List[RuleHit] = []

    wip_ratio = float(metrics.get("wip_ratio", 0.0))
    stale_ratio = float(metrics.get("stale_in_progress_ratio", 0.0))
    top1_share = float(metrics.get("top1_wip_share", 0.0))
    unassigned_wip = int(metrics.get("unassigned_in_progress_count", 0))

    # --- Congestion ---
    if wip_ratio >= t["WIP_RATIO_RISK"]:
        hits.append(RuleHit(
            rule="WIP_CONGESTION",
            severity="risk",
            signal="wip_ratio",
            value=wip_ratio,
            threshold=t["WIP_RATIO_RISK"],
            why="WIP is too high; context switching and queueing will slow delivery."
        ))
    elif wip_ratio >= t["WIP_RATIO_WARN"]:
        hits.append(RuleHit(
            rule="WIP_ELEVATED",
            severity="warn",
            signal="wip_ratio",
            value=wip_ratio,
            threshold=t["WIP_RATIO_WARN"],
            why="WIP is trending high; flow may degrade if more work is started."
        ))

    # --- Stale work ---
    if stale_ratio >= t["STALE_WIP_RATIO_RISK"]:
        hits.append(RuleHit(
            rule="STALE_WIP_BOTTLENECK",
            severity="risk",
            signal="stale_in_progress_ratio",
            value=stale_ratio,
            threshold=t["STALE_WIP_RATIO_RISK"],
            why="Large share of WIP is stale; indicates blockers or review bottleneck."
        ))
    elif stale_ratio >= t["STALE_WIP_RATIO_WARN"]:
        hits.append(RuleHit(
            rule="STALE_WIP_WARNING",
            severity="warn",
            signal="stale_in_progress_ratio",
            value=stale_ratio,
            threshold=t["STALE_WIP_RATIO_WARN"],
            why="Some WIP is aging; investigate early to avoid delays."
        ))

    # --- Unassigned WIP ---
    if unassigned_wip >= t["UNASSIGNED_WIP_RISK"]:
        hits.append(RuleHit(
            rule="UNASSIGNED_WIP",
            severity="risk",
            signal="unassigned_in_progress_count",
            value=unassigned_wip,
            threshold=t["UNASSIGNED_WIP_RISK"],
            why="Unassigned in-progress work has unclear ownership and often stalls."
        ))

    # --- Ownership concentration ---
    if top1_share >= t["TOP1_WIP_SHARE_RISK"]:
        hits.append(RuleHit(
            rule="SINGLE_POINT_OF_FAILURE",
            severity="risk",
            signal="top1_wip_share",
            value=top1_share,
            threshold=t["TOP1_WIP_SHARE_RISK"],
            why="WIP is concentrated on one person; dependency risk is high."
        ))
    elif top1_share >= t["TOP1_WIP_SHARE_WARN"]:
        hits.append(RuleHit(
            rule="DEPENDENCY_FORMING",
            severity="warn",
            signal="top1_wip_share",
            value=top1_share,
            threshold=t["TOP1_WIP_SHARE_WARN"],
            why="WIP concentration is moderate; dependency risk may be forming."
        ))

    # --- Health decision (deterministic) ---
    # Senior rule: health is derived from severity levels, not “feelings”.
    severities = {h.severity for h in hits}
    if "risk" in severities:
        health = "AT_RISK"
    elif "warn" in severities:
        health = "WATCH"
    else:
        health = "HEALTHY"

    # --- Convert to compact output ---
    risks = []
    actions = []
    for h in hits:
        if h.severity in ("warn", "risk"):
            risks.append(h.why)

            # Minimal action mapping (keep short & non-destructive)
            if h.rule in ("WIP_CONGESTION", "WIP_ELEVATED"):
                actions.append("Limit WIP: prioritize finishing active work before starting new tickets.")
            elif h.rule in ("STALE_WIP_BOTTLENECK", "STALE_WIP_WARNING"):
                actions.append("Review aging WIP: identify blockers and unblock the oldest items.")
            elif h.rule == "UNASSIGNED_WIP":
                actions.append("Assign owners to all in-progress tickets and clarify next steps.")
            elif h.rule in ("SINGLE_POINT_OF_FAILURE", "DEPENDENCY_FORMING"):
                actions.append("Balance ownership: redistribute one active item or pair to reduce dependency risk.")

    # Deduplicate while preserving order
    def dedupe(xs: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    proof = [
        {
            "rule": h.rule,
            "severity": h.severity,
            "signal": h.signal,
            "value": h.value,
            "threshold": h.threshold,
            "why": h.why,
        }
        for h in hits
    ]

    return {
        "project_health": health,
        "risks": dedupe(risks)[:3],
        "actions": dedupe(actions)[:3],
        "proof": proof,
    }
