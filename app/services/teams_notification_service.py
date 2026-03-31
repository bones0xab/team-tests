# app/services/teams_notification_service.py

import os
import requests
from typing import Optional
from datetime import datetime


class TeamsNotificationService:

    def __init__(self):
        self.webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("TEAMS_WEBHOOK_URL is not set in environment variables.")

    def _send(self, card: dict) -> bool:
        if not self.webhook_url or self.webhook_url == "disabled":
            print("[TEAMS] Webhook not configured — skipping notification")
            return False
        try:
            response = requests.post(self.webhook_url, json=card, timeout=10)
            response.raise_for_status()
            print(f"[TEAMS] Sent successfully — status {response.status_code}")
            return True
        except Exception as e:
            print(f"[TEAMS] Failed to send notification: {e}")
            return False

    # ── MAIN: Consolidated Portfolio Digest (MessageCard format) ──
    def send_consolidated_digest(self, projects: list[dict]) -> None:
        """
        Sends ONE executive summary MessageCard for all firing projects.
        Uses legacy MessageCard format — compatible with all Teams webhook URLs.
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        critical = [p for p in projects if p.get("severity") == "CRITICAL"]
        warning  = [p for p in projects if p.get("severity") == "WARNING"]

        total_stale = sum(p.get("stale") or 0 for p in projects)
        wip_vals    = [p["wip_pct"] for p in projects if p.get("wip_pct") is not None]
        avg_wip     = round(sum(wip_vals) / len(wip_vals), 1) if wip_vals else 0

        # Sort critical by stale issues descending
        top_critical = sorted(
            critical,
            key=lambda x: x.get("stale") or 0,
            reverse=True
        )[:5]

        # Build facts for top critical projects
        top_facts = []
        for p in top_critical:
            parts = []
            if p.get("stale") is not None:
                parts.append(f"{p['stale']} stale issues")
            if p.get("wip_pct") is not None:
                parts.append(f"{p['wip_pct']}% WIP")
            top_facts.append({
                "name": p["project_key"],
                "value": " · ".join(parts) if parts else "AT RISK"
            })

        # Remaining AT RISK projects
        remaining = [p["project_key"] for p in top_critical[5:]]

        sections = [
            {
                "facts": [
                    {"name": "🔴 AT RISK",        "value": str(len(critical))},
                    {"name": "⚠️ WARNING",         "value": str(len(warning))},
                    {"name": "📋 Total Stale",     "value": f"{total_stale:,} issues"},
                    {"name": "📊 Avg WIP Ratio",   "value": f"{avg_wip}%"},
                    {"name": "📁 Total Projects",  "value": str(len(projects))},
                    {"name": "🕐 Generated",       "value": now},
                ],
                "markdown": True,
            }
        ]

        if top_facts:
            sections.append({
                "title": "🔥 Most Critical Projects",
                "facts": top_facts,
                "markdown": True,
            })

        if remaining:
            sections.append({
                "title": "Also AT RISK",
                "text": ", ".join(remaining),
                "markdown": True,
            })

        sections.append({
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "📈 View Dashboard",
                    "targets": [{"os": "default", "uri": os.getenv("APP_URL", "http://localhost:5173/dashboard")}]
                },
                {
                    "@type": "OpenUri",
                    "name": "📊 View Grafana",
                    "targets": [{"os": "default", "uri": os.getenv("GRAFANA_URL", "http://localhost:3001/d/ntt-jira-health-v1/ntt-data-e28094-jira-project-health?orgId=1&refresh=30s")}]
                },
            ]
        })

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000" if critical else "FFA500",
            "summary": f"Jira Portfolio Health — {len(critical)} AT RISK, {len(warning)} WARNING",
            "title": f"🚨 Jira Portfolio Health Report — {datetime.utcnow().strftime('%Y-%m-%d')}",
            "sections": sections,
        }

        self._send(card)

    # ── WARNING Alert ─────────────────────────────────────────
    def send_warning_alert(self, project_key: str, summary: str, description: str):
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FFA500",
            "summary": f"WARNING: {project_key}",
            "title": f"⚠️ WARNING — {project_key}",
            "sections": [{
                "facts": [
                    {"name": "Project",     "value": project_key},
                    {"name": "Summary",     "value": summary},
                    {"name": "Description", "value": description},
                    {"name": "Action",      "value": "Review required within 15 minutes"},
                ],
                "markdown": True,
            }],
            "potentialAction": [
                {"@type": "OpenUri", "name": "✅ Create Incident", "targets": [{"os": "default", "uri": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/create?project={project_key}"}]},
                {"@type": "OpenUri", "name": "❌ Dismiss", "targets": [{"os": "default", "uri": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/dismiss?project={project_key}"}]},
            ]
        }
        self._send(card)

    # ── CRITICAL Alert ────────────────────────────────────────
    def send_critical_alert(self, project_key: str, summary: str, description: str, jira_ticket: Optional[str] = None, is_escalation: bool = False):
        title = f"🔴 ESCALATION — {project_key} still AT RISK, no action taken" if is_escalation else f"🔴 CRITICAL — {project_key} Incident Auto-Created"
        jira_url = f"{os.getenv('JIRA_BASE_URL', '')}/browse/{jira_ticket}" if jira_ticket else None

        actions = []
        if jira_url:
            actions.append({"@type": "OpenUri", "name": "🎫 View Jira Ticket", "targets": [{"os": "default", "uri": jira_url}]})
        actions.append({"@type": "OpenUri", "name": "📈 View Dashboard", "targets": [{"os": "default", "uri": os.getenv("APP_URL", "http://localhost:5173")}]})

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000",
            "summary": f"CRITICAL: {project_key}",
            "title": title,
            "sections": [{
                "facts": [
                    {"name": "Project",     "value": project_key},
                    {"name": "Summary",     "value": summary},
                    {"name": "Description", "value": description},
                    {"name": "Jira Ticket", "value": jira_ticket or "Not created"},
                    {"name": "Time",        "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")},
                ],
                "markdown": True,
            }],
            "potentialAction": actions,
        }
        self._send(card)

    # ── Daily summary ─────────────────────────────────────────
    def send_daily_summary(self, projects: list[dict]):
        at_risk = [p for p in projects if p["health"] == "AT RISK"]
        warning = [p for p in projects if p["health"] == "WARNING"]
        healthy = [p for p in projects if p["health"] == "HEALTHY"]

        def fmt(items):
            return ", ".join(p["project_key"] for p in items) if items else "None"

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "0076D7",
            "summary": "Daily Project Health Summary",
            "title": f"📊 Daily Project Health Summary — {datetime.utcnow().strftime('%B %d, %Y')}",
            "sections": [{
                "facts": [
                    {"name": f"🔴 AT RISK ({len(at_risk)})",  "value": fmt(at_risk)},
                    {"name": f"⚠️ WARNING ({len(warning)})",  "value": fmt(warning)},
                    {"name": f"✅ HEALTHY ({len(healthy)})",   "value": fmt(healthy)},
                ],
                "markdown": True,
            }],
            "potentialAction": [{"@type": "OpenUri", "name": "📈 Open Dashboard", "targets": [{"os": "default", "uri": os.getenv("APP_URL", "http://localhost:5173")}]}]
        }
        self._send(card)

    # ── Project health (manual sends) ────────────────────────
    def send_project_health(self, project_name: str, health_status: str, metrics: dict | None = None, rules: dict | None = None, days_back: int = 30):
        color = self._get_color(health_status)
        facts = [
            {"name": "Project",         "value": project_name},
            {"name": "Health Status",   "value": health_status},
            {"name": "Analysis Window", "value": f"Last {days_back} days"},
            {"name": "Timestamp",       "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")},
        ]
        if metrics:
            facts += [
                {"name": "Total Issues",      "value": str(metrics.get("total", 0))},
                {"name": "Done",              "value": f"{metrics.get('done', 0)} ({round(metrics.get('done_ratio', 0)*100,1)}%)"},
                {"name": "In Progress (WIP)", "value": f"{metrics.get('wip', 0)} ({round(metrics.get('wip_ratio', 0)*100,1)}%)"},
                {"name": "Stale Issues",      "value": str(metrics.get("stale_in_progress_count", 0))},
            ]
        sections = [{"facts": facts, "markdown": True}]
        if rules:
            if rules.get("risks"):
                sections.append({"title": "⚠️ Risks", "text": "\n\n".join(f"• {r}" for r in rules["risks"]), "markdown": True})
            if rules.get("actions"):
                sections.append({"title": "✅ Recommended Actions", "text": "\n\n".join(f"• {a}" for a in rules["actions"]), "markdown": True})
        card = {"@type": "MessageCard", "@context": "http://schema.org/extensions", "summary": f"{project_name} health update", "themeColor": color, "title": "📊 Project Health Update", "sections": sections}
        try:
            requests.post(self.webhook_url, json=card, headers={"Content-Type": "application/json"}, timeout=10)
        except Exception as e:
            print(f"[TEAMS] send_project_health failed: {e}")

    @staticmethod
    def _get_color(status: str) -> str:
        s = (status or "").strip().lower()
        if s in ("at_risk", "risk", "at risk"): return "FF0000"
        if s in ("watch", "warning"):           return "FFA500"
        if s in ("healthy",):                   return "00FF00"
        return "0076D7"