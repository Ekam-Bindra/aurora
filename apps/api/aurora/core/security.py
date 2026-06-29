"""Password hashing and JWT issuance/verification.

Phase 1 uses a dependency-free PBKDF2-SHA256 hasher (stdlib) behind a small interface so it is
trivially swappable for argon2/bcrypt in hardening (Roadmap Phase 9). JWTs are signed with
HS256; access tokens are short-lived and refresh tokens long-lived, both carrying the tenant
and authorization claims so requests can be authorized statelessly.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from typing import Any, Dict, List, Optional

import jwt

_PBKDF2_ITERATIONS = 200_000
_ALGO_TAG = "pbkdf2_sha256"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, *, iterations: int = _PBKDF2_ITERATIONS) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO_TAG}${iterations}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = encoded.split("$")
        if algo != _ALGO_TAG:
            return False
        expected = _b64decode(hash_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64decode(salt_b64), int(iters)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_token(
    *,
    subject: str,
    token_type: str,
    secret: str,
    ttl_seconds: int,
    algorithm: str = "HS256",
    claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(
    token: str, *, secret: str, algorithms: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Decode a JWT, raising ``jwt.PyJWTError`` subclasses on failure."""
    return jwt.decode(token, secret, algorithms=algorithms or ["HS256"])
