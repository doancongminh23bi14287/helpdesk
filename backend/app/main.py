# backend/app/main.py
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.limiter import limiter
from app.core.redis_client import redis_client
from app.core.logging_config import setup_logging
from app.database import get_db
from app.api import auth, organizations, users, tickets, admin, notifications, services, contacts, addresses, items, subscription_plans, subscriptions, projects
from app.api import invoices as invoices_module
from app.api.attachments import router as attachments_router
from app.api.transfer_requests import router as transfer_requests_router
from app.api.staff_assignments import router as staff_assignments_router
from app.api.analytics import router as analytics_router
from app.api.ai import router as ai_router
from app.api.seo_gsc import router as seo_gsc_router
from app.api.seo_ga4 import router as seo_ga4_router
from app.config import settings, validate_production_config

validate_production_config()
setup_logging(env=settings.ENV)

logger = logging.getLogger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)
EMAIL_OUTBOX_PENDING_COUNT = Gauge(
    "email_outbox_pending_count",
    "Number of pending outbound emails.",
)
EMAIL_OUTBOX_FAILED_COUNT = Gauge(
    "email_outbox_failed_count",
    "Number of failed outbound emails.",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.socketio_server import sio as _sio, redis_notification_subscriber
    task = asyncio.create_task(redis_notification_subscriber(_sio))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Helpdesk API", version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a short UUID to every request, log entry/exit, add X-Request-ID header."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()

        _logger = logging.getLogger("api.request")
        _logger.info(
            "%s %s",
            request.method,
            request.url.path,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            _logger.exception(
                "%s %s → 500",
                request.method,
                request.url.path,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            HTTP_REQUESTS_TOTAL.labels(request.method, str(request.url.path), "500").inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(request.method, str(request.url.path)).observe(duration_ms / 1000)
            raise

        duration_ms = (time.perf_counter() - start) * 1000

        _logger.info(
            "%s %s → %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        HTTP_REQUESTS_TOTAL.labels(request.method, str(request.url.path), str(response.status_code)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(request.method, str(request.url.path)).observe(duration_ms / 1000)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)

app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(users.router)
app.include_router(tickets.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(services.router)
app.include_router(contacts.router)
app.include_router(addresses.router)
app.include_router(items.router)
app.include_router(subscription_plans.router)
app.include_router(subscriptions.router)
app.include_router(invoices_module.router)
app.include_router(invoices_module.admin_router)
app.include_router(attachments_router)
app.include_router(transfer_requests_router)
app.include_router(staff_assignments_router)
app.include_router(analytics_router)
app.include_router(ai_router)
app.include_router(seo_gsc_router)
app.include_router(seo_ga4_router)
app.include_router(projects.router)
app.include_router(projects.task_router)


@app.get("/health", tags=["system"])
async def health():
    from datetime import datetime, timezone
    return {
        "status": "ok",
        "service": "CustomerHub API",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }


@app.get("/ready", tags=["system"])
async def ready(db: Session = Depends(get_db)):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text
    from app.models.email_outbox import EmailOutbox

    checks = {}
    overall = "ok"

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        overall = "degraded"

    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
        overall = "degraded"

    try:
        oldest_pending = db.query(EmailOutbox).filter(
            EmailOutbox.status == "pending"
        ).order_by(EmailOutbox.scheduled_at.asc()).first()
        pending_count = db.query(EmailOutbox).filter(
            EmailOutbox.status == "pending"
        ).count()
        stale_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        if oldest_pending and oldest_pending.scheduled_at <= stale_cutoff:
            checks["email_outbox"] = (
                f"warn: {pending_count} pending; oldest pending since "
                f"{oldest_pending.scheduled_at.isoformat()}"
            )
            if overall == "ok":
                overall = "degraded"
        elif pending_count > 50:
            checks["email_outbox"] = f"warn: {pending_count} pending"
            if overall == "ok":
                overall = "degraded"
        else:
            checks["email_outbox"] = f"ok ({pending_count} pending)"
    except Exception as e:
        checks["email_outbox"] = f"error: {e}"
        overall = "degraded"

    if settings.SMTP_PASS:
        checks["smtp_config"] = "ok"
    else:
        checks["smtp_config"] = "error"
        overall = "degraded"

    return JSONResponse(
        status_code=200 if overall == "ok" else 503,
        content={
            "status": overall,
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        },
    )


@app.get("/metrics", tags=["system"])
async def metrics(db: Session = Depends(get_db)):
    from app.models.email_outbox import EmailOutbox

    try:
        EMAIL_OUTBOX_PENDING_COUNT.set(
            db.query(EmailOutbox).filter(EmailOutbox.status == "pending").count()
        )
        EMAIL_OUTBOX_FAILED_COUNT.set(
            db.query(EmailOutbox).filter(EmailOutbox.status == "failed").count()
        )
    except Exception:
        logger.warning("Failed to collect email outbox metrics", exc_info=True)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Combined ASGI application: socket.io at /socket.io/, FastAPI for everything else
import socketio as _socketio
from app.socketio_server import sio as _sio

application = _socketio.ASGIApp(_sio, other_asgi_app=app)
