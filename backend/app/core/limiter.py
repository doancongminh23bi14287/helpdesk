import hmac

from slowapi import Limiter
from slowapi.util import get_remote_address

from app import config


def _load_test_key(request):
    """Use a per-user limiter bucket only for an authenticated dedicated test user."""
    if not config.LOAD_TEST_MODE or not config.ALLOW_LOAD_TEST:
        return get_remote_address(request)
    supplied = request.headers.get("X-Load-Test-Key", "")
    if not config.LOAD_TEST_KEY or not hmac.compare_digest(
        supplied, config.LOAD_TEST_KEY
    ):
        return get_remote_address(request)
    try:
        authorization = request.headers.get("Authorization", "")
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            return get_remote_address(request)
        from app.core.security import decode_token
        from app.database import SessionLocal
        from app.models.team import StaffOrgAssignment
        from app.models.user import User
        payload = decode_token(token)
        user_id = int(payload["sub"])
        with SessionLocal() as db:
            user = db.query(User).filter(
                User.id == user_id,
                User.is_active.is_(True),
            ).first()
            if not user:
                return get_remote_address(request)
            allowed = user.org_id == config.LOAD_TEST_ORG_ID
            if not allowed and user.role == "staff":
                allowed = db.query(StaffOrgAssignment.id).filter(
                    StaffOrgAssignment.user_id == user.id,
                    StaffOrgAssignment.org_id == config.LOAD_TEST_ORG_ID,
                ).first() is not None
            return f"load-test:{user.id}" if allowed else get_remote_address(request)
    except Exception:
        return get_remote_address(request)


limiter = Limiter(key_func=_load_test_key, default_limits=["60/minute"])
