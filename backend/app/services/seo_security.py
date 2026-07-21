"""Shared guards for Google integration callbacks and provider properties."""
from fastapi import HTTPException

def validate_oauth_owner(stored_org_id: int, stored_user_id: int, provider: str, expected_provider: str, user, db) -> None:
    if provider != expected_provider or not user or not user.is_active or user.id != stored_user_id:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    from app.core.scoping import assert_org_access
    assert_org_access(stored_org_id, user, db)

def validate_gsc_property(property_url: str, sites: list) -> str:
    candidate = property_url.strip().rstrip("/")
    if not candidate or not any((site.get("siteUrl") or "").strip().rstrip("/") == candidate for site in sites):
        raise HTTPException(status_code=404, detail="GSC property is not available to this connection")
    return property_url.strip()

def validate_ga4_property(property_id: str, properties: list) -> tuple[str, str]:
    candidate = property_id.strip().removeprefix("properties/")
    for item in properties:
        provider_id = str(item.get("property", "")).removeprefix("properties/")
        if provider_id == candidate:
            return item.get("property", f"properties/{candidate}"), item.get("displayName", "")
    raise HTTPException(status_code=404, detail="GA4 property is not available to this connection")
