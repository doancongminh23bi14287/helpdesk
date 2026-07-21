import pytest
from app.services.seo_security import validate_ga4_property, validate_gsc_property

def test_gsc_property_must_belong_to_provider_account():
    assert validate_gsc_property("https://example.com/", [{"siteUrl": "https://example.com"}]) == "https://example.com/"
    with pytest.raises(Exception):
        validate_gsc_property("https://other.example", [{"siteUrl": "https://example.com"}])

def test_ga4_property_is_canonicalised_and_scoped():
    assert validate_ga4_property("123", [{"property": "properties/123", "displayName": "Site"}]) == ("properties/123", "Site")
    with pytest.raises(Exception):
        validate_ga4_property("999", [{"property": "properties/123"}])
