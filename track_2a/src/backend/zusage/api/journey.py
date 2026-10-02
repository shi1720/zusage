"""The student's journey: today view, Lehrstellen tracker, drills, progress.

The tracker is the OfferLoop pipeline, re-cut for Swiss apprenticeships:

    interested → schnupper (trial days) → applied → interview → offer | rejected

Every card can launch an interview rehearsal tailored to that exact company
and job ad - practice happens where the real-life stakes are.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from ..db import Application, Drill, Interview, StudentProfile, User, aware, utcnow
from ..engine import core
from ..knowledge import Knowledge
from ..learning import calibration, mastery_timeline, streak_days
from .deps import current_user, get_brain, get_kb, get_session
from .interviews import _candidate, interview_out

router = APIRouter(prefix="/api", tags=["journey"])

STATUSES = ("interested", "schnupper", "applied", "interview", "offer", "rejected")
Status = Literal["interested", "schnupper", "applied", "interview", "offer", "rejected"]
FOLLOW_UP_AFTER_DAYS = 10


class ApplicationIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    occupation_id: str = ""
    title: str = Field(default="", max_length=160)
    town: str = Field(default="", max_length=80)
    posting: str = Field(default="", max_length=6000)
    status: Status = "interested"
    interview_at: datetime | None = None
    contact_name: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=4000)


class ApplicationPatch(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=120)
    occupation_id: str | None = None
    title: str | None = Field(default=None, max_length=160)
    town: str | None = Field(default=None, max_length=80)
    posting: str | None = Field(default=None, max_length=6000)
    status: Status | None = None
    interview_at: datetime | None = None
    contact_name: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)


def app_out(app: Application, session: Session) -> dict:
    practice = session.exec(
        select(Interview).where(Interview.application_id == app.id, Interview.status == "completed")
    ).all()
    best = max((i.overall or 0 for i in practice), default=None)
    return {
        **app.model_dump(mode="json", exclude={"user_id", "deleted_at"}),
        "practice_sessions": len(practice),
        "best_score": best,
    }


def _owned_app(session: Session, user: User, app_id: str) -> Application:
    app = session.get(Application, app_id)
    if not app or app.user_id != user.id or app.deleted_at:
        raise HTTPException(404, "Application not found")
    return app


@router.get("/applications")
def list_applications(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(
        select(Application)
        .where(Application.user_id == user.id, col(Application.deleted_at).is_(None))
        .order_by(col(Application.updated_at).desc())
    ).all()
    return [app_out(a, session) for a in rows]


@router.post("/applications")
def create_application(body: ApplicationIn, user: User = Depends(current_user),
                       session: Session = Depends(get_session)):
    if not body.company.strip():
        raise HTTPException(422, "Company cannot be blank")
    now = utcnow()
    data = body.model_dump()
    data["interview_at"] = aware(data["interview_at"])
    app = Application(user_id=user.id, **data, history=[{"to": body.status, "at": now.isoformat()}])
    session.add(app)
    session.commit()
    session.refresh(app)
    return app_out(app, session)


@router.patch("/applications/{app_id}")
def update_application(app_id: str, body: ApplicationPatch, user: User = Depends(current_user),
                       session: Session = Depends(get_session)):
    app = _owned_app(session, user, app_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None and key != "interview_at" for key, value in changes.items()):
        raise HTTPException(422, "Only the interview date may be cleared")
    if "company" in changes and not changes["company"].strip():
        raise HTTPException(422, "Company cannot be blank")
    if "interview_at" in changes:
        changes["interview_at"] = aware(changes["interview_at"])
    now = utcnow()
    if "status" in changes and changes["status"] != app.status:
        app.history = [*app.history, {"from": app.status, "to": changes["status"], "at": now.isoformat()}]
    for key, value in changes.items():
        setattr(app, key, value)
    app.updated_at = now
    session.add(app)
    session.commit()
    session.refresh(app)
    return app_out(app, session)


@router.delete("/applications/{app_id}")
def delete_application(app_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    app = _owned_app(session, user, app_id)
    app.deleted_at = utcnow()
    session.add(app)
    session.commit()
    return {"ok": True}


@router.post("/applications/{app_id}/restore")
def restore_application(app_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    app = session.get(Application, app_id)
    if not app or app.user_id != user.id:
        raise HTTPException(404, "Application not found")
    app.deleted_at = None
    session.add(app)
    session.commit()
    return app_out(app, session)


# ---------------------------------------------------------------------------
# drills (spaced retrieval practice)
# ---------------------------------------------------------------------------


def drill_out(drill: Drill, kb: Knowledge, lang: str) -> dict:
    q = kb.question(drill.question_id, drill.occupation_id)
    return {
        "id": drill.id,
        "question_id": drill.question_id,
        "question": q.in_lang(lang) if q else drill.question_id,
        "phase": q.phase if q else "",
        "criterion": drill.criterion,
        "box": drill.box,
        "due_at": drill.due_at.isoformat(),
        "due": drill.due_at <= utcnow(),
        "last_score": drill.last_score,
        "best_score": drill.best_score,
        "reps": drill.reps,
        "occupation_id": drill.occupation_id,
    }


def _preferred_lang(session: Session, user: User) -> str:
    profile = session.get(StudentProfile, user.id)
    if profile and profile.data.get("interview_language"):
        return profile.data["interview_language"]
    last = session.exec(
        select(Interview).where(Interview.user_id == user.id).order_by(col(Interview.created_at).desc())
    ).first()
    return last.language if last else user.ui_lang


@router.get("/drills")
def list_drills(user: User = Depends(current_user), session: Session = Depends(get_session),
                kb: Knowledge = Depends(get_kb)):
    lang = _preferred_lang(session, user)
    rows = session.exec(select(Drill).where(Drill.user_id == user.id).order_by(col(Drill.due_at))).all()
    return [drill_out(d, kb, lang) for d in rows]


@router.post("/drills/{drill_id}/start")
def start_drill(drill_id: str, body: dict | None = None, user: User = Depends(current_user),
                session: Session = Depends(get_session), kb: Knowledge = Depends(get_kb), brain=Depends(get_brain)):
    drill = session.get(Drill, drill_id)
    if not drill or drill.user_id != user.id:
        raise HTTPException(404, "Drill not found")
    lang = (body or {}).get("language") or _preferred_lang(session, user)
    occupation_id = drill.occupation_id or next(iter(kb.occupations))
    setup = {
        "language": lang,
        "occupation_id": occupation_id,
        "persona_id": (body or {}).get("persona_id") or "structured",
        "mode": "training",
        "length": "quick",
        "candidate": _candidate(session, user),
    }
    state = core.start(kb, brain, setup, drill_qid=drill.question_id)
    iv = Interview(user_id=user.id, occupation_id=occupation_id, language=lang, persona_id=setup["persona_id"],
                   mode="drill", length="drill", state=state)
    session.add(iv)
    session.commit()
    session.refresh(iv)
    return interview_out(iv, kb)


# ---------------------------------------------------------------------------
# today + progress
# ---------------------------------------------------------------------------


def _criteria_now(interviews: list[Interview]) -> dict[str, float]:
    done = [i for i in interviews if i.status == "completed" and i.report and i.mode != "drill"]
    done.sort(key=lambda i: i.created_at, reverse=True)
    buckets: dict[str, list[float]] = {}
    for iv in done[:3]:
        for crit, value in (iv.report.get("averages") or {}).items():
            buckets.setdefault(crit, []).append(value)
    return {c: round(mean(v), 2) for c, v in buckets.items()}


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), session: Session = Depends(get_session),
              kb: Knowledge = Depends(get_kb)):
    now = utcnow()
    lang = _preferred_lang(session, user)
    interviews = session.exec(select(Interview).where(Interview.user_id == user.id)).all()
    drills = session.exec(select(Drill).where(Drill.user_id == user.id)).all()
    apps = session.exec(
        select(Application).where(Application.user_id == user.id, col(Application.deleted_at).is_(None))
    ).all()

    upcoming = sorted(
        (a for a in apps if a.interview_at and now - timedelta(hours=12) <= a.interview_at <= now + timedelta(days=21)),
        key=lambda a: a.interview_at,  # type: ignore[arg-type,return-value]
    )
    follow_ups = [
        a for a in apps if a.status == "applied" and (now - a.updated_at).days >= FOLLOW_UP_AFTER_DAYS
    ]
    completed = [i for i in interviews if i.status == "completed"]
    active = sorted((i for i in interviews if i.status == "active"), key=lambda i: i.created_at, reverse=True)
    conf = [(i.confidence_before, i.confidence_after) for i in completed
            if i.confidence_before is not None and i.confidence_after is not None]
    criteria = _criteria_now(interviews)
    focus = sorted(criteria, key=criteria.get)[:2] if criteria else []  # type: ignore[arg-type]
    return {
        "due_drills": [drill_out(d, kb, lang) for d in sorted(drills, key=lambda d: d.due_at) if d.due_at <= now],
        "next_drill_at": min((d.due_at for d in drills if d.due_at > now), default=None),
        "upcoming_interviews": [app_out(a, session) for a in upcoming],
        "follow_ups": [app_out(a, session) for a in follow_ups],
        "active_interview": interview_out(active[0], kb) if active else None,
        "stats": {
            "sessions": len(completed),
            "answers": sum(i.answers for i in completed),
            "streak": streak_days(interviews, now),
            "last_overall": next((i.overall for i in sorted(completed, key=lambda i: i.created_at, reverse=True)
                                  if i.overall is not None and i.mode != "drill"), None),
            "confidence_gain": round(mean(b - a for a, b in conf), 2) if conf else None,
            "applications": {s: sum(1 for a in apps if a.status == s) for s in STATUSES},
        },
        "criteria": criteria,
        "focus": focus,
    }


@router.get("/progress")
def progress(user: User = Depends(current_user), session: Session = Depends(get_session),
             kb: Knowledge = Depends(get_kb)):
    interviews = session.exec(select(Interview).where(Interview.user_id == user.id)).all()
    drills = session.exec(select(Drill).where(Drill.user_id == user.id)).all()
    lang = _preferred_lang(session, user)
    return {
        "timeline": mastery_timeline(list(interviews)),
        "criteria_now": _criteria_now(list(interviews)),
        "calibration": calibration(list(interviews)),
        "drills": [drill_out(d, kb, lang) for d in drills],
        "streak": streak_days(list(interviews)),
    }
