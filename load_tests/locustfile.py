import os
import random
from urllib.parse import urlparse
from gevent.lock import Semaphore

from locust import HttpUser, between, events, task
from locust.exception import StopUser

PREFIX = os.getenv("LOAD_TEST_PREFIX", "LOADTEST-")
ALLOWED = os.getenv("ALLOW_LOAD_TEST", "").lower() == "true"
CONFIRMED = os.getenv("LOAD_TEST_CONFIRM", "").lower() == "true"
ALLOW_STAGING = os.getenv("LOAD_TEST_ALLOW_STAGING", "").lower() == "true"
ALLOWED_HOSTS = {host.strip().lower() for host in os.getenv("LOAD_TEST_ALLOWED_HOSTS", "").split(",") if host.strip()}
CREATE_TICKETS = os.getenv("LOAD_TEST_CREATE_TICKETS", "").lower() == "true"
BACKEND_SIDE_EFFECTS_DISABLED = (
    os.getenv("LOAD_TEST_BACKEND_SIDE_EFFECTS_DISABLED", "").lower() == "true"
)
SYNTHETIC_EMAIL_VARS = ("LOAD_TEST_CUSTOMER_EMAIL", "LOAD_TEST_STAFF_EMAIL", "LOAD_TEST_ADMIN_EMAIL")
SYNTHETIC_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}
PERSONA_TOKENS = {}
PERSONA_LOCKS = {name: Semaphore(1) for name in SYNTHETIC_EMAIL_VARS}


@events.test_start.add_listener
def require_explicit_confirmation(environment, **_kwargs):
    raw_host = (environment.host or "").strip()
    hostname = (urlparse(raw_host).hostname or "").lower()
    if not ALLOWED or not CONFIRMED:
        raise RuntimeError(
            "Set both ALLOW_LOAD_TEST=true and LOAD_TEST_CONFIRM=true after reviewing the target."
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


class AuthenticatedUser(HttpUser):
    abstract = True
    wait_time = between(1, 5)
    credential_prefix = ""

    def on_start(self):
        email_key = f"{self.credential_prefix}_EMAIL"
        email = os.getenv(email_key)
        password = os.getenv(f"{self.credential_prefix}_PASSWORD")
        if not email or not password:
            raise StopUser()
        with PERSONA_LOCKS[email_key]:
            token = PERSONA_TOKENS.get(email_key)
            if token is None:
                with self.client.post(
                    "/api/auth/login",
                    json={"email": email, "password": password},
                    name="/api/auth/login [setup]",
                    catch_response=True,
                ) as response:
                    if response.status_code != 200:
                        response.failure("load-test login failed")
                        raise StopUser()
                    token = response.json().get("access_token")
                    if not token:
                        response.failure("login response has no access_token")
                        raise StopUser()
                    PERSONA_TOKENS[email_key] = token
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    def ticket_items(self):
        response = self.client.get("/api/tickets", name="/api/tickets")
        if response.status_code != 200:
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else payload.get("items", [])


class CustomerUser(AuthenticatedUser):
    weight = 5
    credential_prefix = "LOAD_TEST_CUSTOMER"

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

    @task(4)
    def organisations(self):
        self.client.get("/api/organizations", name="/api/organizations")

    @task(3)
    def analytics(self):
        self.client.get("/api/analytics/tickets", name="/api/analytics/tickets")

    @task(2)
    def notifications(self):
        self.client.get("/api/notifications", name="/api/notifications")
