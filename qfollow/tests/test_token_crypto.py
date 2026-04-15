import os
import secrets

import pytest

from scripts import token_crypto


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", secrets.token_bytes(32).hex())


def test_round_trip():
    token = "1//0abcdefgRefreshTokenSample_xyz-123"
    assert token_crypto.decrypt(token_crypto.encrypt(token)) == token


def test_ciphertext_does_not_contain_plaintext():
    token = "supersecret-refresh-token-value"
    blob = token_crypto.encrypt(token)
    assert token not in blob


def test_nonce_uniqueness_same_plaintext():
    token = "same-value"
    assert token_crypto.encrypt(token) != token_crypto.encrypt(token)


def test_tampered_ciphertext_rejected():
    blob = token_crypto.encrypt("hello")
    tampered = blob[:-2] + ("AA" if blob[-2:] != "AA" else "BB")
    with pytest.raises(Exception):
        token_crypto.decrypt(tampered)


def test_wrong_key_rejected(monkeypatch):
    blob = token_crypto.encrypt("hello")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", secrets.token_bytes(32).hex())
    with pytest.raises(Exception):
        token_crypto.decrypt(blob)


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not set"):
        token_crypto.encrypt("x")


def test_wrong_key_length_raises(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "deadbeef")
    with pytest.raises(RuntimeError, match="32 bytes"):
        token_crypto.encrypt("x")
