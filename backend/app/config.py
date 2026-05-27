# backend/app/config.py
import os
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
