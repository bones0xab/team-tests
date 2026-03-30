# app/routes/metrics.py
# ──────────────────────────────────────────────────────────────
# Exposes /api/metrics for Prometheus to scrape
# ──────────────────────────────────────────────────────────────

import time
from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.metrics.prometheus_metrics import api_requests_total, api_request_duration

router = APIRouter(tags=["Metrics"])


@router.get("/api/metrics", include_in_schema=False)
async def metrics():
    """Prometheus scrape endpoint — do not call manually."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# ──────────────────────────────────────────────────────────────
# Middleware — auto-tracks every request duration + count
# Add this to main.py:
#   app.middleware("http")(track_requests)
# ──────────────────────────────────────────────────────────────

async def track_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    endpoint = request.url.path
    method   = request.method
    status   = str(response.status_code)

    api_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=status
    ).inc()

    api_request_duration.labels(endpoint=endpoint).observe(duration)

    return response