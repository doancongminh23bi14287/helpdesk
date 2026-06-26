# backend/app/core/constants.py
"""
Central registry of business-rule magic numbers.

Keep values here rather than scattered in service/task files so that:
  - thesis defense questions ("why 50%?") have one place to point to
  - changing a value doesn't require a codebase-wide grep
  - tests can import and assert against the canonical constant

Do NOT import heavy app modules here (models, DB) — this file must be
importable before the app is fully configured.
"""

# ── SLA thresholds ────────────────────────────────────────────────────────────
# Percentage of the total resolution window remaining when state changes.
SLA_GREEN_THRESHOLD = 50   # > 50% remaining → green
SLA_AMBER_THRESHOLD = 20   # 20–50% remaining → amber; < 20% → red; ≤ 0 → breached

# Redis dedup TTL: one SLA alert per ticket per state per hour.
SLA_DEDUP_TTL_SECONDS = 3600

# ── Billing cycle discount multipliers ────────────────────────────────────────
QUARTERLY_MONTHS = 3
ANNUAL_MONTHS = 12
QUARTERLY_DISCOUNT = "0.95"   # 5% off for 3-month commitment (Decimal-safe string)
ANNUAL_DISCOUNT = "0.80"      # 20% off for 12-month commitment (Decimal-safe string)

# ── Assignment scoring weights (must sum to 100) ──────────────────────────────
ASSIGN_WORKLOAD_WEIGHT = 40.0
ASSIGN_SKILL_WEIGHT = 40.0    # max points skill can contribute
ASSIGN_ONLINE_WEIGHT = 20.0

# Staff is considered "online" if last_login_at is within this window.
ASSIGN_ONLINE_WINDOW_SECONDS = 1800   # 30 minutes

# Redis lock TTL to prevent double-assignment within one org.
ASSIGN_LOCK_TTL_SECONDS = 10

# ── Skill score — hybrid (historical + baseline) ──────────────────────────────
# skill_score = SKILL_HISTORICAL_WEIGHT × historical_score
#             + SKILL_BASELINE_WEIGHT   × baseline_score
# Both sub-scores are normalised to 0–ASSIGN_SKILL_WEIGHT.
SKILL_HISTORICAL_WEIGHT = 0.7
SKILL_BASELINE_WEIGHT = 0.3
# Each resolved ticket of the same category earns this many skill points.
# 5 matching tickets → 5×8 = 40 = max → historical fully saturates.
HISTORICAL_POINT_PER_TICKET = 8
# Below this threshold the agent is "new"; baseline score decays linearly to 0.
SKILL_COLDSTART_THRESHOLD = 10

# ── File uploads ──────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAGIC_BYTE_READ_SIZE = 2048              # bytes fed to libmagic for MIME detection

# ── OTP / password reset ──────────────────────────────────────────────────────
OTP_LENGTH = 6                 # digits
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5           # failed attempts before OTP is locked
RESET_TOKEN_EXPIRE_MINUTES = 15  # reset token must be shorter than a normal session

# ── AI input ──────────────────────────────────────────────────────────────────
MAX_AI_INPUT_CHARS = 2000   # max chars sent to Groq; prevents prompt stuffing

# ── Pagination ────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20

# ── Ticket lifecycle ──────────────────────────────────────────────────────────
# Resolved tickets are auto-closed after this many days of inactivity.
# (No auto-close task exists yet — documented as a planned feature.)
TICKET_AUTO_CLOSE_DAYS = 3
