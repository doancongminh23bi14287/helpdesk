"""
Customer service — business logic for resolving services and summaries.
"""
from customer_portal.repositories.customer_repository import get_customer_for_user
from customer_portal.repositories import service_repository


def get_services_for_user(user_email: str) -> dict:
    """
    Return the full services payload for the portal UI.
    Resolves the Customer entity from the user's email, then fetches
    hosting plans and subscriptions.
    """
    customer = get_customer_for_user(user_email)
    hosting = service_repository.get_hosting_plans(customer)
    subscriptions = service_repository.get_subscriptions(customer)

    return {
        "customer": customer,
        "hosting": hosting,
        "subscriptions": subscriptions,
    }
