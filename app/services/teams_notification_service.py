# app/services/teams_notification_service.py
import os
import time
import requests
from typing import Optional
from datetime import datetime

import logging
logger = logging.getLogger(__name__)


class TeamsNotificationService:

    def __init__(self) -> None:
        self.webhook_url: str = os.getenv("TEAMS_WEBHOOK_URL") or ""

    def _send(self, card: dict) -> bool:
        if not self.webhook_url or self.webhook_url == "disabled":
            logger.warning("[TEAMS] Webhook not configured — skipping")
            return False
        for attempt in range(3):
            try:
                response = requests.post(self.webhook_url, json=card, timeout=10)
                response.raise_for_status()
                logger.info(f"[TEAMS] Sent successfully — status {response.status_code}")
                return True
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"[TEAMS] Attempt {attempt+1} failed: {e} — retrying in {wait}s")
                time.sleep(wait)
        logger.error("[TEAMS] All 3 attempts failed")
        return False

    # ── MAIN: Consolidated Portfolio Digest ───────────────────
    def send_consolidated_digest(self, projects: list[dict]) -> None:
        now = datetime.utcnow().strftime("%Y-%m-%d · %H:%M UTC")
        critical = [p for p in projects if p.get("severity") == "CRITICAL"]
        warning  = [p for p in projects if p.get("severity") == "WARNING"]
        color    = "C0392B" if critical else "E67E22"
        sections = []

        # Header summary
        sections.append({
            "activityTitle": "**Portfolio Health Report**",
            "activitySubtitle": now,
            "facts": [
                {"name": "🔴 At risk",      "value": f"**{len(critical)}**"},
                {"name": "⚠️ Warning",     "value": f"**{len(warning)}**"},
                {"name": "📋 Total stale", "value": str(sum(p.get("stale", 0) or 0 for p in projects))},
                {"name": "📁 Projects",    "value": str(len(projects))},
            ],
            "markdown": True,
        })

        # Per-project section
        for p in sorted(projects, key=lambda x: 0 if x.get("severity") == "CRITICAL" else 1):
            sev   = p.get("severity", "UNKNOWN")
            icon  = "🔴" if sev == "CRITICAL" else "⚠️"
            label = "Critical" if sev == "CRITICAL" else "Warning"

            parts = [
                f"Total **{p.get('total', '—')}**",
                f"Stale **{p.get('stale', '—')}**",
                f"WIP **{p.get('wip_pct', '—')}%**",
            ]
            if p.get("done_pct") is not None:
                parts.append(f"Done **{p['done_pct']}%**")
            metrics_line = "  ·  ".join(parts)

            risks   = self._risks(p)
            actions = self._actions(p)

            risks_text   = "\n\n".join(f"● {r}" for r in risks)   if risks   else "None identified"
            actions_text = "\n\n".join(f"● {a}" for a in actions) if actions else "No actions required"

            facts = [{"name": "Metrics", "value": metrics_line}]

            if p.get("jira_ticket"):
                url = f"{os.getenv('JIRA_BASE_URL', '')}/browse/{p['jira_ticket']}"
                facts.append({"name": "Jira", "value": f"[{p['jira_ticket']}]({url})"})

            sections.append({
                "activityTitle": f"{icon} **{p['project_key']}** — {label}",
                "facts": facts,
                "text": f"**RISKS**\n\n{risks_text}\n\n---\n\n**RECOMMENDED ACTIONS**\n\n{actions_text}",
                "markdown": True,
            })

        # Buttons
        sections.append({
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View Dashboard",
                    "targets": [{"os": "default", "uri": os.getenv("APP_URL", "http://localhost:5173/dashboard")}],
                },
                {
                    "@type": "OpenUri",
                    "name": "View Grafana",
                    "targets": [{"os": "default", "uri": os.getenv("GRAFANA_URL", "http://localhost:3001")}],
                },
            ]
        })

        self._send({
            "@type":      "MessageCard",
            "@context":   "http://schema.org/extensions",
            "themeColor": color,
            "summary":    f"Portfolio Health — {len(critical)} Critical, {len(warning)} Warning",
            "sections":   sections,
        })

    @staticmethod
    def _risks(p: dict) -> list[str]:
        out, stale, wip = [], p.get("stale", 0) or 0, p.get("wip_pct", 0) or 0
        if stale > 50:
            out.append("Large share of WIP is stale — indicates blockers or review bottleneck.")
        if wip > 30:
            out.append("WIP concentration is moderate — dependency risk may be forming.")
        if stale > 0 and wip < 5:
            out.append("Unassigned in-progress work has unclear ownership and often stalls.")
        if not out and stale > 0:
            out.append("Stale issues accumulating — monitor before escalating to critical.")
        return out

    @staticmethod
    def _actions(p: dict) -> list[str]:
        out, stale = [], p.get("stale", 0) or 0
        if stale > 0:
            out.append("Review aging WIP — identify and unblock the oldest items first.")
            out.append("Assign owners to all in-progress tickets and clarify next steps.")
        if (p.get("wip_pct") or 0) > 30:
            out.append("Balance ownership — redistribute active items to reduce single-point dependency.")
        return out

    # ── WARNING Alert ─────────────────────────────────────────
    def send_warning_alert(self, project_key: str, summary: str, description: str) -> None:
        card = {
            "@type":      "MessageCard",
            "@context":   "http://schema.org/extensions",
            "themeColor": "FFA500",
            "summary":    f"WARNING: {project_key}",
            "title":      f"WARNING — {project_key}",
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
                {
                    "@type": "OpenUri",
                    "name":  "Create Incident",
                    "targets": [{"os": "default", "uri": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/create?project={project_key}"}],
                },
                {
                    "@type": "OpenUri",
                    "name":  "Dismiss",
                    "targets": [{"os": "default", "uri": f"{os.getenv('APP_URL', 'http://localhost:8000')}/api/incident/dismiss?project={project_key}"}],
                },
            ],
        }
        self._send(card)

    # ── CRITICAL Alert ────────────────────────────────────────
    def send_critical_alert(
        self,
        project_key:   str,
        summary:       str,
        description:   str,
        jira_ticket:   Optional[str] = None,
        is_escalation: bool = False,
    ) -> None:
        title = (
            f"ESCALATION — {project_key} still AT RISK, no action taken"
            if is_escalation else
            f"CRITICAL — {project_key} Incident Auto-Created"
        )
        jira_url = f"{os.getenv('JIRA_BASE_URL', '')}/browse/{jira_ticket}" if jira_ticket else None
        actions: list[dict] = []
        if jira_url:
            actions.append({
                "@type": "OpenUri",
                "name":  "View Jira Ticket",
                "targets": [{"os": "default", "uri": jira_url}],
            })
        actions.append({
            "@type": "OpenUri",
            "name":  "View Dashboard",
            "targets": [{"os": "default", "uri": os.getenv("APP_URL", "http://localhost:5173")}],
        })

        card = {
            "@type":      "MessageCard",
            "@context":   "http://schema.org/extensions",
            "themeColor": "FF0000",
            "summary":    f"CRITICAL: {project_key}",
            "title":      title,
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

    # ── Daily Summary ─────────────────────────────────────────
    def send_daily_summary(self, projects: list[dict]) -> None:
        at_risk = [p for p in projects if p["health"] == "AT RISK"]
        warning = [p for p in projects if p["health"] == "WARNING"]
        healthy = [p for p in projects if p["health"] == "HEALTHY"]

        def fmt(items: list[dict]) -> str:
            return ", ".join(p["project_key"] for p in items) if items else "None"

        card = {
            "@type":      "MessageCard",
            "@context":   "http://schema.org/extensions",
            "themeColor": "0076D7",
            "summary":    "Daily Project Health Summary",
            "title":      f"Daily Project Health Summary — {datetime.utcnow().strftime('%B %d, %Y')}",
            "sections": [{
                "facts": [
                    {"name": f"AT RISK ({len(at_risk)})", "value": fmt(at_risk)},
                    {"name": f"WARNING ({len(warning)})", "value": fmt(warning)},
                    {"name": f"HEALTHY ({len(healthy)})", "value": fmt(healthy)},
                ],
                "markdown": True,
            }],
            "potentialAction": [{
                "@type": "OpenUri",
                "name":  "Open Dashboard",
                "targets": [{"os": "default", "uri": os.getenv("APP_URL", "http://localhost:5173")}],
            }],
        }
        self._send(card)

    # ── Project Health (manual sends) ─────────────────────────
    def send_project_health(
        self,
        project_name:  str,
        health_status: str,
        metrics:       dict | None = None,
        rules:         dict | None = None,
        days_back:     int = 30,
    ) -> None:
        color = self._get_color(health_status)
        facts: list[dict] = [
            {"name": "Project",         "value": project_name},
            {"name": "Health Status",   "value": health_status},
            {"name": "Analysis Window", "value": f"Last {days_back} days"},
            {"name": "Timestamp",       "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")},
        ]
        if metrics:
            facts += [
                {"name": "Total Issues",      "value": str(metrics.get("total", 0))},
                {"name": "Done",              "value": f"{metrics.get('done', 0)} ({round(metrics.get('done_ratio', 0) * 100, 1)}%)"},
                {"name": "In Progress (WIP)", "value": f"{metrics.get('wip', 0)} ({round(metrics.get('wip_ratio', 0) * 100, 1)}%)"},
                {"name": "Stale Issues",      "value": str(metrics.get("stale_in_progress_count", 0))},
            ]
        sections: list[dict] = [{"facts": facts, "markdown": True}]
        if rules:
            if rules.get("risks"):
                sections.append({
                    "title":    "Risks",
                    "text":     "\n\n".join(f"- {r}" for r in rules["risks"]),
                    "markdown": True,
                })
            if rules.get("actions"):
                sections.append({
                    "title":    "Recommended Actions",
                    "text":     "\n\n".join(f"- {a}" for a in rules["actions"]),
                    "markdown": True,
                })

        card = {
            "@type":      "MessageCard",
            "@context":   "http://schema.org/extensions",
            "summary":    f"{project_name} health update",
            "themeColor": color,
            "title":      "Project Health Update",
            "sections":   sections,
        }
        self._send(card)

    @staticmethod
    def _get_color(status: str) -> str:
        s = (status or "").strip().lower()
        if s in ("at_risk", "risk", "at risk"):
            return "FF0000"
        if s in ("watch", "warning"):
            return "FFA500"
        if s in ("healthy",):
            return "00FF00"
        return "0076D7"