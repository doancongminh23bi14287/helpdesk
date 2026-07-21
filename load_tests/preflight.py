"""Fail-closed preflight for a local/staging CustomerHub load test."""
import os
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def fail(message):
    print(f"PREFLIGHT FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def main():
    target = os.getenv("LOAD_TEST_TARGET", "http://127.0.0.1:8001")
    parsed = urlparse(target)
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        if os.getenv("LOAD_TEST_ALLOW_STAGING", "").lower() != "true":
            fail("target is not loopback and staging was not explicitly allowed")
    if any(marker in host for marker in ("railway.app", "production", "prod.")):
        fail("production-like target is forbidden")
    required = {
        "LOAD_TEST_MODE": "true",
        "ALLOW_LOAD_TEST": "true",
        "AI_ENABLED": "false",
        "EMAIL_SENDING_ENABLED": "false",
        "EMAIL_POLLING_ENABLED": "false",
        "GOOGLE_INTEGRATIONS_ENABLED": "false",
        "PAYMENT_INTEGRATIONS_ENABLED": "false",
        "LOAD_TEST_KEY": None,
        "LOAD_TEST_ORG_ID": None,
        "LOAD_TEST_ADMIN_TOKEN": None,
    }
    for name, expected in required.items():
        value = os.getenv(name, "")
        if expected is not None and value.lower() != expected:
            fail(f"{name} must be {expected!r}")
        if expected is None and not value:
            fail(f"{name} is required")
    try:
        with urlopen(Request(f"{target.rstrip('/')}/health"), timeout=5) as response:
            if response.status != 200:
                fail(f"health check returned HTTP {response.status}")
    except Exception as exc:
        fail(f"health check failed: {type(exc).__name__}")
    print("PREFLIGHT OK: target and side-effect configuration passed")


if __name__ == "__main__":
    main()
