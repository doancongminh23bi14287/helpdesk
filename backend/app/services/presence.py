"""Best-effort Redis-backed presence for assignment decisions.

Presence is intentionally ephemeral. Redis failure must never block ticket
creation or assignment; callers receive an empty/offline result instead.
"""
import logging
import time
from collections.abc import Iterable

from app.config import settings
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

PRESENCE_KEY_PREFIX = "presence:user:"


def _presence_key(user_id: int) -> str:
    return f"{PRESENCE_KEY_PREFIX}{int(user_id)}"


def mark_user_present(user_id: int) -> bool:
    """Refresh a user's presence TTL, returning False on disabled/unavailable Redis."""
    if not settings.PRESENCE_ENABLED:
        return False
    try:
        redis_client.setex(
            _presence_key(user_id),
            settings.PRESENCE_TTL_SECONDS,
            str(int(time.time())),
        )
        return True
    except Exception as exc:
        logger.warning("Presence refresh failed for user_id=%s: %s", user_id, type(exc).__name__)
        return False


def get_present_user_ids(user_ids: Iterable[int]) -> set[int]:
    """Return present IDs with one batched Redis lookup.

    Missing keys and all Redis failures are treated as neutral/offline.
    """
    ids = list(dict.fromkeys(int(user_id) for user_id in user_ids))
    if not ids or not settings.PRESENCE_ENABLED:
        return set()
    try:
        values = redis_client.mget([_presence_key(user_id) for user_id in ids])
    except Exception as exc:
        logger.warning(
            "Presence batch lookup failed candidate_count=%s: %s",
            len(ids),
            type(exc).__name__,
        )
        return set()
    return {user_id for user_id, value in zip(ids, values) if value is not None}


def is_user_present(user_id: int) -> bool:
    """Return whether a heartbeat key currently exists."""
    return int(user_id) in get_present_user_ids([user_id])
