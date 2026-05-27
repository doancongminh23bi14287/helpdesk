# backend/tests/test_security.py
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
    token = create_access_token({"sub": "42"})
    claims = decode_token(token)
    assert claims["sub"] == "42"
    assert claims["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token({"sub": "7"})
    claims = decode_token(token)
    assert claims["sub"] == "7"
    assert claims["type"] == "refresh"


def test_access_and_refresh_tokens_have_different_type_claim():
    access = create_access_token({"sub": "1"})
    refresh = create_refresh_token({"sub": "1"})
    assert decode_token(access)["type"] == "access"
    assert decode_token(refresh)["type"] == "refresh"
