"""Interview endpoints - the heart of the product.

    POST /api/interviews                  start (greeting + first question)
    POST /api/interviews/{id}/answer      one candidate answer  → 1 Apertus call
    POST /api/interviews/{id}/retry       redo the last answer  → 1 Apertus call (training mode)
    POST /api/interviews/{id}/self-rating metacognition: "how did that go?" before feedback
    POST /api/interviews/{id}/finish      final report          → 1 Apertus call
    POST /api/interviews/{id}/resume      continue after a safety pause

The same endpoints, with ``Authorization: Bearer <token>``, are the machine
interface for external evaluation harnesses (e.g. FHGR's LLM-as-judge).
"""

from __future__ import annotations

import hashlib
from statistics import mean
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from ..db import Application, Drill, Interview, StudentProfile, User, utcnow
from ..engine import core, phrases
from ..knowledge import CRITERIA, Knowledge, feedback_lang
from ..learning import schedule_drills
from .deps import current_user, get_brain, get_kb, get_session

router = APIRouter(prefix="/api", tags=["interviews"])


class StartIn(BaseModel):
    occupation_id: str
    language: Literal["de", "fr", "it", "en", "gsw"] = "de"
    persona_id: str = "warm"
    mode: Literal["training", "real"] = "training"
    length: Literal["quick", "full"] = "full"
    application_id: str | None = None
    posting: str = Field(default="", max_length=6000)
    confidence_before: int | None = Field(default=None, ge=1, le=5)


class AnswerIn(BaseModel):
    answer: str = Field(max_length=4000)


class RatingIn(BaseModel):
    turn_idx: int
    rating: int = Field(ge=1, le=3)


class FinishIn(BaseModel):
    confidence_after: int | None = Field(default=None, ge=1, le=5)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _candidate(session: Session, user: User) -> dict:
    profile = session.get(StudentProfile, user.id)
    data = dict(profile.data) if profile else {}
    stories = data.get("stories") or []
    return {
        "first_name": user.display_name.split()[0] if user.display_name else "",
        "age": data.get("age") or 15,
        "school": data.get("school") or "",
        "hobbies": data.get("hobbies") or [],
        "experience": data.get("experience") or "",
        "stories": [s.get("text", "") if isinstance(s, dict) else str(s) for s in stories],
    }


def _focus_criteria(session: Session, user: User) -> list[str]:
    """The student's two weakest criteria over their last 5 sessions -
    the planner favours questions that train exactly these."""
    recent = session.exec(
        select(Interview)
        .where(Interview.user_id == user.id, Interview.status == "completed")
        .order_by(col(Interview.created_at).desc())
        .limit(5)
    ).all()
    buckets: dict[str, list[float]] = {}
    for iv in recent:
        for crit, value in ((iv.report or {}).get("averages") or {}).items():
            buckets.setdefault(crit, []).append(value)
    if not buckets:
        return []
    ranked = sorted(buckets, key=lambda c: mean(buckets[c]))
    return ranked[:2]


def _owned(session: Session, user: User, interview_id: str) -> Interview:
    # Serialize state transitions on PostgreSQL so two requests cannot overwrite a turn.
    iv = session.get(Interview, interview_id, with_for_update=True)
    if not iv or iv.user_id != user.id:
        raise HTTPException(404, "Interview not found")
    return iv


def _sync_metrics(iv: Interview, state: dict, model: str) -> None:
    usage = state.get("usage") or {}
    iv.llm_calls = usage.get("calls", 0)
    iv.tokens_in = usage.get("tokens_in", 0)
    iv.tokens_out = usage.get("tokens_out", 0)
    iv.latency_ms = usage.get("latency_ms", 0)
    iv.answers = len(state.get("turns", []))
    iv.model = model


def interview_out(iv: Interview, kb: Knowledge, *, include_all: bool = False) -> dict:
    state = iv.state or {}
    setup = state.get("setup", {})
    persona = kb.personas.get(iv.persona_id)
    occ = kb.occupations.get(iv.occupation_id)
    lang = iv.language
    reveal = iv.mode in ("training", "drill") or iv.status == "completed" or include_all
    turns = []
    for t in state.get("turns", []):
        item = {
            "idx": t["idx"],
            "question": t["question"]["text"],
            "qid": t["question"]["qid"],
            "phase": t["question"]["phase"],
            "is_followup": t["question"].get("is_followup", False),
            "answer": t["answer"],
            "bridge": t.get("bridge", ""),
            "retry_of": t.get("retry_of"),
            "previous": t.get("previous"),
            "self_rating": t.get("self_rating"),
        }
        if reveal:
            item["assessment"] = t.get("assessment")
        turns.append(item)
    plan = state.get("plan", [])
    answered_main = len({t["question"]["qid"] for t in state.get("turns", []) if not t["question"].get("is_followup")})
    current = state.get("current") or {}
    return {
        "id": iv.id,
        "status": iv.status,
        "mode": iv.mode,
        "length": iv.length,
        "language": lang,
        "feedback_language": feedback_lang(lang),
        "occupation": {"id": occ.id, "label": occ.label(lang), "level": occ.level, "icon": occ.icon} if occ else None,
        "persona": {
            "id": persona.id,
            "name": persona.display_name(lang),
            "role": persona.display_role(lang),
            "avatar": persona.avatar,
        }
        if persona
        else None,
        "company": {"name": setup.get("company", {}).get("name"), "town": setup.get("company", {}).get("town")},
        "application_id": iv.application_id,
        "interviewer_message": state.get("interviewer_message", ""),
        "current": {"phase": current.get("phase"), "is_followup": current.get("is_followup", False)},
        "phases": [q["phase"] for q in plan if q["phase"] != "closing"],
        "progress": {"answered": answered_main, "planned": max(1, len(plan) - 1)},
        "done": bool(state.get("done")),
        "safety_pause": bool(state.get("safety_pause")),
        "safety_message": phrases.localized(phrases.SAFETY_MESSAGE, feedback_lang(lang))
        if state.get("safety_pause")
        else None,
        "last_feedback": state.get("last_feedback") if reveal else None,
        "can_retry": iv.mode == "training" and not state.get("done") and bool(state.get("prev")),
        "turns": turns,
        "report": iv.report,
        "overall": iv.overall,
        "confidence_before": iv.confidence_before,
        "confidence_after": iv.confidence_after,
        "usage": {
            "llm_calls": iv.llm_calls,
            "answers": iv.answers,
            "calls_per_answer": round(iv.llm_calls / iv.answers, 2) if iv.answers else 0,
            "tokens_in": iv.tokens_in,
            "tokens_out": iv.tokens_out,
            "avg_latency_ms": round(iv.latency_ms / iv.llm_calls) if iv.llm_calls else 0,
            "model": iv.model,
        },
        "created_at": iv.created_at.isoformat(),
        "completed_at": iv.completed_at.isoformat() if iv.completed_at else None,
    }


def _complete(session: Session, iv: Interview, kb: Knowledge, brain, state: dict) -> dict:
    if not state.get("report"):
        state = core.finish(kb, brain, state)
    iv.state = state
    iv.report = state["report"]
    iv.overall = state["report"]["overall"] if state["report"].get("averages") else None
    iv.status = "completed"
    iv.completed_at = utcnow()
    _sync_metrics(iv, state, brain.model)
    schedule_drills(session, iv)
    return state


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@router.get("/catalog")
def catalog(kb: Knowledge = Depends(get_kb)):
    levels = kb.rubric["scale"]["levels"]
    return {
        "occupations": [
            {
                "id": o.id,
                "level": o.level,
                "field": o.field,
                "icon": o.icon,
                "name": o.name,
                "company": {"name": o.company.name, "town": o.company.town},
                "competencies": list(o.competencies),
            }
            for o in kb.occupations.values()
        ],
        "personas": [
            {"id": p.id, "difficulty": p.difficulty, "avatar": p.avatar, "name": p.name, "role": p.role}
            for p in kb.personas.values()
        ],
        "criteria": {c: kb.rubric["criteria"][c]["name"] for c in CRITERIA},
        "levels": {int(k): v for k, v in levels.items()},
        "languages": ["de", "fr", "it", "en", "gsw"],
    }


@router.get("/interviews")
def list_interviews(user: User = Depends(current_user), session: Session = Depends(get_session),
                    kb: Knowledge = Depends(get_kb)):
    rows = session.exec(
        select(Interview).where(Interview.user_id == user.id).order_by(col(Interview.created_at).desc()).limit(100)
    ).all()
    out = []
    for iv in rows:
        occ = kb.occupations.get(iv.occupation_id)
        persona = kb.personas.get(iv.persona_id)
        out.append({
            "id": iv.id,
            "status": iv.status,
            "mode": iv.mode,
            "language": iv.language,
            "occupation": occ.label(iv.language) if occ else iv.occupation_id,
            "company": (iv.state or {}).get("setup", {}).get("company", {}).get("name"),
            "persona": persona.display_name(iv.language) if persona else "",
            "overall": iv.overall,
            "answers": iv.answers,
            "averages": (iv.report or {}).get("averages"),
            "confidence_before": iv.confidence_before,
            "confidence_after": iv.confidence_after,
            "created_at": iv.created_at.isoformat(),
        })
    return out


@router.post("/interviews")
def start_interview(body: StartIn, user: User = Depends(current_user), session: Session = Depends(get_session),
                    kb: Knowledge = Depends(get_kb), brain=Depends(get_brain)):
    if body.occupation_id not in kb.occupations:
        raise HTTPException(422, "Unknown occupation")
    if body.persona_id not in kb.personas:
        raise HTTPException(422, "Unknown persona")
    occ = kb.occupations[body.occupation_id]
    company = None
    posting = body.posting.strip()
    if body.application_id:
        app = session.get(Application, body.application_id)
        if not app or app.user_id != user.id:
            raise HTTPException(404, "Application not found")
        posting = posting or app.posting
        company = {"name": app.company, "town": app.town or occ.company.town,
                   "facts": [f"Training company: {app.company}" + (f" in {app.town}" if app.town else "")]}
    seed = int(hashlib.sha1(f"{user.id}:{utcnow().isoformat()}".encode()).hexdigest()[:8], 16)
    setup = {
        "language": body.language,
        "occupation_id": occ.id,
        "persona_id": body.persona_id,
        "mode": body.mode,
        "length": body.length,
        "candidate": _candidate(session, user),
        "posting": posting,
    }
    if company:
        setup["company"] = company
    state = core.start(kb, brain, setup, seed=seed, focus=_focus_criteria(session, user))
    iv = Interview(
        user_id=user.id,
        application_id=body.application_id,
        occupation_id=occ.id,
        language=body.language,
        persona_id=body.persona_id,
        mode=body.mode,
        length=body.length,
        state=state,
        confidence_before=body.confidence_before,
    )
    _sync_metrics(iv, state, brain.model)
    session.add(iv)
    session.commit()
    session.refresh(iv)
    return interview_out(iv, kb)


@router.get("/interviews/{interview_id}")
def get_interview(interview_id: str, user: User = Depends(current_user), session: Session = Depends(get_session),
                  kb: Knowledge = Depends(get_kb)):
    return interview_out(_owned(session, user, interview_id), kb)


def _run_turn(request: Request, iv: Interview, answer: str, *, retry: bool) -> dict:
    graph = request.app.state.turn_graph
    try:
        result = graph.invoke({"state": iv.state, "answer": answer, "retry": retry})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return result["state"]


@router.post("/interviews/{interview_id}/answer")
def answer(interview_id: str, body: AnswerIn, request: Request, user: User = Depends(current_user),
           session: Session = Depends(get_session), kb: Knowledge = Depends(get_kb), brain=Depends(get_brain)):
    iv = _owned(session, user, interview_id)
    if iv.status != "active":
        raise HTTPException(409, "This interview is already finished")
    if (iv.state or {}).get("safety_pause"):
        raise HTTPException(409, "Interview is paused")
    state = _run_turn(request, iv, body.answer, retry=False)
    iv.state = state
    _sync_metrics(iv, state, brain.model)
    if state.get("done") and not state.get("safety_pause"):
        _complete(session, iv, kb, brain, state)
    session.add(iv)
    session.commit()
    session.refresh(iv)
    return interview_out(iv, kb)


@router.post("/interviews/{interview_id}/retry")
def retry(interview_id: str, body: AnswerIn, request: Request, user: User = Depends(current_user),
          session: Session = Depends(get_session), kb: Knowledge = Depends(get_kb), brain=Depends(get_brain)):
    iv = _owned(session, user, interview_id)
    if iv.mode != "training" or iv.status != "active":
        raise HTTPException(409, "Retry is available in training mode only")
    if iv.state.get("safety_pause"):
        raise HTTPException(409, "Interview is paused")
    state = _run_turn(request, iv, body.answer, retry=True)
    iv.state = state
    _sync_metrics(iv, state, brain.model)
    if state.get("done") and not state.get("safety_pause"):
        _complete(session, iv, kb, brain, state)
    session.add(iv)
    session.commit()
    session.refresh(iv)
    return interview_out(iv, kb)


@router.post("/interviews/{interview_id}/self-rating")
def self_rating(interview_id: str, body: RatingIn, user: User = Depends(current_user),
                session: Session = Depends(get_session), kb: Knowledge = Depends(get_kb)):
    iv = _owned(session, user, interview_id)
    state = dict(iv.state or {})
    turns = [dict(t) for t in state.get("turns", [])]
    if not 0 <= body.turn_idx < len(turns):
        raise HTTPException(404, "Turn not found")
    turns[body.turn_idx]["self_rating"] = body.rating
    state["turns"] = turns
    iv.state = state
    session.add(iv)
    session.commit()
    return interview_out(iv, kb)


@router.post("/interviews/{interview_id}/resume")
def resume(interview_id: str, user: User = Depends(current_user), session: Session = Depends(get_session),
           kb: Knowledge = Depends(get_kb)):
    iv = _owned(session, user, interview_id)
    iv.state = core.resume_after_pause(iv.state or {})
    session.add(iv)
    session.commit()
    return interview_out(iv, kb)


@router.post("/interviews/{interview_id}/finish")
def finish(interview_id: str, body: FinishIn, user: User = Depends(current_user),
           session: Session = Depends(get_session), kb: Knowledge = Depends(get_kb), brain=Depends(get_brain)):
    iv = _owned(session, user, interview_id)
    if body.confidence_after is not None:
        iv.confidence_after = body.confidence_after
    if iv.status == "active":
        state = dict(iv.state or {})
        if not state.get("turns"):
            iv.status = "abandoned"
        else:
            _complete(session, iv, kb, brain, state)
    session.add(iv)
    session.commit()
    session.refresh(iv)
    return interview_out(iv, kb)


@router.delete("/interviews/{interview_id}")
def delete_interview(interview_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    iv = _owned(session, user, interview_id)
    for drill in session.exec(select(Drill).where(Drill.source_interview_id == iv.id)):
        drill.source_interview_id = None
        session.add(drill)
    session.delete(iv)
    session.commit()
    return {"ok": True}
