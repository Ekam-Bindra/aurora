"""In-memory OIDC state/nonce store for the authorization code flow."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class OidcState:
    nonce: str
    created_at: float


_store: Dict[str, OidcState] = {}
_TTL_SECONDS = 600


def create_state() -> tuple[str, str]:
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    _store[state] = OidcState(nonce=nonce, created_at=time.time())
    _purge_expired()
    return state, nonce


def pop_state(state: str) -> Optional[str]:
    entry = _store.pop(state, None)
    if entry is None:
        return None
    if time.time() - entry.created_at > _TTL_SECONDS:
        return None
    return entry.nonce


def _purge_expired() -> None:
    now = time.time()
    expired = [key for key, val in _store.items() if now - val.created_at > _TTL_SECONDS]
    for key in expired:
        _store.pop(key, None)
