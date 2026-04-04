from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=False)
load_dotenv(".env.local", override=True)

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.db.models_alerts import AlertHistory
from app.services.alert_service import AlertService
from app.services.throttle_service import EscalationService
from app.services.teams_notification_service import TeamsNotificationService
from app.routes import (
    ai, auth, dashboard, export,
    incident, jira_explorer, metrics,
    snapshots, team_scorecard, users,
    webhook, ws,
)


# ─────────────────────────────────────────────────────────────────────────────
# Background tasks
# ─────────────────────────────────────────────────────────────────────────────

async def escalation_checker() -> None:
    """
    Tourne toutes les 120s.
    Auto-escalade les alertes WARNING non acquittées depuis > 15 min.
    """
    esc      = EscalationService()
    notifier = TeamsNotificationService()

    while True:
        await asyncio.sleep(120)
        db = None
        try:
            db = SessionLocal()
            cutoff = datetime.utcnow() - timedelta(minutes=15)
            pending = (
                db.query(AlertHistory)
                .filter(
                    AlertHistory.severity    == "WARNING",
                    AlertHistory.status      == "firing",
                    AlertHistory.acknowledged == False,  # noqa: E712
                    AlertHistory.fired_at    <= cutoff,
                )
                .all()
            )
            for alert in pending:
                project_key = str(alert.project_key)
                if esc.is_pending(project_key):
                    print(f"[ESCALATION] Auto-escalation {project_key} → CRITICAL")
                    notifier.send_critical_alert(
                        project_key=project_key,
                        summary=f"[ESCALATED] {alert.summary}",
                        description="Warning non acquitté sous 15 minutes.",
                    )
                    alert.severity = "CRITICAL"
                    alert.status   = "escalated"
                    db.commit()
                    esc.clear_pending(project_key)
        except Exception as exc:
            print(f"[ESCALATION] Erreur : {exc}")
        finally:
            if db is not None:
                db.close()


async def metrics_refresher() -> None:
    """
    Tourne toutes les 10 min.
    Met à jour les métriques Prometheus pour chaque projet.
    Cache-first : si le cache est chaud, pas d'appel Jira.
    """
    from app.services.services import (
        _DASHBOARD_CACHE,
        fetch_dashboard_data,
        fetch_portfolio_summary,
    )
    from app.metrics.prometheus_metrics import update_project_metrics
    import time

    await asyncio.sleep(60)   # laisse le serveur démarrer
    loop = asyncio.get_event_loop()

    while True:
        try:
            print("[METRICS] Démarrage du rafraîchissement...")
            portfolio = await loop.run_in_executor(
                None, lambda: fetch_portfolio_summary(days_back=30)
            )
            await asyncio.sleep(2)

            if not portfolio:
                print("[METRICS] Portfolio vide — skip")
            else:
                cached_count  = 0
                fetched_count = 0
                now = time.time()

                for project in portfolio:
                    project_key: str | None = None
                    try:
                        if isinstance(project, dict) and "identity" in project:
                            project_key = project["identity"]["project_key"]
                        elif isinstance(project, dict) and "project_key" in project:
                            project_key = project["project_key"]
                        else:
                            continue

                        cache_key = (project_key, 30)
                        cached    = _DASHBOARD_CACHE.get(cache_key)

                        if cached and cached["expires_at"] > now:
                            update_project_metrics(
                                project_key,
                                cached["payload"]["metrics"],
                                cached["payload"]["rules"],
                            )
                            cached_count += 1
                        else:
                            data = await loop.run_in_executor(
                                None,
                                lambda k=project_key: fetch_dashboard_data(k, 30),
                            )
                            if data:
                                update_project_metrics(
                                    project_key,
                                    data["metrics"],
                                    data["rules"],
                                )
                                fetched_count += 1
                            await asyncio.sleep(1)

                    except Exception as exc:
                        print(f"[METRICS] Erreur {project_key or '?'}: {exc}")

                print(
                    f"[METRICS] Done — {cached_count} cache, "
                    f"{fetched_count} Jira. Prochain dans 10 min."
                )

        except Exception as exc:
            print(f"[METRICS] Erreur globale : {exc}")

        await asyncio.sleep(600)


async def daily_summary_task() -> None:
    """
    Envoie le résumé quotidien Teams à 9h00 (Africa/Casablanca).
    """
    import pytz
    from app.db.models_alerts import ProjectHealthState

    tz = pytz.timezone("Africa/Casablanca")

    while True:
        now    = datetime.now(tz)
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()

        print(
            f"[SUMMARY] Prochain résumé dans "
            f"{int(wait_seconds // 3600)}h "
            f"{int((wait_seconds % 3600) // 60)}m"
        )
        await asyncio.sleep(wait_seconds)

        try:
            db     = SessionLocal()
            states = db.query(ProjectHealthState).all()
            projs  = [{"project_key": s.project_key, "health": s.health} for s in states]
            db.close()

            if projs:
                TeamsNotificationService().send_daily_summary(projs)
                print(f"[SUMMARY] Résumé envoyé — {len(projs)} projets")
            else:
                print("[SUMMARY] Aucun état projet — skip")
        except Exception as exc:
            print(f"[SUMMARY] Erreur : {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[misc]
    Base.metadata.create_all(bind=engine)
    from app.db.seed import seed_roles_and_permissions
    seed_roles_and_permissions()

    escalation_task = asyncio.create_task(escalation_checker())
    metrics_task    = asyncio.create_task(metrics_refresher())
    summary_task    = asyncio.create_task(daily_summary_task())

    yield

    escalation_task.cancel()
    metrics_task.cancel()
    summary_task.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# Application FastAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Project Intelligence Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_extra        = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _extra.split(",") if o.strip()]
if not _cors_origins:
    _cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8081",
        "exp://192.168.1.11:8081",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers métier ────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(ai.router)
app.include_router(snapshots.router)
app.include_router(export.router)
app.include_router(jira_explorer.router)
app.include_router(team_scorecard.router)
app.include_router(ws.router)
app.include_router(incident.router)
app.include_router(webhook.router)
app.include_router(metrics.router)


# ─────────────────────────────────────────────────────────────────────────────
# Router /api/debug  (DOIT être déclaré APRÈS app = FastAPI(...))
# ─────────────────────────────────────────────────────────────────────────────
# ⚠️  ERREUR PRÉCÉDENTE : router était déclaré AVANT app, en dehors de tout
#    contexte FastAPI. Pyright ne pouvait pas résoudre les types → Awaitable.
#    SOLUTION : déclarer router ici, inclure dans app immédiatement après.

_debug_router = APIRouter(prefix="/api/debug", tags=["debug"])

# Instance synchrone (redis.Redis, PAS redis.asyncio.Redis)
_alert_svc = AlertService(
    redis_host=os.getenv("REDIS_HOST", "redis"),
    redis_port=int(os.getenv("REDIS_PORT", "6379")),
)


@_debug_router.get("/redis")
def check_redis_status() -> dict:
    """
    GET /api/debug/redis

    Retourne l'état complet de Redis :
    - Version, mémoire, clients connectés
    - Tous les locks alert_* actifs + leur TTL restant
    - Nombre de clés throttle:* et escalation:*

    Utile pour expliquer à ton équipe pourquoi des alertes ont été envoyées
    ou pourquoi elles ont été bloquées.

    Exemple de réponse :
    {
      "status": "ok",
      "redis_version": "7.0.11",
      "alert_keys": {
        "alert_lock:jira_report": { "value": "locked_at:...", "ttl_seconds": 248 },
        "alert_dedup:jira_report:abc123ef": { "value": "{...}", "ttl_seconds": 548 }
      },
      "total_throttle_keys": 25,
      "escalation_keys_sample": ["escalation:AMALLRUN", ...]
    }
    """
    return _alert_svc.get_redis_status()


@_debug_router.get("/redis/throttle")
def check_throttle_details() -> dict:
    """
    GET /api/debug/redis/throttle

    Retourne le détail de toutes les clés throttle:* et escalation:*.
    Permet de voir le cycle de vie exact de chaque projet.
    """
    return _alert_svc.get_throttle_details()


@_debug_router.delete("/redis/locks")
def clear_all_locks() -> dict:
    """
    DELETE /api/debug/redis/locks

    Supprime tous les locks alert_lock:* actifs.
    À utiliser si une alerte est bloquée par erreur.
    NE supprime PAS les clés throttle ni escalation.
    """
    keys = _alert_svc.redis.keys("alert_lock:*")
    deleted = 0
    for k in keys:
        deleted += _alert_svc.redis.delete(k)
    return {
        "cleared": deleted,
        "keys_cleared": list(keys),
        "message": f"{deleted} lock(s) supprimé(s)",
    }


@_debug_router.delete("/redis/all")
def clear_all_alert_keys() -> dict:
    """
    DELETE /api/debug/redis/all

    Supprime TOUS les locks ET dedups alert_*.
    ⚠️  Utiliser avec précaution — permet un re-envoi immédiat.
    """
    keys = _alert_svc.redis.keys("alert_*")
    deleted = 0
    for k in keys:
        deleted += _alert_svc.redis.delete(k)
    return {
        "cleared": deleted,
        "message": f"{deleted} clé(s) alert_* supprimée(s)",
    }


# ⚠️ IMPORTANT : include_router APRÈS les définitions des endpoints
app.include_router(_debug_router)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints système
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/test-route")
def test_route() -> dict:
    return {"status": "working"}