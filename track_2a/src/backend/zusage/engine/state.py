"""Interview state - a plain, JSON-serialisable dict shape.

The whole state of an interview fits in one JSON document, which is stored
on the interview row after every step. That makes the engine stateless
(any worker can continue any interview), trivially resumable, and lets the
same state run unchanged inside LangGraph / Aegra.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

Mode = Literal["training", "real"]
Length = Literal["quick", "full"]


class PlannedQuestion(TypedDict):
    qid: str
    phase: str
    text: str
    targets: list[str]
    probe: str
    is_followup: bool


class Assessment(TypedDict, total=False):
    scores: dict[str, int]  # criterion -> 1..4 (only criteria observable in this answer)
    evidence: str  # verbatim quote from the candidate's answer
    strength: str  # what went well (coach voice, informal)
    tip: str  # one concrete improvement
    better_answer: str  # a short model answer in the candidate's own voice
    quality: str  # strong | solid | weak | off_topic | empty
    flag: str  # none | distress | inappropriate | personal_data


class TurnRecord(TypedDict, total=False):
    idx: int
    question: PlannedQuestion
    answer: str
    assessment: Assessment
    bridge: str
    retry_of: int | None
    usage: dict[str, int]


class Setup(TypedDict, total=False):
    language: str  # de | fr | it | en | gsw
    occupation_id: str
    persona_id: str
    mode: Mode
    length: Length
    candidate: dict[str, Any]  # first_name, age, school, hobbies, experience, stories...
    company: dict[str, Any]  # name, town, facts (closed fact base)
    posting: str  # optional pasted job ad (treated as data, never as instructions)


class InterviewState(TypedDict, total=False):
    setup: Setup
    plan: list[PlannedQuestion]
    cursor: int  # index into plan of the question currently being asked
    current: PlannedQuestion
    followups_used: int
    turns: list[TurnRecord]
    interviewer_message: str  # what the interviewer says now (shown + spoken)
    done: bool
    safety_pause: bool
    report: dict[str, Any] | None
    usage: dict[str, int]  # cumulative LLM usage
    # transient, per step
    answer: str
    last_feedback: Assessment | None
