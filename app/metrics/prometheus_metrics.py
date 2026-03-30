# app/metrics/prometheus_metrics.py
# ──────────────────────────────────────────────────────────────
# All Prometheus metrics definitions — single source of truth
# ──────────────────────────────────────────────────────────────

from prometheus_client import Gauge, Counter, Histogram, REGISTRY

# ── Project Health ─────────────────────────────────────────────
project_health_gauge = Gauge(
    "jira_project_health",
    "Project health status (0=HEALTHY, 1=WATCH, 2=AT_RISK)",
    ["project_key"]
)

# ── Issue Counts ───────────────────────────────────────────────
issues_total_gauge = Gauge(
    "jira_issues_total",
    "Total number of Jira issues",
    ["project_key"]
)

issues_wip_gauge = Gauge(
    "jira_issues_wip",
    "Issues currently in progress",
    ["project_key"]
)

issues_done_gauge = Gauge(
    "jira_issues_done",
    "Issues marked as done",
    ["project_key"]
)

issues_stale_gauge = Gauge(
    "jira_issues_stale",
    "Stale in-progress issues (not updated recently)",
    ["project_key"]
)

# ── API Performance ────────────────────────────────────────────
api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"]
)

api_request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# ── Health map ─────────────────────────────────────────────────
HEALTH_MAP = {
    "HEALTHY": 0,
    "WATCH":   1,
    "AT RISK": 2,
    "AT_RISK": 2,
    "UNKNOWN": -1,
}


def update_project_metrics(project_key: str, metrics: dict, rules: dict):
    """
    Called after every fetch_dashboard_data() to update Prometheus gauges.
    """
    health_str = rules.get("project_health", "UNKNOWN")
    health_val = HEALTH_MAP.get(health_str, -1)

    project_health_gauge.labels(project_key=project_key).set(health_val)
    issues_total_gauge.labels(project_key=project_key).set(metrics.get("total", 0))
    issues_wip_gauge.labels(project_key=project_key).set(metrics.get("wip", 0))
    issues_done_gauge.labels(project_key=project_key).set(metrics.get("done", 0))
    issues_stale_gauge.labels(project_key=project_key).set(
        metrics.get("stale_in_progress_count", 0)
    )