# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.limiter import limiter
from app.api import auth, organizations, users, tickets, admin, notifications, services, contacts, addresses, items, price_lists, subscription_plans, subscriptions
from app.api import invoices as invoices_module

app = FastAPI(title="Helpdesk API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(price_lists.router)
app.include_router(subscription_plans.router)
app.include_router(subscriptions.router)
app.include_router(invoices_module.router)
app.include_router(invoices_module.admin_router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


# Combined ASGI application: socket.io at /socket.io/, FastAPI for everything else
import socketio as _socketio
from app.socketio_server import sio as _sio

application = _socketio.ASGIApp(_sio, other_asgi_app=app)
