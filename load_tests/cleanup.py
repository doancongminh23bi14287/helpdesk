"""Dry-run-first cleanup for records created in the dedicated load-test organisation."""
import argparse
import json
import os
import sys
from urllib.request import Request, urlopen


def request_json(url, token, method="GET", body=None):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, headers=headers, method=method, data=body)
    with urlopen(req, timeout=15) as response:
        return response.status, json.loads(response.read() or b"{}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    base = os.getenv("LOAD_TEST_TARGET", "http://127.0.0.1:8001").rstrip("/")
    token = os.getenv("LOAD_TEST_ADMIN_TOKEN", "")
    org_id = os.getenv("LOAD_TEST_ORG_ID", "")
    prefix = os.getenv("LOAD_TEST_PREFIX", "LOADTEST-")
    if not token or not org_id or not prefix.startswith("LOADTEST-"):
        raise SystemExit("LOAD_TEST_ADMIN_TOKEN, LOAD_TEST_ORG_ID and LOADTEST- prefix are required")
    status, payload = request_json(f"{base}/api/tickets?org_id={int(org_id)}", token)
    if status != 200:
        raise SystemExit(f"ticket listing failed: HTTP {status}")
    items = payload if isinstance(payload, list) else payload.get("items", [])
    ids = sorted(
        int(item["id"]) for item in items
        if str(item.get("subject", "")).startswith(prefix)
    )
    print(json.dumps({"organisation_id": int(org_id), "prefix": prefix, "ticket_count": len(ids), "ticket_ids": ids}))
    if not args.confirm:
        print("DRY RUN: pass --confirm to delete only these ticket IDs")
        return
    for ticket_id in ids:
        request_json(f"{base}/api/tickets/{ticket_id}", token, method="DELETE", body=None)
    print(json.dumps({"deleted_ticket_count": len(ids), "deleted_ticket_ids": ids}))


if __name__ == "__main__":
    main()
