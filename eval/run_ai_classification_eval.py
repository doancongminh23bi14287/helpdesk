#!/usr/bin/env python3
import csv
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "eval" / "ticket_bank.csv"
OUTPUT_CSV = ROOT / "eval" / "ticket_bank_with_model_output.csv"
BACKEND_ENV = ROOT / "backend" / ".env"

API_BASE = "http://localhost:8001"
ORG_ID = 3  # ALOHA-VN from seeded demo data.
TOTAL_EXPECTED = 47


def read_env(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def request_json(method: str, path: str, payload=None, token: str | None = None, timeout: int = 60):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc


def login() -> str:
    env = read_env(BACKEND_ENV)
    candidates = []
    if env.get("SEED_ADMIN_PASSWORD"):
        candidates.append(("ticket@osd.vn", env["SEED_ADMIN_PASSWORD"]))
    candidates.extend([
        ("staff1@osd.vn", "staff123"),
        ("staff2@osd.vn", "staff123"),
    ])
    last_error = None
    for email, password in candidates:
        try:
            result = request_json(
                "POST",
                "/api/auth/login",
                {"email": email, "password": password},
                timeout=30,
            )
            token = result.get("access_token")
            if token:
                print(f"Logged in as {email}")
                return token
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not login with existing test users: {last_error}")


def preflight_ai(token: str) -> None:
    health = request_json("GET", "/api/ai/health", token=token, timeout=30)
    if not health.get("ai_enabled"):
        raise RuntimeError("AI_FEATURES_ENABLED=false; stopping without fake results.")
    if not health.get("groq_configured"):
        raise RuntimeError("GROQ_API_KEY is missing; stopping without fake results.")
    print(f"AI preflight ok: model={health.get('model')}")


def create_ticket(token: str, text: str) -> int:
    subject = "[EVAL] " + text[:50]
    payload = {
        "org_id": ORG_ID,
        "subject": subject,
        "description": text,
        "priority": "Medium",
        "ticket_type": "Question",
        "assignment_mode": "none",
    }
    last_error = None
    for attempt in range(1, 5):
        try:
            result = request_json("POST", "/api/tickets", payload, token=token, timeout=60)
            return int(result["id"])
        except Exception as exc:
            last_error = exc
            if "HTTP 429" in str(exc) and attempt < 4:
                print("  create-ticket rate limit hit; waiting 65s before retry")
                time.sleep(65)
                continue
            raise
    raise RuntimeError(str(last_error))


def classify_ticket(token: str, ticket_id: int) -> tuple[str, str]:
    last_error = None
    for attempt in range(1, 4):
        try:
            result = request_json(
                "POST",
                f"/api/ai/tickets/{ticket_id}/classify",
                token=token,
                timeout=120,
            )
            return result["predicted_category"], result["predicted_priority"]
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                sleep_s = 2 * attempt
                print(f"  classify retry {attempt}/2 after error: {exc}")
                time.sleep(sleep_s)
    raise RuntimeError(str(last_error))


def write_output(rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "ticket_id",
        "ticket_text",
        "rater1_category",
        "rater1_priority",
        "rater2_category",
        "rater2_priority",
        "model_category",
        "model_priority",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = list(csv.DictReader(INPUT_CSV.open(encoding="utf-8")))
    if len(rows) != TOTAL_EXPECTED:
        raise RuntimeError(f"Expected {TOTAL_EXPECTED} tickets, found {len(rows)}")
    for row in rows:
        for key in ("rater1_category", "rater1_priority", "rater2_category", "rater2_priority"):
            if row.get(key):
                raise RuntimeError(f"{key} is not empty for {row.get('ticket_id')}; refusing to continue")

    token = login()
    preflight_ai(token)

    created = []
    failures = []
    success = 0

    for idx, row in enumerate(rows, 1):
        eval_id = row["ticket_id"]
        text = row["ticket_text"]
        print(f"[{idx:02d}/{len(rows)}] {eval_id}: creating ticket")
        try:
            real_ticket_id = create_ticket(token, text)
            created.append((eval_id, real_ticket_id, "[EVAL] " + text[:50]))
            print(f"  created DB ticket #{real_ticket_id}; classifying")
            category, priority = classify_ticket(token, real_ticket_id)
            row["model_category"] = category
            row["model_priority"] = priority
            success += 1
            print(f"  ok: {category}/{priority}")
        except Exception as exc:
            failures.append((eval_id, str(exc)))
            print(f"  FAILED: {exc}")
        finally:
            write_output(rows)

    print("\nSUMMARY")
    print(f"classified_success={success}/{len(rows)}")
    print("failed_ticket_ids=" + (", ".join(f"{tid}: {reason}" for tid, reason in failures) if failures else "none"))
    print("created_eval_tickets:")
    for eval_id, real_ticket_id, subject in created:
        print(f"- {eval_id}: db_ticket_id={real_ticket_id}, subject={subject}")
    print(f"output_csv={OUTPUT_CSV}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
