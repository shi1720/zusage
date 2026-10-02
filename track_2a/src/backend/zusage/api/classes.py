"""Teacher cockpit: one class, at a glance.

A Sek-I teacher running the "Berufliche Orientierung" module (Lehrplan 21)
cannot run 24 mock interviews per week - but they CAN see who practised,
which criteria the class struggles with, who is losing confidence, and
whose application pipeline has stalled. That is what this API serves.

Privacy: aggregates (scores, counts) are visible for every class member;
transcripts only for students who switched on ``consent_share``.
"""

from __future__ import annotations

from datetime import timedelta
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from ..db import Application, Classroom, Interview, User, join_code, utcnow
from ..knowledge import CRITERIA, Knowledge
from ..learning import mastery_timeline
from .deps import get_kb, get_session, teacher_user
from .interviews import interview_out
from .journey import STATUSES

router = APIRouter(prefix="/api/classes", tags=["classes"])
INACTIVE_DAYS = 14


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    school: str = Field(default="", max_length=120)


def _owned_class(session: Session, teacher: User, class_id: str) -> Classroom:
    classroom = session.get(Classroom, class_id)
    if not classroom or (classroom.teacher_id != teacher.id and teacher.role != "admin"):
        raise HTTPException(404, "Class not found")
    return classroom


@router.get("")
def list_classes(teacher: User = Depends(teacher_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Classroom).where(Classroom.teacher_id == teacher.id)).all()
    out = []
    for c in rows:
        students = session.exec(select(User).where(User.class_id == c.id)).all()
        out.append({"id": c.id, "name": c.name, "school": c.school, "code": c.code, "students": len(students)})
    return out


@router.post("")
def create_class(body: ClassIn, teacher: User = Depends(teacher_user), session: Session = Depends(get_session)):
    classroom = Classroom(name=body.name.strip(), school=body.school.strip(), teacher_id=teacher.id)
    session.add(classroom)
    session.commit()
    session.refresh(classroom)
    return {"id": classroom.id, "name": classroom.name, "school": classroom.school, "code": classroom.code,
            "students": 0}


@router.post("/{class_id}/new-code")
def regenerate_code(class_id: str, teacher: User = Depends(teacher_user), session: Session = Depends(get_session)):
    classroom = _owned_class(session, teacher, class_id)
    classroom.code = join_code()
    session.add(classroom)
    session.commit()
    return {"code": classroom.code}


@router.get("/{class_id}")
def class_overview(class_id: str, teacher: User = Depends(teacher_user), session: Session = Depends(get_session),
                   kb: Knowledge = Depends(get_kb)):
    classroom = _owned_class(session, teacher, class_id)
    now = utcnow()
    students = session.exec(select(User).where(User.class_id == classroom.id).order_by(User.display_name)).all()
    ids = [s.id for s in students]
    interviews = session.exec(select(Interview).where(col(Interview.user_id).in_(ids))).all() if ids else []
    apps = session.exec(
        select(Application).where(col(Application.user_id).in_(ids), col(Application.deleted_at).is_(None))
    ).all() if ids else []

    rows = []
    class_buckets: dict[str, list[float]] = {c: [] for c in CRITERIA}
    weekly: dict[str, int] = {}
    for student in students:
        mine = [i for i in interviews if i.user_id == student.id]
        done = sorted((i for i in mine if i.status == "completed"), key=lambda i: i.created_at)
        full = [i for i in done if i.mode != "drill" and i.report]
        latest = full[-1] if full else None
        averages: dict[str, float] = {}
        for crit in CRITERIA:
            values = [i.report["averages"][crit] for i in full[-3:] if crit in (i.report.get("averages") or {})]
            if values:
                averages[crit] = round(mean(values), 2)
                class_buckets[crit].append(averages[crit])
        conf = [(i.confidence_before, i.confidence_after) for i in done
                if i.confidence_before is not None and i.confidence_after is not None]
        last_at = max((i.created_at for i in mine), default=None)
        my_apps = [a for a in apps if a.user_id == student.id]
        flags = []
        if not last_at or (now - last_at).days >= INACTIVE_DAYS:
            flags.append("inactive")
        if conf and conf[-1][1] is not None and conf[-1][1] <= 2:
            flags.append("low_confidence")
        if any(a.status == "interview" and a.interview_at and 0 <= (a.interview_at - now).days <= 7 for a in my_apps):
            flags.append("interview_soon")
        if any(a.status == "offer" for a in my_apps):
            flags.append("has_offer")
        for i in done:
            week = (i.created_at - timedelta(days=i.created_at.weekday())).date().isoformat()
            weekly[week] = weekly.get(week, 0) + 1
        rows.append({
            "id": student.id,
            "name": student.display_name,
            "username": student.username,
            "sessions": len(done),
            "drills_done": sum(1 for i in done if i.mode == "drill"),
            "last_practice": last_at.isoformat() if last_at else None,
            "latest_overall": latest.overall if latest else None,
            "first_overall": full[0].overall if full else None,
            "averages": averages,
            "weakest": min(averages, key=averages.get) if averages else None,  # type: ignore[arg-type]
            "confidence_gain": round(mean(b - a for a, b in conf), 2) if conf else None,
            "applications": {s: sum(1 for a in my_apps if a.status == s) for s in STATUSES},
            "consent_share": student.consent_share,
            "flags": flags,
        })

    class_avg = {c: round(mean(v), 2) for c, v in class_buckets.items() if v}
    weak_spots = sorted(class_avg, key=class_avg.get)[:2] if class_avg else []  # type: ignore[arg-type]
    return {
        "class": {"id": classroom.id, "name": classroom.name, "school": classroom.school, "code": classroom.code},
        "students": rows,
        "class_averages": class_avg,
        "weak_spots": weak_spots,
        "weekly_sessions": [{"week": w, "sessions": n} for w, n in sorted(weekly.items())][-10:],
        "pipeline": {s: sum(1 for a in apps if a.status == s) for s in STATUSES},
        "students_with_offer": sum(1 for r in rows if "has_offer" in r["flags"]),
        "active_last_7d": sum(1 for r in rows if r["last_practice"] and
                              (now - _parse(r["last_practice"])).days < 7),
    }


def _parse(iso: str):
    from datetime import datetime

    return datetime.fromisoformat(iso)


@router.get("/{class_id}/students/{student_id}")
def student_detail(class_id: str, student_id: str, teacher: User = Depends(teacher_user),
                   session: Session = Depends(get_session), kb: Knowledge = Depends(get_kb)):
    classroom = _owned_class(session, teacher, class_id)
    student = session.get(User, student_id)
    if not student or student.class_id != classroom.id:
        raise HTTPException(404, "Student not in this class")
    interviews = session.exec(
        select(Interview).where(Interview.user_id == student.id).order_by(col(Interview.created_at).desc())
    ).all()
    sessions = []
    for iv in interviews:
        if iv.status != "completed":
            continue
        item = {
            "id": iv.id,
            "date": iv.created_at.isoformat(),
            "mode": iv.mode,
            "occupation": kb.occupations[iv.occupation_id].label(iv.language) if iv.occupation_id in kb.occupations
            else iv.occupation_id,
            "language": iv.language,
            "overall": iv.overall,
            "averages": (iv.report or {}).get("averages"),
            "goals": ((iv.report or {}).get("narrative") or {}).get("goals"),
        }
        if student.consent_share:
            item["detail"] = interview_out(iv, kb, include_all=True)
        sessions.append(item)
    apps = session.exec(
        select(Application).where(Application.user_id == student.id, col(Application.deleted_at).is_(None))
    ).all()
    return {
        "student": {"id": student.id, "name": student.display_name, "consent_share": student.consent_share},
        "timeline": mastery_timeline(list(interviews)),
        "sessions": sessions,
        "applications": [
            {"company": a.company, "occupation_id": a.occupation_id, "status": a.status,
             "interview_at": a.interview_at.isoformat() if a.interview_at else None}
            for a in apps
        ],
    }
