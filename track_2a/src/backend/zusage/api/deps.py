"""Shared FastAPI dependencies. The DB engine, knowledge base and brain are
singletons built at startup (see ``main.create_app``) and stored on app.state."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from ..db import User
from ..engine.brain import Brain
from ..knowledge import Knowledge
from ..security import COOKIE_NAME, read_token


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_kb(request: Request) -> Knowledge:
    return request.app.state.kb


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE_NAME, "")
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    claims = read_token(token, request.app.state.settings.secret_key)
    if not claims:
        raise HTTPException(status_code=401, detail="Session expired - please sign in again")
    user = session.get(User, claims["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    import hashlib

    stamp = claims.get("auth_stamp")
    if not stamp or stamp != hashlib.sha256(user.password_hash.encode()).hexdigest():
        raise HTTPException(401, "Password changed. Sign in again.")
    return user


def teacher_user(user: User = Depends(current_user)) -> User:
    if user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Teachers only")
    return user


def get_brain(request: Request) -> Iterator[Brain]:
    from ..engine.brain import build_brain
    from .workspace import personal_key

    token = request.cookies.get(COOKIE_NAME, "")
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:].strip()
    claims = read_token(token, request.app.state.settings.secret_key) if token else None
    key = personal_key(request, claims["sub"]) if claims else None
    if not key:
        yield request.app.state.brain
        return
    settings = request.app.state.settings.model_copy(update={"llm_api_key": key})
    brain = build_brain(settings)
    try:
        yield brain
    finally:
        if hasattr(brain, "client"):
            brain.client._http.close()
