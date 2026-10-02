"""Learning-science layer: spaced repetition, mastery and calibration.

Interview skill is a *performance* skill, so Zusage treats it like one:

- **Spaced retrieval practice** - every question a student struggled with
  becomes a 2-minute "drill" card in a Leitner system (1 → 3 → 7 → 14 → 30
  days). Successful recall promotes the card, a weak answer resets it. This
  re-uses the follow-up *cadence* idea from OfferLoop: instead of nudging a
  recruiter after 5/7/10 days, we nudge the student to re-practise.
- **Mastery tracking** - per-criterion averages over time, so progress is
  visible on the six FHGR criteria, not on a single opaque number.
- **Calibration** - students predict how well an answer went before seeing
  feedback; agreement between self-rating and coach rating is a measure of
  metacognitive accuracy (and itself improves with practice).
- **Self-efficacy** - confidence is asked before and after every session;
  the change is the "Lampenfieber-Meter" shown to students and teachers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean

from sqlmodel import Session, select

from .db import Drill, Interview, utcnow

LEITNER_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MASTERED = 3.0  # average rubric score at which a drill counts as recalled successfully


def _turn_avg(turn: dict) -> float | None:
    scores = (turn.get("assessment") or {}).get("scores") or {}
    return mean(scores.values()) if scores else None


def _weakest(turn: dict) -> str:
    scores = (turn.get("assessment") or {}).get("scores") or {}
    return min(scores, key=scores.get) if scores else ""


def schedule_drills(session: Session, interview: Interview, now: datetime | None = None) -> list[Drill]:
    """After an interview: create/refresh drill cards for weak answers."""
    now = now or utcnow()
    created: list[Drill] = []
    turns = (interview.state or {}).get("turns", [])
    # the final attempt per question counts
    final: dict[str, dict] = {}
    for turn in turns:
        q = turn["question"]
        if q.get("is_followup") or q["phase"] in ("closing",) or q["qid"].startswith("posting_"):
            continue
        final[q["qid"]] = turn
    # Only the three weakest answers become cards: a short, focused queue
    # beats an overwhelming one (cognitive load for 15-year-olds).
    ranked = sorted(
        ((qid, turn, _turn_avg(turn)) for qid, turn in final.items() if _turn_avg(turn) is not None),
        key=lambda item: item[2],  # type: ignore[arg-type,return-value]
    )
    if interview.mode != "drill":
        ranked = [r for r in ranked if r[2] < MASTERED][:3]
    for qid, turn, avg in ranked:
        assert avg is not None
        existing = session.exec(
            select(Drill).where(Drill.user_id == interview.user_id, Drill.question_id == qid)
        ).first()
        if interview.mode == "drill" and existing:
            review(existing, avg, now)
            session.add(existing)
            continue
        if avg >= MASTERED:
            continue
        if existing:
            existing.box = 1
            existing.due_at = now + timedelta(days=LEITNER_DAYS[1])
            existing.last_score = avg
            existing.criterion = _weakest(turn)
            existing.updated_at = now
            session.add(existing)
            continue
        drill = Drill(
            user_id=interview.user_id,
            question_id=qid,
            occupation_id=interview.occupation_id,
            criterion=_weakest(turn),
            box=1,
            due_at=now + timedelta(days=LEITNER_DAYS[1]),
            last_score=avg,
            best_score=avg,
            source_interview_id=interview.id,
        )
        session.add(drill)
        created.append(drill)
    return created


def review(drill: Drill, score: float, now: datetime | None = None) -> Drill:
    """Leitner update after a drill attempt."""
    now = now or utcnow()
    drill.reps += 1
    drill.last_score = score
    drill.best_score = max(drill.best_score or 0, score)
    drill.box = min(5, drill.box + 1) if score >= MASTERED else 1
    drill.due_at = now + timedelta(days=LEITNER_DAYS[drill.box])
    drill.updated_at = now
    return drill


def calibration(interviews: list[Interview]) -> dict | None:
    """Agreement between the student's own rating (1-3) and the coach's
    average (mapped to 1-3). Returns share of exact matches + bias."""
    pairs = []
    for iv in interviews:
        for turn in (iv.state or {}).get("turns", []):
            own = turn.get("self_rating")
            avg = _turn_avg(turn)
            if own is None or avg is None:
                continue
            coach = 1 if avg < 2.25 else 2 if avg < 3.25 else 3
            pairs.append((int(own), coach))
    if len(pairs) < 3:
        return None
    match = sum(1 for a, b in pairs if a == b) / len(pairs)
    bias = mean(a - b for a, b in pairs)
    return {"n": len(pairs), "accuracy": round(match, 2), "bias": round(bias, 2)}


def mastery_timeline(interviews: list[Interview]) -> list[dict]:
    done = sorted((i for i in interviews if i.status == "completed" and i.report), key=lambda i: i.created_at)
    return [
        {
            "id": i.id,
            "date": i.created_at.isoformat(),
            "overall": i.overall,
            "averages": (i.report or {}).get("averages", {}),
            "mode": i.mode,
            "confidence_before": i.confidence_before,
            "confidence_after": i.confidence_after,
        }
        for i in done
    ]


def streak_days(interviews: list[Interview], today: datetime | None = None) -> int:
    today = (today or utcnow()).date()
    days = {i.created_at.date() for i in interviews if i.answers > 0}
    streak, cursor = 0, today
    if cursor not in days:
        cursor = cursor - timedelta(days=1)
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
