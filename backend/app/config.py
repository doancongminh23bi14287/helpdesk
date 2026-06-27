# backend/app/config.py
import os
import pathlib
import sys
import types
from dotenv import load_dotenv

load_dotenv()

ENV: str = os.getenv("ENV", "development")  # "development" | "test" | "production"

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
DB_URL: str = os.getenv("DB_URL", DATABASE_URL or "")
JWT_SECRET: str = os.getenv("JWT_SECRET", "changeme")
JWT_ALGO: str = os.getenv("JWT_ALGO", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# True when running under pytest (in-process detection only — not overridable via env var).
# Do NOT add _env_bool("TESTING") here: that would allow a production deploy to bypass
# validate_production_config() by setting TESTING=true in the environment.
TESTING: bool = "pytest" in sys.modules

CORS_ORIGINS: list[str] = _split_csv(
    os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8001")
)
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
EMAIL_FEATURES_ENABLED: bool = _env_bool("EMAIL_FEATURES_ENABLED", False)

IMAP_HOST: str = os.getenv("IMAP_HOST", "mail.example.com")
IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER: str = os.getenv("IMAP_USER", "support@example.com")
IMAP_PASS: str = os.getenv("IMAP_PASS", "")

REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
REDIS_AUTH_PREFIX: str = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
REDIS_URL: str = os.getenv("REDIS_URL", f"redis://{REDIS_AUTH_PREFIX}{REDIS_HOST}:{REDIS_PORT}")

SMTP_HOST: str = os.getenv("SMTP_HOST", "mail.example.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
SMTP_USER: str = os.getenv("SMTP_USER", "support@example.com")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")
SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", SMTP_USER)
SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "WorkDesk Support")
ADMIN_NOTIFICATION_EMAIL: str = os.getenv("ADMIN_NOTIFICATION_EMAIL", "admin@example.com")
FILES_ROOT: str = os.getenv("FILES_ROOT", str(pathlib.Path.home() / "helpdesk-system" / "files"))
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
AI_FEATURES_ENABLED: bool = _env_bool("AI_FEATURES_ENABLED", False)
AI_MODEL: str = os.getenv("AI_MODEL", "llama-3.1-8b-instant")

# ── Google Search Console OAuth ───────────────────────────────────────────────
GSC_CLIENT_ID: str = os.getenv("GSC_CLIENT_ID", "")
GSC_CLIENT_SECRET: str = os.getenv("GSC_CLIENT_SECRET", "")
GSC_REDIRECT_URI: str = os.getenv("GSC_REDIRECT_URI", "http://localhost:8001/api/seo/gsc/callback")

RATE_LIMIT_LOGIN: str = os.getenv("RATE_LIMIT_LOGIN", "10/minute")
RATE_LIMIT_REFRESH: str = os.getenv("RATE_LIMIT_REFRESH", "30/minute")
RATE_LIMIT_CHANGE_PASSWORD: str = os.getenv("RATE_LIMIT_CHANGE_PASSWORD", "5/minute")
RATE_LIMIT_TICKET_CREATE: str = os.getenv("RATE_LIMIT_TICKET_CREATE", "20/minute")
RATE_LIMIT_FILE_UPLOAD: str = os.getenv("RATE_LIMIT_FILE_UPLOAD", "10/minute")
RATE_LIMIT_ADMIN_EMAIL_POLL: str = os.getenv("RATE_LIMIT_ADMIN_EMAIL_POLL", "3/minute")
RATE_LIMIT_OTP_VERIFY: str = os.getenv("RATE_LIMIT_OTP_VERIFY", "5/minute")
RATE_LIMIT_OTP_RESET: str = os.getenv("RATE_LIMIT_OTP_RESET", "5/minute")

# Convenience object for callers that prefer attribute-style access.
settings = types.SimpleNamespace(
    ENV=ENV,
    CORS_ORIGINS=CORS_ORIGINS,
    FRONTEND_URL=FRONTEND_URL,
    EMAIL_FEATURES_ENABLED=EMAIL_FEATURES_ENABLED,
    DATABASE_URL=DATABASE_URL,
    DB_URL=DB_URL,
    JWT_SECRET=JWT_SECRET,
    JWT_ALGO=JWT_ALGO,
    ACCESS_TOKEN_EXPIRE_MINUTES=ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS=REFRESH_TOKEN_EXPIRE_DAYS,
    IMAP_HOST=IMAP_HOST, IMAP_PORT=IMAP_PORT,
    IMAP_USER=IMAP_USER, IMAP_PASS=IMAP_PASS,
    REDIS_HOST=REDIS_HOST, REDIS_PORT=REDIS_PORT,
    REDIS_PASSWORD=REDIS_PASSWORD, REDIS_URL=REDIS_URL,
    SMTP_HOST=SMTP_HOST, SMTP_PORT=SMTP_PORT,
    SMTP_USE_SSL=SMTP_USE_SSL, SMTP_USER=SMTP_USER, SMTP_PASS=SMTP_PASS,
    SMTP_FROM_EMAIL=SMTP_FROM_EMAIL,
    SMTP_FROM_NAME=SMTP_FROM_NAME,
    ADMIN_NOTIFICATION_EMAIL=ADMIN_NOTIFICATION_EMAIL,
    FILES_ROOT=FILES_ROOT,
    STORAGE_BACKEND=STORAGE_BACKEND,
    GROQ_API_KEY=GROQ_API_KEY,
    AI_FEATURES_ENABLED=AI_FEATURES_ENABLED,
    AI_MODEL=AI_MODEL,
    GSC_CLIENT_ID=GSC_CLIENT_ID,
    GSC_CLIENT_SECRET=GSC_CLIENT_SECRET,
    GSC_REDIRECT_URI=GSC_REDIRECT_URI,
    RATE_LIMIT_LOGIN=RATE_LIMIT_LOGIN,
    RATE_LIMIT_REFRESH=RATE_LIMIT_REFRESH,
    RATE_LIMIT_CHANGE_PASSWORD=RATE_LIMIT_CHANGE_PASSWORD,
    RATE_LIMIT_TICKET_CREATE=RATE_LIMIT_TICKET_CREATE,
    RATE_LIMIT_FILE_UPLOAD=RATE_LIMIT_FILE_UPLOAD,
    RATE_LIMIT_ADMIN_EMAIL_POLL=RATE_LIMIT_ADMIN_EMAIL_POLL,
    RATE_LIMIT_OTP_VERIFY=RATE_LIMIT_OTP_VERIFY,
    RATE_LIMIT_OTP_RESET=RATE_LIMIT_OTP_RESET,
)


def validate_production_config() -> None:
    """Raise ValueError at process startup if env has insecure or missing config."""
    if TESTING:
        return
    _insecure_defaults = {"changeme", "dev-secret-change-in-production"}
    if not JWT_SECRET or JWT_SECRET in _insecure_defaults:
        raise ValueError(
            "FATAL: JWT_SECRET must be set to a secure value. "
            "Current value is missing or an insecure default."
        )
    if len(JWT_SECRET) < 32:
        raise ValueError(
            "FATAL: JWT_SECRET must be at least 32 characters. "
            f"Current length: {len(JWT_SECRET)}."
        )
    if not DB_URL:
        raise ValueError("FATAL: DB_URL or DATABASE_URL must be set (no localhost fallback).")
    if ENV != "production":
        return
    if not os.getenv("DATABASE_URL") and not os.getenv("DB_URL"):
        raise ValueError("FATAL: DATABASE_URL or DB_URL must be set in production.")
    if "REDIS_URL" not in os.environ and (
        "REDIS_HOST" not in os.environ or "REDIS_PORT" not in os.environ
    ):
        raise ValueError("FATAL: REDIS_URL or REDIS_HOST/REDIS_PORT must be set in production.")
    if "*" in CORS_ORIGINS:
        raise ValueError("FATAL: CORS_ORIGINS must not contain '*' in production.")
    if EMAIL_FEATURES_ENABLED:
        missing = [
            name for name, value in {
                "IMAP_HOST": IMAP_HOST,
                "IMAP_USER": IMAP_USER,
                "IMAP_PASS": IMAP_PASS,
                "SMTP_HOST": SMTP_HOST,
                "SMTP_USER": SMTP_USER,
                "SMTP_PASS": SMTP_PASS,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(
                "FATAL: email features are enabled but missing production config: "
                + ", ".join(missing)
            )
