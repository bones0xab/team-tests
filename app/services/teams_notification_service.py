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
            return True
        except Exception as e:
            print(f"[TEAMS] Failed to send notification: {e}")
            return False

    # ── MAIN: Consolidated Portfolio Digest ───────────────────
    def send_consolidated_digest(self, projects: list[dict]):
        """
        Sends ONE executive summary card for all firing projects.
        projects: list of {project_key, severity, summary, stale, wip_pct, total}
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        critical = [p for p in projects if p.get("severity") == "CRITICAL"]
        warning  = [p for p in projects if p.get("severity") == "WARNING"]

        total_stale = sum(p.get("stale") or 0 for p in projects)
        wip_vals    = [p["wip_pct"] for p in projects if p.get("wip_pct") is not None]
        avg_wip     = round(sum(wip_vals) / len(wip_vals), 1) if wip_vals else 0

        # Sort critical by stale issues descending for "most critical" list
        top_critical = sorted(
            [p for p in critical if p.get("stale") is not None],
            key=lambda x: x.get("stale", 0),
            reverse=True
        )[:5]

        # Header color — red if any critical, orange if only warnings
        header_color = "attention" if critical else "warning"

        # Build top issues facts
        top_facts = []
        for p in top_critical:
            stale_str = f"{p['stale']} stale" if p.get("stale") else ""
            wip_str   = f", {p['wip_pct']}% WIP" if p.get("wip_pct") else ""
            top_facts.append({
                "title": p["project_key"],
                "value": f"{stale_str}{wip_str}" or "AT RISK"
            })

        # If no enriched data, just list project keys
        if not top_facts:
            top_facts = [{"title": p["project_key"], "value": "AT RISK"} for p in critical[:5]]

        body = [
            {
                "type": "TextBlock",
                "text": f"🚨 Jira Portfolio Health Report",
                "weight": "Bolder",
                "size": "ExtraLarge",
                "color": header_color,
            },
            {
                "type": "TextBlock",
                "text": now,
                "isSubtle": True,
                "size": "Small",
                "spacing": "None",
            },
            {"type": "Separator"},
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [{
                            "type": "TextBlock",
                            "text": f"🔴 {len(critical)} AT RISK",
                            "weight": "Bolder",
                            "color": "attention",
                            "size": "Large",
                        }]
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [{
                            "type": "TextBlock",
                            "text": f"⚠️ {len(warning)} WARNING",
                            "weight": "Bolder",
                            "color": "warning",
                            "size": "Large",
                        }]
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [{
                            "type": "TextBlock",
                            "text": f"📋 {total_stale:,} stale",
                            "weight": "Bolder",
                            "size": "Large",
                        }]
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [{
                            "type": "TextBlock",
                            "text": f"📊 {avg_wip}% avg WIP",
                            "weight": "Bolder",
                            "size": "Large",
                        }]
                    },
                ]
            },
        ]

        # Most critical projects section
        if top_facts:
            body += [
                {"type": "Separator"},
                {
                    "type": "TextBlock",
                    "text": "Most Critical Projects",
                    "weight": "Bolder",
                    "size": "Medium",
                    "spacing": "Medium",
                },
                {
                    "type": "FactSet",
                    "facts": top_facts,
                }
            ]

        # All AT RISK list if more than 5
        if len(critical) > 5:
            remaining = [p["project_key"] for p in critical[5:]]
            body.append({
                "type": "TextBlock",
                "text": f"Also AT RISK: {', '.join(remaining)}",
                "isSubtle": True,
                "size": "Small",
                "wrap": True,
                "spacing": "Small",
            })

        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "📈 View Dashboard",
                            "url": os.getenv("APP_URL", "http://localhost:5173"),
                            "style": "positive",
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "📊 View Grafana",
                            "url": os.getenv("GRAFANA_URL", "http://localhost:3001"),
                        },
                    ]
                }
            }]
        }
        self._send(card)

    # ── WARNING Alert (kept for escalation use) ───────────────
    def send_warning_alert(self, project_key: str, summary: str, description: str):
        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": "⚠️ WARNING Alert", "weight": "Bolder", "size": "Large", "color": "warning"},
                        {"type": "FactSet", "facts": [
                            {"title": "Project",     "value": project_key},
                            {"title": "Summary",     "value": summary},
                            {"title": "Description", "value": description},
                            {"title": "Action",      "value": "Review required within 15 minutes"},
                        ]}
                    ],
                    "actions": [
                        {"type": "Action.OpenUrl", "title": "✅ Create Incident", "url": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/create?project={project_key}", "style": "positive"},
                        {"type": "Action.OpenUrl", "title": "❌ Dismiss", "url": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/dismiss?project={project_key}", "style": "destructive"},
                    ]
                }
            }]
        }
        self._send(card)

    # ── CRITICAL Alert (kept for escalation use) ──────────────
    def send_critical_alert(self, project_key: str, summary: str, description: str, jira_ticket: Optional[str] = None, is_escalation: bool = False):
        title = "🔴 ESCALATION — Still AT RISK, no action taken" if is_escalation else "🔴 CRITICAL — Incident Auto-Created"
        jira_url = f"{os.getenv('JIRA_BASE_URL', '')}/browse/{jira_ticket}" if jira_ticket else None

        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Large", "color": "attention"},
                        {"type": "FactSet", "facts": [
                            {"title": "Project",     "value": project_key},
                            {"title": "Summary",     "value": summary},
                            {"title": "Description", "value": description},
                            {"title": "Jira Ticket", "value": jira_ticket or "Not created"},
                            {"title": "Time",        "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")},
                        ]}
                    ],
                    "actions": ([{"type": "Action.OpenUrl", "title": "🎫 View Jira Ticket", "url": jira_url}] if jira_url else [])
                }
            }]
        }
        self._send(card)

    # ── Daily summary (scheduled, kept for 9AM digest) ────────
    def send_daily_summary(self, projects: list[dict]):
        at_risk = [p for p in projects if p["health"] == "AT RISK"]
        warning = [p for p in projects if p["health"] == "WARNING"]
        healthy = [p for p in projects if p["health"] == "HEALTHY"]

        def fmt(items):
            return ", ".join(p["project_key"] for p in items) if items else "None"

        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": f"📊 Daily Project Health Summary — {datetime.utcnow().strftime('%B %d, %Y')}", "weight": "Bolder", "size": "Large", "color": "accent"},
                        {"type": "TextBlock", "text": f"Portfolio overview across {len(projects)} active projects.", "isSubtle": True, "spacing": "Small"},
                        {"type": "Separator"},
                        {"type": "FactSet", "facts": [
                            {"title": f"🔴 AT RISK ({len(at_risk)})",  "value": fmt(at_risk)},
                            {"title": f"⚠️ WARNING ({len(warning)})",  "value": fmt(warning)},
                            {"title": f"✅ HEALTHY ({len(healthy)})",   "value": fmt(healthy)},
                        ]},
                    ],
                    "actions": [{"type": "Action.OpenUrl", "title": "📈 Open Dashboard", "url": os.getenv("APP_URL", "http://localhost:5173")}]
                }
            }]
        }
        self._send(card)

    # ── Project health (kept for manual sends) ────────────────
    def send_project_health(self, project_name: str, health_status: str, metrics: dict | None = None, rules: dict | None = None, days_back: int = 30):
        color = self._get_color(health_status)
        facts = [
            {"name": "Project",          "value": project_name},
            {"name": "Health Status",    "value": health_status},
            {"name": "Analysis Window",  "value": f"Last {days_back} days"},
            {"name": "Timestamp",        "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")},
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
        payload = {"@type": "MessageCard", "@context": "http://schema.org/extensions", "summary": f"{project_name} health status update", "themeColor": color, "title": "📊 Project Health Update", "sections": sections}
        try:
            requests.post(self.webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        except Exception as e:
            print(f"[TEAMS] send_project_health failed: {e}")

    @staticmethod
    def _get_color(status: str) -> str:
        s = (status or "").strip().lower()
        if s in ("at_risk", "risk", "at risk"): return "FF0000"
        if s in ("watch", "warning"):           return "FFA500"
        if s in ("healthy",):                   return "00FF00"
        return "0076D7"