"""LangGraph wiring of the interview engine.

Two graphs share the same node functions from ``core.py``:

``turn_graph``      - one graph invocation per candidate answer. Stateless:
                      the caller passes the full state + the new answer and
                      receives the next state. Used by the Zusage HTTP API
                      (state is persisted in the app database).

``interview_graph`` - the whole interview as ONE long-running graph that
                      pauses with ``interrupt()`` whenever it needs the
                      candidate's answer. This is the form LangGraph Server
                      and Aegra (FHGR's suggested deployment target) expect:
                      register it in ``aegra.json`` and drive it through the
                      Agent Protocol with ``Command(resume=answer)``.

           ┌────────┐   ┌──────────────┐   ┌─────────┐
  answer ─▶│ assess │──▶│ done? report │──▶│   END   │
           └────────┘   └──────────────┘   └─────────┘
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..config import get_settings
from ..knowledge import get_knowledge
from . import core, guard, phrases
from .brain import build_brain


class TurnIO(TypedDict, total=False):
    state: dict[str, Any]
    answer: str
    retry: bool


def _runtime():
    settings = get_settings()
    return get_knowledge(settings.data_dir), build_brain(settings), settings


def build_turn_graph(kb=None, brain=None, settings=None):
    if kb is None or brain is None or settings is None:
        kb, brain, settings = _runtime()

    def assess(io: TurnIO) -> TurnIO:
        fn = core.retry if io.get("retry") else core.step
        state = fn(kb, brain, io["state"], io.get("answer", ""),
                   max_followups=settings.max_followups_per_interview, max_chars=settings.max_answer_chars)
        return {"state": state}

    def report(io: TurnIO) -> TurnIO:
        return {"state": core.finish(kb, brain, io["state"])}

    def route(io: TurnIO) -> str:
        st = io["state"]
        return "report" if st.get("done") and not st.get("report") and not st.get("safety_pause") else END

    g = StateGraph(TurnIO)
    g.add_node("assess", assess)
    g.add_node("report", report)
    g.add_edge(START, "assess")
    g.add_conditional_edges("assess", route, {"report": "report", END: END})
    g.add_edge("report", END)
    return g.compile()


# ---------------------------------------------------------------------------
# Aegra / LangGraph-Server graph (interrupt-driven)
# ---------------------------------------------------------------------------


class InterviewIO(TypedDict, total=False):
    setup: dict[str, Any]  # input: language, occupation_id, persona_id, length, candidate
    state: dict[str, Any]
    answer: str
    transcript: list[dict[str, str]]


def build_interview_graph(kb=None, brain=None, settings=None, checkpointer=None):
    """begin -> ask (interrupt) -> assess -> ask ... -> report.

    Each node is checkpointed separately, so resuming after an interrupt never
    replays earlier model calls."""
    if kb is None or brain is None or settings is None:
        kb, brain, settings = _runtime()

    def begin(io: InterviewIO) -> InterviewIO:
        state = core.start(kb, brain, io["setup"])
        return {"state": state, "transcript": [{"role": "interviewer", "text": state["interviewer_message"]}]}

    def ask(io: InterviewIO) -> InterviewIO:
        state = io["state"]
        message = (phrases.localized(phrases.SAFETY_MESSAGE, state["setup"]["language"])
                   if state.get("safety_pause") else state["interviewer_message"])
        answer = interrupt({"interviewer": message, "phase": state["current"]["phase"],
                            "safety_pause": bool(state.get("safety_pause")),
                            "resume_command": "resume" if state.get("safety_pause") else None})
        return {"answer": str(answer)}

    def assess(io: InterviewIO) -> InterviewIO:
        if io["state"].get("safety_pause"):
            state = (core.resume_after_pause(io["state"]) if io.get("answer", "").strip().lower() == "resume"
                     else io["state"])
            return {"state": state}
        state = core.step(kb, brain, io["state"], io.get("answer", ""),
                          max_followups=settings.max_followups_per_interview)
        if state.get("safety_pause"):
            return {"state": state}
        transcript = list(io.get("transcript", [])) + [
            {"role": "candidate", "text": guard.redact(io.get("answer", ""))}
        ]
        if state.get("last_feedback") and state["last_feedback"].get("tip"):
            transcript.append({"role": "coach", "text": state["last_feedback"]["tip"]})
        transcript.append({"role": "interviewer", "text": state["interviewer_message"]})
        return {"state": state, "transcript": transcript}

    def report(io: InterviewIO) -> InterviewIO:
        return {"state": core.finish(kb, brain, io["state"])}

    g = StateGraph(InterviewIO)
    g.add_node("begin", begin)
    g.add_node("ask", ask)
    g.add_node("assess", assess)
    g.add_node("report", report)
    g.add_edge(START, "begin")
    g.add_edge("begin", "ask")
    g.add_edge("ask", "assess")
    g.add_conditional_edges("assess", lambda io: "report" if io["state"].get("done") else "ask",
                            {"report": "report", "ask": "ask"})
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)


def __getattr__(name: str):  # lazy, so importing this module never needs an LLM
    if name == "graph":
        return build_interview_graph()
    raise AttributeError(name)
