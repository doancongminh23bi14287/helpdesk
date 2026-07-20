import os
import random

from locust import HttpUser, between, events, task
from locust.exception import StopUser

PREFIX = os.getenv("LOAD_TEST_PREFIX", "[LOADTEST]")
CONFIRMED = os.getenv("LOAD_TEST_CONFIRM", "").lower() == "true"
ALLOW_PRODUCTION = os.getenv("LOAD_TEST_ALLOW_PRODUCTION", "").lower() == "true"
CREATE_TICKETS = os.getenv("LOAD_TEST_CREATE_TICKETS", "").lower() == "true"
INCLUDE_AI = os.getenv("LOAD_TEST_INCLUDE_AI", "").lower() == "true"


@events.test_start.add_listener
def require_explicit_confirmation(environment, **_kwargs):
    host = (environment.host or "").lower()
    if not CONFIRMED:
        raise RuntimeError("Set LOAD_TEST_CONFIRM=true after reviewing the target and test data.")
    looks_production = any(marker in host for marker in ("railway.app", "production", "prod."))
    if looks_production and not ALLOW_PRODUCTION:
        raise RuntimeError("Production-like host blocked without explicit approval.")


class AuthenticatedUser(HttpUser):
    abstract = True
    wait_time = between(1, 5)
    credential_prefix = ""

    def on_start(self):
        email = os.getenv(f"{self.credential_prefix}_EMAIL")
        password = os.getenv(f"{self.credential_prefix}_PASSWORD")
        if not email or not password:
            raise StopUser()
        with self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            name="/api/auth/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure("load-test login failed")
                raise StopUser()
            token = response.json().get("access_token")
            if not token:
                response.failure("login response has no access_token")
                raise StopUser()
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

    @task(1)
    def optional_ai_summary(self):
        if not INCLUDE_AI:
            return
        items = [item for item in self.ticket_items() if str(item.get("subject", "")).startswith(PREFIX)]
        if items:
            self.client.post(
                f"/api/ai/tickets/{random.choice(items)['id']}/summarize",
                name="/api/ai/tickets/[id]/summarize",
            )


class AdminUser(AuthenticatedUser):
    weight = 1
    credential_prefix = "LOAD_TEST_ADMIN"

    @task(4)
    def organisations(self):
        self.client.get("/api/organizations", name="/api/organizations")

    @task(3)
    def analytics(self):
        self.client.get("/api/admin/analytics/overview", name="/api/admin/analytics/overview")

    @task(2)
    def notifications(self):
        self.client.get("/api/notifications", name="/api/notifications")
