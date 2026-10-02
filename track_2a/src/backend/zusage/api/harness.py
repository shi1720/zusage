"""OpenAI-compatible facade for external evaluation harnesses.

Many LLM-as-judge benchmarks drive the system under test as if it were a chat
model: they keep a message list and POST it to ``/v1/chat/completions``. This
endpoint maps that convention onto a real Zusage interview:

- the FIRST user message starts the interview (its text is ignored unless it is
  a JSON setup object); the assistant reply is the greeting + first question;
- every further user message is a candidate answer → one Apertus call;
- the session is keyed by the OpenAI ``user`` field (or ``metadata.session``),
  falling back to a hash of the first user message;
- the reply carries the interviewer's words in ``content`` and the coach's
  structured feedback in a ``zusage`` extension field (and, with
  ``metadata.feedback_in_content=true``, appended to the content).

Auth: ``Authorization: Bearer <ZUSAGE_HARNESS_KEY>`` (default ``zusage-demo``
while demo mode is on). Interviews are owned by a dedicated harness account.
"""

from __future__ import annotations

import hashlib
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import Interview, User
from ..engine import core, phrases
from ..knowledge import Knowledge, feedback_lang
from ..security import hash_password
from .deps import get_brain, get_kb, get_session
from .interviews import _complete, _sync_metrics

router = APIRouter(tags=["harness"])
HARNESS_USER = "harness"


class ChatMessage(BaseModel):
    role: str
    content: str | list | None = None


class ChatRequest(BaseModel):
    model: str = "zusage"
    messages: list[ChatMessage]
    user: str | None = None
    metadata: dict | None = None


def _text(content) -> str:
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def _auth(request: Request) -> None:
    settings = request.app.state.settings
    import os

    key = os.environ.get("ZUSAGE_HARNESS_KEY") or ("zusage-demo" if settings.seed_demo else "")
    if not key:
        raise HTTPException(404, "Harness endpoint disabled (set ZUSAGE_HARNESS_KEY)")
    if request.headers.get("Authorization", "") != f"Bearer {key}":
        raise HTTPException(401, "Invalid harness key")


def _harness_user(session: Session) -> User:
    user = session.exec(select(User).where(User.username == HARNESS_USER)).first()
    if not user:
        user = User(username=HARNESS_USER, display_name="Kandidat", password_hash=hash_password(str(time.time())),
                    role="student", onboarded=True)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def _format_feedback(fb: dict | None, kb: Knowledge, lang: str) -> str:
    if not fb or not fb.get("scores"):
        return ""
    flang = feedback_lang(lang)
    scores = ", ".join(f"{kb.criterion_name(c, flang)} {v}/4" for c, v in fb["scores"].items())
    parts = [f"[Coach] {scores}"]
    for key in ("strength", "tip", "better_answer"):
        if fb.get(key):
            parts.append(f"- {fb[key]}")
    return "\n".join(parts)


@router.post("/v1/chat/completions")
def chat_completions(body: ChatRequest, request: Request, session: Session = Depends(get_session),
                     kb: Knowledge = Depends(get_kb), brain=Depends(get_brain)):
    _auth(request)
    user_msgs = [_text(m.content) for m in body.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(422, "At least one user message is required")
    meta = body.metadata or {}
    try:  # optional JSON setup in the first user message
        first = json.loads(user_msgs[0])
        if isinstance(first, dict):
            meta = {**first, **meta}
    except (json.JSONDecodeError, TypeError):
        pass
    if meta.get("language", "de") not in ("de", "fr", "it", "en", "gsw"):
        raise HTTPException(422, "Unknown interview language")
    key = meta.get("session") or body.user or hashlib.sha1(user_msgs[0].encode()).hexdigest()[:16]
    if not isinstance(key, str):
        raise HTTPException(422, "Session must be text")
    owner = _harness_user(session)
    session_id = f"h{hashlib.sha1(key.encode()).hexdigest()[:15]}"

    iv = session.get(Interview, session_id, with_for_update=True)
    if iv is None:
        occupation = meta.get("occupation_id") if meta.get("occupation_id") in kb.occupations else "kaufmann_efz"
        setup = {
            "language": meta.get("language", "de"),
            "occupation_id": occupation,
            "persona_id": meta["persona_id"] if meta.get("persona_id") in kb.personas else "structured",
            "mode": "training",
            "length": meta.get("length", "full"),
            "candidate": {"first_name": meta.get("first_name", ""), "age": meta.get("age", 15),
                          "school": meta.get("school", ""), "hobbies": meta.get("hobbies", []),
                          "experience": meta.get("experience", "")},
            "posting": meta.get("posting", ""),
        }
        state = core.start(kb, brain, setup, seed=int(session_id[1:9], 16))
        iv = Interview(id=session_id, user_id=owner.id, occupation_id=occupation, language=setup["language"],
                       persona_id=setup["persona_id"], mode="training", length=setup["length"], state=state)
        _sync_metrics(iv, state, brain.model)
        session.add(iv)
        session.commit()
        session.refresh(iv)

    feedback = None
    answers_expected = len(user_msgs) - 1
    if answers_expected > len(iv.state.get("turns", [])) and iv.status == "active":
        state = request.app.state.turn_graph.invoke({"state": iv.state, "answer": user_msgs[-1]})["state"]
        iv.state = state
        feedback = state.get("last_feedback")
        _sync_metrics(iv, state, brain.model)
        if state.get("done"):
            _complete(session, iv, kb, brain, state)
        session.add(iv)
        session.commit()
        session.refresh(iv)

    content = iv.state.get("interviewer_message", "")
    if iv.state.get("safety_pause"):
        content = phrases.localized(phrases.SAFETY_MESSAGE, feedback_lang(iv.language))
    if meta.get("feedback_in_content") and feedback:
        content = f"{content}\n\n{_format_feedback(feedback, kb, iv.language)}"
    if iv.status == "completed" and meta.get("feedback_in_content") and iv.report:
        narrative = iv.report.get("narrative", {})
        content += "\n\n[Report] " + " ".join(filter(None, [narrative.get("headline"), narrative.get("summary")]))
    return {
        "id": f"chatcmpl-{iv.id}-{len(iv.state.get('turns', []))}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": f"zusage/{brain.model}",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": iv.tokens_in, "completion_tokens": iv.tokens_out,
                  "total_tokens": iv.tokens_in + iv.tokens_out},
        "zusage": {
            "interview_id": iv.id,
            "phase": (iv.state.get("current") or {}).get("phase"),
            "done": iv.status == "completed",
            "safety_pause": bool(iv.state.get("safety_pause")),
            "feedback": feedback,
            "report": iv.report,
            "llm_calls": iv.llm_calls,
        },
    }
