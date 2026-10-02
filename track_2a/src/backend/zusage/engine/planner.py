"""Deterministic interview planner.

The plan is the *skeleton* of the interview: which questions, in which order,
following the FHGR flow (intro -> motivation -> strengths -> situational ->
candidate questions -> closing). The LLM adds the *flesh* at run time -
reactions, follow-up probes, answers to the candidate's questions - but never
decides the skeleton. Three reasons:

1. Reliability - planned questions are pre-written and reviewed in DE / FR /
   IT / EN / Swiss German, so question quality and language never drift.
2. Efficiency - no LLM call is spent on planning (except an optional single
   call to tailor two questions to a pasted job ad).
3. Pedagogy - the planner implements *variation* and *interleaving*: each
   session draws different variants, and questions targeting the student's
   weakest criteria are favoured (adaptive practice across sessions).
"""

from __future__ import annotations

import random

from ..knowledge import Knowledge, Question
from .state import PlannedQuestion

# Alternatives drawn per slot; first element is the default.
_STRENGTH_ALTS = ("str_weakness", "str_friends")
_SITUATIONAL_ALTS = ("sit_team_conflict", "sit_mistake", "sit_stress")
_MOTIVATION_ALTS = ("mot_schnupper", "mot_future")


def to_planned(q: Question, lang: str, *, text: str | None = None) -> PlannedQuestion:
    return {
        "qid": q.id,
        "phase": q.phase,
        "text": text or q.in_lang(lang),
        "targets": list(q.targets),
        "probe": q.probe,
        "is_followup": False,
    }


def _score_for_focus(q: Question, focus: list[str]) -> int:
    return sum(1 for t in q.targets if t in focus)


def _pick(kb: Knowledge, ids: tuple[str, ...], rng: random.Random, focus: list[str]) -> Question:
    pool = [q for q in (kb.question(i) for i in ids) if q is not None]
    if focus:
        best = max(_score_for_focus(q, focus) for q in pool)
        pool = [q for q in pool if _score_for_focus(q, focus) == best]
    return rng.choice(pool)


def build_plan(
    kb: Knowledge,
    *,
    occupation_id: str,
    language: str,
    length: str = "full",
    seed: int = 0,
    focus: list[str] | None = None,
    persona_difficulty: int = 2,
    has_experience: bool = True,
) -> list[PlannedQuestion]:
    """Return the ordered list of questions, closing message last."""
    rng = random.Random(seed)
    focus = focus or []
    occ = kb.occupations[occupation_id]
    occ_motivation = [q for q in occ.questions if q.phase == "motivation"]
    occ_situational = [q for q in occ.questions if q.phase == "situational"]

    plan: list[Question] = [kb.question("intro_about_you")]  # type: ignore[list-item]
    plan.append(kb.question("mot_why_occupation"))  # type: ignore[arg-type]

    if length == "full":
        if occ_motivation:
            plan.append(rng.choice(occ_motivation))
        motivation_alt = _pick(kb, _MOTIVATION_ALTS if has_experience else ("mot_future",), rng, focus)
        plan.append(motivation_alt)
        plan.append(kb.question("mot_why_company"))  # type: ignore[arg-type]

    plan.append(kb.question("str_strengths"))  # type: ignore[arg-type]
    if length == "full":
        plan.append(_pick(kb, _STRENGTH_ALTS, rng, focus))

    if occ_situational:
        # Harder personas get the harder occupation scenario.
        occ_situational.sort(key=lambda q: q.difficulty, reverse=persona_difficulty >= 2)
        plan.append(occ_situational[0])
    if length == "full" or not occ_situational:
        plan.append(_pick(kb, _SITUATIONAL_ALTS, rng, focus))

    plan.append(kb.question("cand_questions"))  # type: ignore[arg-type]
    plan.append(kb.question("closing"))  # type: ignore[arg-type]

    return [to_planned(q, language) for q in plan if q is not None]


def answerable_count(plan: list[PlannedQuestion]) -> int:
    return sum(1 for q in plan if q["phase"] != "closing")
