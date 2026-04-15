"""AES-256-GCM encryption for OAuth refresh tokens stored in tenants.oauth_token_enc.

Key source: TOKEN_ENCRYPTION_KEY env var — 64 hex chars (32 bytes). Generate with
`openssl rand -hex 32` and store in qfollow/deploy/.env.

Wire format (base64-urlsafe-encoded):  [12-byte nonce][ciphertext+16-byte tag]
"""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12


def _load_key() -> bytes:
    hex_key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if not hex_key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY not set")
    key = bytes.fromhex(hex_key)
    if len(key) != 32:
        raise RuntimeError(f"TOKEN_ENCRYPTION_KEY must decode to 32 bytes, got {len(key)}")
    return key


def encrypt(plaintext: str) -> str:
    key = _load_key()
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt(blob: str) -> str:
    key = _load_key()
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    nonce, ct = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ct, associated_data=None).decode("utf-8")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3 or sys.argv[1] not in {"encrypt", "decrypt"}:
        print("Usage: token_crypto.py {encrypt|decrypt} <value>", file=sys.stderr)
        sys.exit(2)
    fn = encrypt if sys.argv[1] == "encrypt" else decrypt
    print(fn(sys.argv[2]))
