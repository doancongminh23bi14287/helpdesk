import os
import random
from urllib.parse import urlparse
from gevent.lock import Semaphore
from gevent.queue import Queue, Empty

from locust import HttpUser, between, events, task
from locust.exception import StopUser

PREFIX = os.getenv("LOAD_TEST_PREFIX", "LOADTEST-")
ALLOWED = os.getenv("ALLOW_LOAD_TEST", "").lower() == "true"
LOAD_TEST_MODE = os.getenv("LOAD_TEST_MODE", "").lower() == "true"
LOAD_TEST_KEY = os.getenv("LOAD_TEST_KEY", "")
CONFIRMED = os.getenv("LOAD_TEST_CONFIRM", "").lower() == "true"
ALLOW_STAGING = os.getenv("LOAD_TEST_ALLOW_STAGING", "").lower() == "true"
ALLOWED_HOSTS = {host.strip().lower() for host in os.getenv("LOAD_TEST_ALLOWED_HOSTS", "").split(",") if host.strip()}
CREATE_TICKETS = os.getenv("LOAD_TEST_CREATE_TICKETS", "").lower() == "true"
BACKEND_SIDE_EFFECTS_DISABLED = (
    os.getenv("LOAD_TEST_BACKEND_SIDE_EFFECTS_DISABLED", "").lower() == "true"
)
SYNTHETIC_EMAIL_VARS = ("LOAD_TEST_CUSTOMER_EMAIL", "LOAD_TEST_STAFF_EMAIL", "LOAD_TEST_ADMIN_EMAIL")
SYNTHETIC_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}
def _account_pool(name):
    result = []
    for raw in os.getenv(name, "").split(","):
        if not raw.strip():
            continue
        fields = [part.strip() for part in raw.split("|")]
        if len(fields) not in (4, 5):
            raise RuntimeError(f"{name} entries must be EMAIL|PASSWORD|USER_ID|ORG_ID|TOKEN")
        result.append({"email": fields[0].lower(), "password": fields[1], "user_id": int(fields[2]), "org_id": int(fields[3]), "token": fields[4] if len(fields) == 5 else ""})
    return result

ACCOUNT_POOLS = {name: _account_pool(name) for name in ("LOAD_TEST_CUSTOMER_ACCOUNTS", "LOAD_TEST_STAFF_ACCOUNTS", "LOAD_TEST_ADMIN_ACCOUNTS")}
ACCOUNT_QUEUES = {name: Queue() for name in ACCOUNT_POOLS}


@events.test_start.add_listener
def require_explicit_confirmation(environment, **_kwargs):
    raw_host = (environment.host or "").strip()
    hostname = (urlparse(raw_host).hostname or "").lower()
    if not ALLOWED or not CONFIRMED or not LOAD_TEST_MODE or not LOAD_TEST_KEY:
        raise RuntimeError(
            "Set ALLOW_LOAD_TEST, LOAD_TEST_CONFIRM, LOAD_TEST_MODE and LOAD_TEST_KEY after backend preflight."
        )
    if not hostname:
        raise RuntimeError("A valid --host is required.")
    if any(marker in hostname for marker in ("railway.app", "production", "prod.")):
        raise RuntimeError("Production-like hosts are always blocked by this harness.")
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if hostname not in local_hosts and not (ALLOW_STAGING and hostname in ALLOWED_HOSTS):
        raise RuntimeError(
            "Only loopback is allowed by default; staging requires LOAD_TEST_ALLOW_STAGING=true "
            "and an exact LOAD_TEST_ALLOWED_HOSTS entry."
        )
    if not PREFIX.startswith("LOADTEST-"):
        raise RuntimeError("LOAD_TEST_PREFIX must start with LOADTEST-.")
    if not os.getenv("LOAD_TEST_ORG_ID"):
        raise RuntimeError("LOAD_TEST_ORG_ID is required for an isolated test organisation.")
    if CREATE_TICKETS and not BACKEND_SIDE_EFFECTS_DISABLED:
        raise RuntimeError(
            "Ticket creation is blocked until the running backend has AI/email/external "
            "side effects disabled and LOAD_TEST_BACKEND_SIDE_EFFECTS_DISABLED=true is set."
        )
    for variable in SYNTHETIC_EMAIL_VARS:
        email = os.getenv(variable, "").lower()
        domain = email.rsplit("@", 1)[-1] if "@" in email else ""
        if domain not in SYNTHETIC_EMAIL_DOMAINS:
            raise RuntimeError(f"{variable} must use a reserved example.com, example.org or example.net address.")
    seen = set()
    for pool_name, accounts in ACCOUNT_POOLS.items():
        if not accounts:
            raise RuntimeError(f"{pool_name} is required; shared persona credentials are not supported.")
        for account in accounts:
            identity = (account["email"], account["user_id"])
            if identity in seen or account["org_id"] != int(os.environ["LOAD_TEST_ORG_ID"]):
                raise RuntimeError("Duplicate or out-of-scope synthetic account identity detected.")
            seen.add(identity)
            ACCOUNT_QUEUES[pool_name].put(account)


class AuthenticatedUser(HttpUser):
    abstract = True
    wait_time = between(1, 5)
    credential_prefix = ""
    account_pool_name = ""

    def on_start(self):
        try:
            account = ACCOUNT_QUEUES[self.account_pool_name].get_nowait()
        except Empty:
            raise RuntimeError(f"No unused account remains in {self.account_pool_name}; refusing token sharing.")
        if account.get("token"):
            self.client.headers.update({"Authorization": f"Bearer {account["token"]}", "X-Load-Test-Key": LOAD_TEST_KEY})
            return
        with self.client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]}, name="/api/auth/login [setup]", catch_response=True) as response:
            if response.status_code != 200:
                response.failure("load-test login failed")
                raise StopUser()
            token = response.json().get("access_token")
            if not token:
                response.failure("load-test login response has no access_token")
                raise StopUser()
        self.client.headers.update({"Authorization": f"Bearer {token}", "X-Load-Test-Key": LOAD_TEST_KEY})

    def ticket_items(self):
        response = self.client.get("/api/tickets", name="/api/tickets")
        if response.status_code != 200:
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else payload.get("items", [])


class CustomerUser(AuthenticatedUser):
    weight = 5
    credential_prefix = "LOAD_TEST_CUSTOMER"
    account_pool_name = "LOAD_TEST_CUSTOMER_ACCOUNTS"

    @task(5)
    def list_tickets(self):
        self.client.get("/api/tickets", name="/api/tickets")

    @task(3)
    def view_ticket(self):
        items = self.ticket_items()
        if items:
            self.client.get(f"/api/tickets/{random.choice(items)['id']}", name="/api/tickets/[id]")

    @task(2)
    def list_invoices(self):
        self.client.get("/api/invoices", name="/api/invoices")

    @task(1)
    def create_marked_ticket(self):
        if not CREATE_TICKETS:
            return
        org_id = os.getenv("LOAD_TEST_ORG_ID")
        service_id = os.getenv("LOAD_TEST_SERVICE_ID")
        if not org_id:
            return
        payload = {
            "org_id": int(org_id),
            "subject": f"{PREFIX} synthetic support request",
            "description": f"{PREFIX} safe isolated test data; may be deleted.",
            "ticket_type": "Question",
            "priority": "Low",
        }
        if service_id:
            payload["service_id"] = int(service_id)
        self.client.post("/api/tickets", json=payload, name="/api/tickets [create]")


class StaffUser(AuthenticatedUser):
    weight = 3
    credential_prefix = "LOAD_TEST_STAFF"
    account_pool_name = "LOAD_TEST_STAFF_ACCOUNTS"

    @task(5)
    def list_scoped_tickets(self):
        self.client.get("/api/tickets", name="/api/tickets")

    @task(4)
    def open_detail(self):
        items = self.ticket_items()
        if items:
            self.client.get(f"/api/tickets/{random.choice(items)['id']}", name="/api/tickets/[id]")

    @task(2)
    def notifications(self):
        self.client.get("/api/notifications", name="/api/notifications")

    @task(1)
    def reply_only_to_marked_ticket(self):
        items = [item for item in self.ticket_items() if str(item.get("subject", "")).startswith(PREFIX)]
        if items:
            ticket = random.choice(items)
            self.client.post(
                f"/api/tickets/{ticket['id']}/replies",
                json={"content": f"{PREFIX} synthetic staff reply", "is_internal": False},
                name="/api/tickets/[id]/replies",
            )


class AdminUser(AuthenticatedUser):
    weight = 1
    credential_prefix = "LOAD_TEST_ADMIN"
    account_pool_name = "LOAD_TEST_ADMIN_ACCOUNTS"

    @task(4)
    def organisations(self):
        self.client.get("/api/organizations", name="/api/organizations")

    @task(3)
    def analytics(self):
        self.client.get("/api/analytics/tickets", name="/api/analytics/tickets")

    @task(2)
    def notifications(self):
        self.client.get("/api/notifications", name="/api/notifications")
