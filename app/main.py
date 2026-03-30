# app/main.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv(override=False)
load_dotenv(".env.local", override=True)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db.models_alerts import AlertHistory
from app.services.throttle_service import EscalationService
from app.services.teams_notification_service import TeamsNotificationService
from app.routes import ai, auth, dashboard, export, jira_explorer, snapshots, users, team_scorecard, ws, incident, webhook
from app.routes import metrics


async def escalation_checker():
    """Runs every 60s — auto-escalates WARNING alerts that were never acknowledged."""
    esc = EscalationService()
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
                    AlertHistory.severity == "WARNING",
                    AlertHistory.status == "firing",
                    AlertHistory.acknowledged == False,
                    AlertHistory.fired_at <= cutoff,
                )
                .all()
            )
            for alert in pending:
                project_key = str(alert.project_key)
                if esc.is_pending(project_key):
                    print(f"[ESCALATION] Auto-escalating {project_key} to CRITICAL")
                    notifier.send_critical_alert(
                        project_key=project_key,
                        summary=f"[ESCALATED] {alert.summary}",
                        description="Warning was not acknowledged within 15 minutes.",
                    )
                    alert.severity = "CRITICAL"
                    alert.status = "escalated"
                    db.commit()
                    esc.clear_pending(project_key)
        except Exception as e:
            print(f"[ESCALATION] Error: {e}")
        finally:
            if db is not None:
                db.close()


async def metrics_refresher():
    """
    Runs every 10 minutes. Only fetches projects NOT already in cache.
    Cache hit = instant Prometheus update, no Jira call.
    Cache miss = fetch from Jira with 1s pause to avoid rate limiting.
    """
    from app.services.services import fetch_portfolio_summary, fetch_dashboard_data, _DASHBOARD_CACHE
    from app.metrics.prometheus_metrics import update_project_metrics
    import time

    await asyncio.sleep(60)  # let server settle on startup
    loop = asyncio.get_event_loop()

    while True:
        try:
            print("[METRICS] Starting project metrics refresh...")
            portfolio = await loop.run_in_executor(
                None, lambda: fetch_portfolio_summary(days_back=30)
            )
            await asyncio.sleep(2)
            if not portfolio:
                print("[METRICS] No projects found — skipping")
            else:
                cached_count = 0
                fetched_count = 0
                now = time.time()

                for project in portfolio:
                    project_key = None
                    try:
                        if isinstance(project, dict) and "identity" in project:
                            project_key = project["identity"]["project_key"]
                        elif isinstance(project, dict) and "project_key" in project:
                            project_key = project["project_key"]
                        else:
                            continue

                        cache_key = (project_key, 30)
                        cached = _DASHBOARD_CACHE.get(cache_key)

                        if cached and cached["expires_at"] > now:
                            data = cached["payload"]
                            update_project_metrics(project_key, data["metrics"], data["rules"])
                            cached_count += 1
                        else:
                            data = await loop.run_in_executor(
                                None, lambda k=project_key: fetch_dashboard_data(k, 30)
                            )
                            if data:
                                update_project_metrics(project_key, data["metrics"], data["rules"])
                                fetched_count += 1
                            await asyncio.sleep(1)

                    except Exception as e:
                        print(f"[METRICS] Error refreshing {project_key or 'unknown'}: {e}")

                print(f"[METRICS] Done — {cached_count} from cache, {fetched_count} from Jira. Next run in 10 min.")

        except Exception as e:
            print(f"[METRICS] Top-level error: {e}")

        await asyncio.sleep(600)


async def daily_summary_task():
    """Sends a daily portfolio summary to Teams at 9:00 AM Africa/Casablanca."""
    import pytz
    from app.db.models_alerts import ProjectHealthState

    tz = pytz.timezone("Africa/Casablanca")

    while True:
        now = datetime.now(tz)
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)
        wait_seconds = (target - now).total_seconds()

        print(f"[SUMMARY] Next daily summary in {int(wait_seconds // 3600)}h {int((wait_seconds % 3600) // 60)}m")
        await asyncio.sleep(wait_seconds)

        try:
            db = SessionLocal()
            states = db.query(ProjectHealthState).all()
            projects = [{"project_key": s.project_key, "health": s.health} for s in states]
            db.close()

            if projects:
                notifier = TeamsNotificationService()
                notifier.send_daily_summary(projects)
                print(f"[SUMMARY] Daily summary sent — {len(projects)} projects")
            else:
                print("[SUMMARY] No project health states found — skipping")
        except Exception as e:
            print(f"[SUMMARY] Error sending daily summary: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    from app.db.seed import seed_roles_and_permissions
    seed_roles_and_permissions()
    
    # ── Pre-warm the project cache on startup ──

    escalation_task = asyncio.create_task(escalation_checker())
    metrics_task    = asyncio.create_task(metrics_refresher())
    summary_task    = asyncio.create_task(daily_summary_task())
    yield
    escalation_task.cancel()
    metrics_task.cancel()
    summary_task.cancel()


app = FastAPI(
    title="AI Project Intelligence Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

_extra = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _extra.split(",") if o.strip()]
if not _cors_origins:
    _cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


@app.get("/api/test-route")
def test_route():
    return {"status": "working"}