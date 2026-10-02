"""Authentication primitives: Argon2id password hashing, signed session tokens,
and a small login rate limiter.

Sessions are JWTs carried in an HttpOnly, SameSite=Lax cookie for the web
app, and accepted as ``Authorization: Bearer`` for API clients (e.g. an
external LLM-as-judge benchmark harness driving interviews over HTTP).
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Firebase Hosting forwards only this cookie to dynamic backends.
COOKIE_NAME = "__session"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def issue_token(user_id: str, role: str, secret: str, hours: int, password_hash: str = "") -> str:
    now = datetime.now(UTC)
    payload = {"sub": user_id, "role": role, "iat": now, "exp": now + timedelta(hours=hours)}
    if password_hash:
        payload["auth_stamp"] = hashlib.sha256(password_hash.encode()).hexdigest()
    return jwt.encode(payload, secret, algorithm="HS256")


def read_token(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


class RateLimiter:
    """Sliding window: at most ``limit`` attempts per ``window_s`` per key."""

    def __init__(self, limit: int = 10, window_s: int = 300):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True
