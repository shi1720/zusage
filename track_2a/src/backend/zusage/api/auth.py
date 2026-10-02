"""Accounts: register, sign in/out, demo sign-in, profile, data rights.

Privacy by design for minors (Swiss FADP / revDSG):
- students sign up with a username - no e-mail, no birth date, no address;
- "export my data" and "delete my account" are one click each (Art. 25/32 FADP);
- teachers only see transcripts of students who opted in (``consent_share``).
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, delete, select

from ..db import Application, Classroom, Drill, Interview, StudentProfile, User, Workspace
from ..security import COOKIE_NAME, RateLimiter, hash_password, issue_token, verify_password
from .deps import current_user, get_session

router = APIRouter(prefix="/api", tags=["auth"])
_login_limiter = RateLimiter(limit=10, window_s=300)
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

DEMO_ACCOUNTS = {"student": "lea", "teacher": "frau.meier"}


class RegisterIn(BaseModel):
    username: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=60)
    role: Literal["student", "teacher"] = "student"
    class_code: str = ""
    ui_lang: Literal["de", "fr", "it", "en"] = "en"


class LoginIn(BaseModel):
    username: str
    password: str


class MeUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=60)
    ui_lang: Literal["de", "fr", "it", "en"] | None = None
    consent_share: bool | None = None
    onboarded: bool | None = None


class StoryIn(BaseModel):
    title: str = Field(default="", max_length=100)
    text: str = Field(max_length=1500)


class ProfileDataIn(BaseModel):
    age: int | None = Field(default=None, ge=10, le=100)
    school: str = Field(default="", max_length=160)
    canton: str = Field(default="", max_length=80)
    hobbies: list[str] = Field(default_factory=list, max_length=20)
    experience: str = Field(default="", max_length=3000)
    strengths: str = Field(default="", max_length=1500)
    stories: list[StoryIn] = Field(default_factory=list, max_length=10)
    target_occupation_id: str = Field(default="", max_length=80)
    interview_language: Literal["de", "fr", "it", "en", "gsw"] = "en"
    persona_id: str = Field(default="warm", max_length=80)


class ProfileIn(BaseModel):
    data: ProfileDataIn


def user_out(user: User, session: Session) -> dict:
    classroom = session.get(Classroom, user.class_id) if user.class_id else None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "ui_lang": user.ui_lang,
        "consent_share": user.consent_share,
        "onboarded": user.onboarded,
        "classroom": {"id": classroom.id, "name": classroom.name, "school": classroom.school} if classroom else None,
    }


def _set_session(response: Response, request: Request, user: User) -> None:
    settings = request.app.state.settings
    token = issue_token(user.id, user.role, settings.secret_key, settings.session_hours, user.password_hash)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_hours * 3600,
        path="/",
    )


@router.post("/auth/register")
def register(body: RegisterIn, request: Request, response: Response, session: Session = Depends(get_session)):
    username = body.username.strip().lower()
    if not _USERNAME.match(username):
        raise HTTPException(422, "Username: 3-32 characters, letters, digits, dot, dash or underscore")
    if session.exec(select(User).where(User.username == username)).first():
        raise HTTPException(409, "This username is taken")
    classroom = None
    if not body.display_name.strip():
        raise HTTPException(422, "Enter a first name or nickname")
    if body.class_code:
        if body.role != "student":
            raise HTTPException(422, "Class codes are for students")
        classroom = session.exec(select(Classroom).where(Classroom.code == body.class_code.strip().upper())).first()
        if not classroom:
            raise HTTPException(404, "Class code not found - check with your teacher")
    user = User(
        username=username,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
        ui_lang=body.ui_lang,
        class_id=classroom.id if classroom else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _set_session(response, request, user)
    return user_out(user, session)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    key = f"{request.client.host if request.client else '?'}:{body.username.lower()}"
    if not _login_limiter.allow(key):
        raise HTTPException(429, "Too many attempts - wait a few minutes")
    user = session.exec(select(User).where(User.username == body.username.strip().lower())).first()
    if (
        request.app.state.settings.isolate_demo
        and user
        and user.username in {"frau.meier", "lea", "noah", "elif", "luca", "chloe", "amar", "mara", "giulia"}
    ):
        raise HTTPException(401, "Use Try as student or Try as teacher to open your private demo")
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Username or password is wrong")
    _set_session(response, request, user)
    return user_out(user, session)


@router.post("/auth/demo/{role}")
def demo_login(
    role: Literal["student", "teacher"], request: Request, response: Response, session: Session = Depends(get_session)
):
    """One-click entry into the seeded demo accounts (judges, school visits).
    Disabled when ZUSAGE_SEED_DEMO=false (production)."""
    if not request.app.state.settings.seed_demo:
        raise HTTPException(404, "Demo accounts are disabled on this server")
    user = session.exec(select(User).where(User.username == DEMO_ACCOUNTS[role])).first()
    if not user:
        raise HTTPException(404, "Demo data not seeded")
    if request.app.state.settings.isolate_demo:
        from ..demo import private_demo

        user = private_demo(session, role)
    _set_session(response, request, user)
    return user_out(user, session)


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return user_out(user, session)


@router.patch("/me")
def update_me(body: MeUpdate, user: User = Depends(current_user), session: Session = Depends(get_session)):
    if body.display_name is not None and not body.display_name.strip():
        raise HTTPException(422, "Display name cannot be blank")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(user, key, value.strip() if isinstance(value, str) else value)
    session.add(user)
    session.commit()
    return user_out(user, session)


@router.post("/me/join-class")
def join_class(body: dict, user: User = Depends(current_user), session: Session = Depends(get_session)):
    if user.role != "student":
        raise HTTPException(403, "Only students can join a class")
    code = str(body.get("code", "")).strip().upper()
    classroom = session.exec(select(Classroom).where(Classroom.code == code)).first()
    if not classroom:
        raise HTTPException(404, "Class code not found")
    if user.class_id != classroom.id:
        user.consent_share = False
    user.class_id = classroom.id
    session.add(user)
    session.commit()
    return user_out(user, session)


@router.post("/me/leave-class")
def leave_class(user: User = Depends(current_user), session: Session = Depends(get_session)):
    user.class_id = None
    user.consent_share = False
    session.add(user)
    session.commit()
    return user_out(user, session)


@router.get("/me/profile")
def get_profile(user: User = Depends(current_user), session: Session = Depends(get_session)):
    profile = session.get(StudentProfile, user.id)
    return {"data": profile.data if profile else {}}


@router.put("/me/profile")
def put_profile(body: ProfileIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    data = body.data.model_dump(exclude_unset=True)
    profile = session.get(StudentProfile, user.id) or StudentProfile(user_id=user.id)
    profile.data = data
    session.add(profile)
    session.commit()
    return {"data": profile.data}


@router.get("/me/export")
def export_data(user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Right of access: everything we store about the user, as JSON."""
    profile = session.get(StudentProfile, user.id)
    workspace = session.get(Workspace, user.id)
    return {
        "workspace": {
            k: v
            for k, v in (workspace.data if workspace else {}).items()
            if k not in ("api_key", "recovery_hash", "push_subscriptions")
        },
        "account": user_out(user, session),
        "profile": profile.data if profile else {},
        "applications": [
            a.model_dump(mode="json") for a in session.exec(select(Application).where(Application.user_id == user.id))
        ],
        "interviews": [
            i.model_dump(mode="json") for i in session.exec(select(Interview).where(Interview.user_id == user.id))
        ],
        "drills": [d.model_dump(mode="json") for d in session.exec(select(Drill).where(Drill.user_id == user.id))],
    }


@router.delete("/me")
def delete_account(response: Response, user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Right to erasure: hard-deletes the account and every row it owns."""
    for model in (Interview, Drill, Application):
        session.exec(delete(model).where(model.user_id == user.id))  # type: ignore[attr-defined]
    session.exec(delete(Workspace).where(Workspace.user_id == user.id))
    session.exec(delete(StudentProfile).where(StudentProfile.user_id == user.id))
    if user.role == "teacher":
        for classroom in session.exec(select(Classroom).where(Classroom.teacher_id == user.id)):
            for student in session.exec(select(User).where(User.class_id == classroom.id)):
                student.class_id = None
                student.consent_share = False
                session.add(student)
            session.delete(classroom)
    session.delete(user)
    session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
