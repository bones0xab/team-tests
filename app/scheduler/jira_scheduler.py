from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)

# ─── Singletons ───────────────────────────────────────────────────────────────

# Une seule instance AlertService partagée entre tous les threads
_alert_service = AlertService(
    redis_host=os.getenv("REDIS_HOST", "redis"),
    redis_port=int(os.getenv("REDIS_PORT", "6379")),
)

# Lock Python LOCAL — empêche deux threads du même process de s'exécuter en parallèle
_local_lock = threading.Lock()


# ─── Collecte des données Jira ────────────────────────────────────────────────

def _collect_full_jira_report() -> Optional[Dict[str, Any]]:
    """
    Récupère le portfolio COMPLET depuis l'API interne.

    Au lieu de lancer un thread par projet (ce qui causait N cartes Teams),
    on appelle l'endpoint /api/dashboard/portfolio qui agrège tout.

    Returns None si l'appel échoue.
    """
    # L'API backend tourne sur localhost:8000 dans le même container
    # (ou sur le réseau Docker si appelé depuis un container séparé)
    api_base = os.getenv("INTERNAL_API_BASE", "http://localhost:8000")

    try:
        resp = requests.get(
            f"{api_base}/api/dashboard/portfolio",
            params={"days_back": 30},
            timeout=30,
        )
        resp.raise_for_status()
        portfolio: List[Dict] = resp.json()

    except requests.RequestException as exc:
        logger.error("_collect_full_jira_report — appel API échoué : %s", exc)
        return None

    if not portfolio:
        logger.warning("_collect_full_jira_report — portfolio vide")
        return None

    # ── Calcul des métriques agrégées ────────────────────────────────────────
    at_risk_projects:  List[Dict] = []
    warning_projects:  List[Dict] = []
    total_stale:       int = 0
    wip_ratios:        List[float] = []

    for project in portfolio:
        # Support des deux formats de réponse possibles
        if "identity" in project:
            key    = project["identity"].get("project_key", "?")
            name   = project["identity"].get("project_name", key)
            metrics = project.get("metrics", {})
        else:
            key    = project.get("project_key", "?")
            name   = project.get("project_name", key)
            metrics = project.get("metrics", {})

        health      = project.get("health", "UNKNOWN")
        stale_count = int(metrics.get("stale_issues", 0))
        wip_pct     = float(metrics.get("wip_ratio_pct", 0.0))

        total_stale += stale_count
        if wip_pct > 0:
            wip_ratios.append(wip_pct)

        entry = {
            "key":         key,
            "name":        name,
            "stale_count": stale_count,
            "wip_pct":     wip_pct,
        }

        if health == "AT_RISK" or health == "CRITICAL":
            at_risk_projects.append(entry)
        elif health == "WARNING":
            warning_projects.append(entry)

    # Trier par nombre de stale issues décroissant
    at_risk_projects.sort(key=lambda p: p["stale_count"], reverse=True)
    warning_projects.sort(key=lambda p: p["stale_count"], reverse=True)

    avg_wip = round(sum(wip_ratios) / len(wip_ratios), 1) if wip_ratios else 0.0

    return {
        "at_risk_count":    len(at_risk_projects),
        "warning_count":    len(warning_projects),
        "total_stale":      total_stale,
        "total_projects":   len(portfolio),
        "avg_wip_ratio":    avg_wip,
        "critical_projects": at_risk_projects[:5],   # Top 5 pour la carte Teams
        "generated_at":     datetime.now(timezone.utc).isoformat(),
    }


# ─── Envoi Teams ──────────────────────────────────────────────────────────────

def _send_teams_alert(report_data: Dict[str, Any]) -> bool:
    """
    Envoie la carte Teams avec le rapport de santé Jira.

    Format Adaptive Card (compatible Teams webhook).
    Returns True si envoi réussi, False sinon.
    """
    webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
    if not webhook_url:
        logger.error("_send_teams_alert — TEAMS_WEBHOOK_URL non défini")
        return False

    at_risk_count  = report_data.get("at_risk_count", 0)
    warning_count  = report_data.get("warning_count", 0)
    total_stale    = report_data.get("total_stale", 0)
    total_projects = report_data.get("total_projects", 0)
    avg_wip        = report_data.get("avg_wip_ratio", 0.0)
    critical_list  = report_data.get("critical_projects", [])
    generated_at   = report_data.get("generated_at", "")[:10]   # date seule

    # ── Construire la liste des projets critiques ──────────────────────────
    critical_lines = ""
    for p in critical_list[:5]:
        critical_lines += (
            f"**{p['key']}** — "
            f"{p['stale_count']} stale issues · "
            f"{p['wip_pct']}% WIP\n\n"
        )

    # ── Payload Adaptive Card ─────────────────────────────────────────────
    app_url     = os.getenv("APP_URL", "http://localhost:5173")
    grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3001")

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type":    "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type":   "TextBlock",
                            "text":   f"🚨 Jira Portfolio Health Report — {generated_at}",
                            "weight": "Bolder",
                            "size":   "Medium",
                            "color":  "Attention",
                        },
                        {
                            "type":   "FactSet",
                            "facts": [
                                {"title": "🔴 AT RISK",       "value": str(at_risk_count)},
                                {"title": "⚠️ WARNING",       "value": str(warning_count)},
                                {"title": "📋 Total Stale",   "value": f"{total_stale:,} issues"},
                                {"title": "📊 Avg WIP Ratio", "value": f"{avg_wip}%"},
                                {"title": "📁 Total Projects","value": str(total_projects)},
                                {"title": "🕐 Generated",     "value": generated_at},
                            ],
                        },
                        {
                            "type":   "TextBlock",
                            "text":   "🔥 Most Critical Projects",
                            "weight": "Bolder",
                            "size":   "Small",
                        },
                        {
                            "type": "TextBlock",
                            "text": critical_lines or "None",
                            "wrap": True,
                        },
                    ],
                    "actions": [
                        {
                            "type":  "Action.OpenUrl",
                            "title": "📈 View Dashboard",
                            "url":   app_url,
                        },
                        {
                            "type":  "Action.OpenUrl",
                            "title": "📊 View Grafana",
                            "url":   grafana_url,
                        },
                    ],
                },
            }
        ],
    }

    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        logger.info("✅ Carte Teams envoyée — status=%s", resp.status_code)
        return True
    except requests.RequestException as exc:
        logger.error("❌ Envoi Teams échoué : %s", exc)
        return False


# ─── Point d'entrée principal (appelé par APScheduler) ───────────────────────

def run_jira_health_check() -> None:
    """
    Fonction appelée par APScheduler (ou tout autre scheduler).

    AVANT (cassé) : chaque tick lançait N threads → N cartes Teams différentes.
    APRÈS (corrigé) :
      1. Lock Python local  → 1 seul thread à la fois dans ce process
      2. Redis NX lock       → 1 seul envoi même sur plusieurs workers/replicas
      3. Données agrégées    → 1 seul appel API pour tout le portfolio
    """
    # ── 1. Lock local (non-bloquant) ──────────────────────────────────────
    if not _local_lock.acquire(blocking=False):
        logger.info("⏭️  run_jira_health_check — thread local déjà en cours, skip")
        return

    logger.info("🔄 run_jira_health_check — démarrage collecte portfolio")

    try:
        # ── 2. Collecte complète des données ──────────────────────────────
        report_data = _collect_full_jira_report()
        if report_data is None:
            logger.warning("run_jira_health_check — données vides, abandon")
            return

        # ── 3. Vérification Redis (lock distribué + déduplication contenu) ─
        should_send, reason = _alert_service.should_send_alert(
            "jira_report", report_data
        )
        if not should_send:
            logger.info("⏭️  Alerte Teams skippée : %s", reason)
            return

        # ── 4. Envoi de la carte Teams ─────────────────────────────────────
        success = _send_teams_alert(report_data)

        if success:
            # Enregistre le hash → empêche le prochain doublon
            _alert_service.mark_alert_sent("jira_report", report_data)
            logger.info("✅ run_jira_health_check terminé avec succès")
        else:
            # Libère le lock pour permettre un retry au prochain tick
            _alert_service.release_lock("jira_report")
            logger.error("❌ Envoi échoué — lock libéré pour retry")

    except Exception as exc:
        logger.exception("run_jira_health_check — erreur inattendue : %s", exc)
        # Toujours libérer le lock en cas d'exception
        _alert_service.release_lock("jira_report")

    finally:
        # Libère toujours le lock Python local
        _local_lock.release()