# backend/app/config.py
import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

DB_URL: str = os.getenv("DB_URL", "mysql+pymysql://helpdesk:helpdesk_pass@127.0.0.1:3307/helpdesk_db")
JWT_SECRET: str = os.getenv("JWT_SECRET", "changeme")
JWT_ALGO: str = os.getenv("JWT_ALGO", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

IMAP_HOST: str = os.getenv("IMAP_HOST", "mail.osd.vn")
IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER: str = os.getenv("IMAP_USER", "ticket@osd.vn")
IMAP_PASS: str = os.getenv("IMAP_PASS", "")

REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

SMTP_HOST: str = os.getenv("SMTP_HOST", "mail.osd.vn")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
SMTP_USER: str = os.getenv("SMTP_USER", "ticket@osd.vn")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")
SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "OSD Support")
ADMIN_NOTIFICATION_EMAIL: str = os.getenv("ADMIN_NOTIFICATION_EMAIL", "admin@osd.vn")
FILES_ROOT: str = os.getenv("FILES_ROOT", str(pathlib.Path.home() / "helpdesk-system" / "files"))
