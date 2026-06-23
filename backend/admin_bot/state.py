"""Short-lived FSM state for admin bot multi-step flows (in-process only)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

StateKind = Literal[
    "sstats_key",
    "cache_ttl",
    "rate_limit",
    "sub_price",
    "sub_period",
    "sub_free",
    "sub_retry",
    "sub_cancel_uid",
    "legal_terms_url",
    "legal_privacy_url",
    "legal_disclaimer_url",
    "legal_version",
    "legal_effective_at",
    "legal_broadcast_text",
    "admin_add_tg_id",
    "admin_remove_tg_id",
]

TTL_SEC = 600.0


@dataclass
class UserState:
    kind: StateKind
    expires_at: float


_states: dict[int, UserState] = {}


def set_state(uid: int, kind: StateKind) -> None:
    _states[uid] = UserState(kind=kind, expires_at=time.monotonic() + TTL_SEC)


def get_state(uid: int) -> UserState | None:
    st = _states.get(uid)
    if not st:
        return None
    if time.monotonic() > st.expires_at:
        del _states[uid]
        return None
    return st


def clear_state(uid: int) -> None:
    _states.pop(uid, None)


def prune_expired() -> None:
    now = time.monotonic()
    dead = [u for u, s in _states.items() if now > s.expires_at]
    for u in dead:
        del _states[u]
