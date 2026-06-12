import pytest

from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)


def test_hash_and_verify_correct_password():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_wrong_password_returns_false():
    hashed = hash_password("mysecret")
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip():
    token, jti = create_access_token(42, "customer")
    claims = decode_token(token)
    assert claims["sub"] == "42"
    assert claims["role"] == "customer"
    assert claims["jti"] == jti
    assert claims["type"] == "access"


def test_refresh_token_is_opaque_not_jwt():
    token = create_refresh_token(7)
    assert isinstance(token, str)
    assert len(token) >= 32
    with pytest.raises(Exception):
        decode_token(token)


def test_access_token_has_type_and_refresh_token_is_not_decodable():
    access, _ = create_access_token(1, "admin")
    refresh = create_refresh_token(1)
    assert decode_token(access)["type"] == "access"
    with pytest.raises(Exception):
        decode_token(refresh)
