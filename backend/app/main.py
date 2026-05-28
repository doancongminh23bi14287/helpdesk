# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, organizations, users, tickets, admin, notifications

app = FastAPI(title="Helpdesk API", version="1.0.0")

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


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


# Combined ASGI application: socket.io at /socket.io/, FastAPI for everything else
import socketio as _socketio
from app.socketio_server import sio as _sio

application = _socketio.ASGIApp(_sio, other_asgi_app=app)
