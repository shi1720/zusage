"""Interview engine - pure functions over :class:`InterviewState`.

    start()  -> greeting + first question            (0 LLM calls, +1 if a job ad is tailored)
    step()   -> assess answer, react, ask next/probe (1 LLM call)
    retry()  -> redo the last answer (training mode) (1 LLM call)
    finish() -> final development report             (1 LLM call, amortised over the interview)

The LangGraph wiring (``graph.py``) and the HTTP API both call these
functions, so there is exactly one implementation of the interview logic.
"""

from __future__ import annotations

import copy
import logging
from statistics import mean

from ..knowledge import CRITERIA, Knowledge, feedback_lang
from ..llm.client import LLMError, Usage
from . import guard, phrases, validate
from .brain import Brain, OfflineBrain, TurnInput
from .planner import answerable_count, build_plan
from .prompts import extract_facts_from_posting
from .state import Assessment, InterviewState, PlannedQuestion, Setup, TurnRecord

log = logging.getLogger("zusage.engine")

MORE_QUESTIONS = {
    "de": "Haben Sie noch weitere Fragen?",
    "fr": "Avez-vous d'autres questions ?",
    "it": "Ha altre domande?",
    "en": "Do you have any other questions?",
    "gsw": "Händ Sie no wiiteri Frage?",
}


def _usage_add(state: InterviewState, usage: Usage) -> None:
    total = state.setdefault("usage", {"calls": 0, "tokens_in": 0, "tokens_out": 0, "latency_ms": 0})
    for key, value in usage.as_dict().items():
        total[key] = total.get(key, 0) + value


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


DRILL_INTRO = {
    "de": "Schnelltraining – eine Frage, volle Konzentration:",
    "fr": "Entraînement express – une question, pleine concentration :",
    "it": "Allenamento lampo – una domanda, massima concentrazione:",
    "en": "Quick drill – one question, full focus:",
    "gsw": "Schnälltraining – ei Frag, volli Konzentration:",
}


def start(
    kb: Knowledge,
    brain: Brain,
    setup: Setup,
    *,
    seed: int = 0,
    focus: list[str] | None = None,
    drill_qid: str | None = None,
) -> InterviewState:
    occ = kb.occupations[setup["occupation_id"]]
    persona = kb.personas[setup.get("persona_id") or "warm"]
    lang = setup["language"]
    company = setup.get("company") or {
        "name": occ.company.name,
        "town": occ.company.town,
        "facts": list(occ.company.facts),
    }
    posting = (setup.get("posting") or "").strip()
    if posting:
        company = dict(company)
        company["facts"] = list(company.get("facts", [])) + extract_facts_from_posting(posting)
    setup = {**setup, "company": company, "persona_id": persona.id}
    # Profiles and job ads need the same redaction as spoken answers.
    def redact_value(value):
        if isinstance(value, str):
            return guard.redact(value)
        if isinstance(value, dict):
            return {k: redact_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact_value(v) for v in value]
        return value

    setup = redact_value(setup)
    posting = setup.get("posting", "")

    candidate = setup.get("candidate") or {}
    plan = build_plan(
        kb,
        occupation_id=occ.id,
        language=lang,
        length=setup.get("length", "full"),
        seed=seed,
        focus=focus,
        persona_difficulty=persona.difficulty,
        has_experience=bool(candidate.get("experience")),
    )

    state: InterviewState = {
        "setup": setup,
        "plan": plan,
        "cursor": 0,
        "followups_used": 0,
        "turns": [],
        "done": False,
        "safety_pause": False,
        "report": None,
        "usage": {"calls": 0, "tokens_in": 0, "tokens_out": 0, "latency_ms": 0},
        "last_feedback": None,
    }

    if drill_qid:
        from .planner import to_planned

        q = kb.question(drill_qid, occ.id)
        if q is None:
            raise ValueError(f"unknown question {drill_qid}")
        state["plan"] = [to_planned(q, lang), to_planned(kb.question("closing"), lang)]  # type: ignore[arg-type]
        state["current"] = state["plan"][0]
        state["interviewer_message"] = f"{phrases.localized(DRILL_INTRO, lang)} {state['current']['text']}"
        return state

    if posting:
        _tailor_plan(kb, brain, state, posting)

    state["current"] = state["plan"][0]
    hello = phrases.greeting(
        lang,
        first_name=candidate.get("first_name", ""),
        persona=persona.display_name(lang),
        role=persona.display_role(lang),
        company=company["name"],
        town=company["town"],
        occupation=occ.label(lang),
    )
    state["interviewer_message"] = f"{hello} {state['current']['text']}"
    return state


def _tailor_plan(kb: Knowledge, brain: Brain, state: InterviewState, posting: str) -> None:
    """One optional call: replace the generic 'why us' question with two
    questions written for the pasted job ad."""
    setup = state["setup"]
    try:
        result = brain.tailor(kb, lang=setup["language"], occupation_id=setup["occupation_id"], posting=posting)
    except LLMError as exc:
        log.warning("tailoring failed (%s) - keeping the generic plan", exc.code)
        return
    _usage_add(state, result.usage)
    tailored: list[PlannedQuestion] = []
    for i, raw in enumerate((result.data.get("questions") or [])[:2]):
        text = validate.text_field(raw.get("text") if isinstance(raw, dict) else "", 220)
        if not text or not validate.lang_ok(text, setup["language"]):
            continue
        targets = [t for t in (raw.get("targets") or []) if t in CRITERIA] or ["motivation", "relevance"]
        tailored.append(
            {
                "qid": f"posting_{i + 1}",
                "phase": "motivation" if i == 0 else "situational",
                "text": text,
                "targets": targets,
                "probe": validate.text_field(raw.get("probe"), 160),
                "is_followup": False,
            }
        )
    if not tailored:
        return
    plan = state["plan"]
    idx = next((i for i, q in enumerate(plan) if q["qid"] == "mot_why_company"), None)
    if idx is None:
        idx = next(i for i, q in enumerate(plan) if q["phase"] == "strengths")
        plan[idx:idx] = tailored[:1]
        rest = tailored[1:]
    else:
        plan[idx : idx + 1] = tailored[:1]
        rest = tailored[1:]
    if rest:
        cand = next(i for i, q in enumerate(plan) if q["phase"] == "candidate_questions")
        plan[cand:cand] = rest


# ---------------------------------------------------------------------------
# step
# ---------------------------------------------------------------------------


def _recent(state: InterviewState) -> list[tuple[str, str]]:
    return [(t["question"]["text"], t["answer"]) for t in state.get("turns", [])[-2:]]


def _sanitize(
    raw: dict,
    *,
    answer: str,
    targets: list[str],
    lang: str,
    followup_allowed: bool,
    persona_name: str = "",
    fallback: dict | None = None,
) -> tuple[Assessment, str, str]:
    """Validate a model turn output → (assessment, reaction, follow_up).

    Repairs observed failure modes of an 8B model: wrong language or register in
    coach text, questions stuffed into the reaction, the interviewer addressing
    itself by name, whole-answer "quotes", German "ß"."""
    flang = feedback_lang(lang)
    fallback = fallback or {}
    swiss = lang in ("de", "gsw")
    raw = {k: (validate.swiss_spelling(v) if swiss and isinstance(v, str) else v) for k, v in raw.items()}

    scores = validate.clamp_scores(raw.get("scores"), targets)
    missing_scores = not scores
    if missing_scores:
        scores = validate.clamp_scores(fallback.get("scores"), targets)
    evidence = validate.shorten_quote(validate.text_field(raw.get("evidence"), 300), answer)
    if evidence and not validate.evidence_in_answer(evidence, answer):
        log.info("dropping unverifiable evidence quote")
        evidence = ""
    quality = raw.get("quality") if raw.get("quality") in validate.QUALITIES else "solid"
    flag = raw.get("flag") if raw.get("flag") in validate.FLAGS else "none"
    if quality in ("empty", "off_topic") and scores:
        scores = {k: min(v, 2) for k, v in scores.items()}

    def coach_text(key: str, limit: int) -> str:
        text = validate.text_field(raw.get(key), limit)
        ok = validate.lang_ok(text, flang) and validate.informal_ok(text, flang)
        if text and ok and not validate.third_person(text):
            return text
        return fallback.get(key, "")

    better = validate.text_field(raw.get("better_answer"), 520)
    if better and not validate.lang_ok(better, "de" if lang == "gsw" else lang):
        better = fallback.get("better_answer", "")
    assessment: Assessment = {
        "scores": scores,
        "evidence": evidence,
        "strength": coach_text("strength", 300),
        "tip": coach_text("tip", 300),
        "better_answer": better,
        "quality": quality,
        "flag": flag,
    }
    if missing_scores:
        assessment["degraded"] = True

    reaction = validate.text_field(raw.get("reaction") or raw.get("bridge"), 420)
    reaction = validate.strip_self_address(reaction, persona_name)
    statements, questions = validate.split_questions(reaction)
    reaction = validate.first_sentences(statements, 2)
    if reaction and (not validate.lang_ok(reaction, lang) or not validate.formal_ok(reaction, lang)
                     or validate.grades_answer(reaction)):
        reaction = ""
    follow_up = validate.text_field(raw.get("follow_up"), 240) if followup_allowed else ""
    if follow_up and (not validate.lang_ok(follow_up, lang) or not follow_up.rstrip().endswith("?")
                      or not validate.formal_ok(follow_up, lang)):
        follow_up = ""
    # the model often asks its probe inside the reaction - reuse it when a probe is warranted
    if followup_allowed and not follow_up and questions and quality in ("weak", "off_topic", "empty"):
        candidate = questions[0]
        if validate.lang_ok(candidate, lang) and validate.formal_ok(candidate, lang) and len(candidate) <= 240:
            follow_up = candidate
    return assessment, reaction, follow_up


def _advance(state: InterviewState, follow_up: str, candidate_asked: bool, max_followups: int) -> None:
    current = state["current"]
    lang = state["setup"]["language"]
    if follow_up and state["followups_used"] < max_followups and not current["is_followup"]:
        state["followups_used"] += 1
        state["current"] = {**current, "text": follow_up, "is_followup": True}
        return
    if current["phase"] == "candidate_questions" and candidate_asked and not current["is_followup"]:
        state["current"] = {
            **current,
            "text": MORE_QUESTIONS.get(lang, MORE_QUESTIONS["en"]),
            "is_followup": True,
            "targets": ["communication"],
        }
        return
    state["cursor"] += 1
    state["current"] = state["plan"][state["cursor"]]


def step(
    kb: Knowledge,
    brain: Brain,
    state: InterviewState,
    answer: str,
    *,
    max_followups: int = 3,
    max_chars: int = 1500,
    retry_of: int | None = None,
) -> InterviewState:
    if state.get("done"):
        raise ValueError("interview already finished")
    if state.get("safety_pause"):
        return copy.deepcopy(state)
    snapshot = copy.deepcopy({k: v for k, v in state.items() if k != "prev"})
    state = copy.deepcopy(state)
    setup = state["setup"]
    lang = setup["language"]
    flang = feedback_lang(lang)
    current = state["current"]
    answer = (answer or "").strip()[:max_chars]

    # 1. empty answer → gentle reprompt, no model call, no advance
    if not answer:
        state["interviewer_message"] = f"{phrases.localized(phrases.EMPTY_REPROMPT, lang)} {current['text']}"
        state["last_feedback"] = None
        return state

    # 2. deterministic safety pre-screen
    screen = guard.screen(answer)
    if screen == "distress":
        state["safety_pause"] = True
        state["interviewer_message"] = ""
        state["last_feedback"] = {"flag": "distress", "scores": {}, "quality": "empty"}
        state["prev"] = snapshot
        return state
    clean_answer = guard.redact(answer)

    # 3. one model call: assess + react + decide follow-up
    persona = kb.personas[setup["persona_id"]]
    followup_allowed = (
        state["followups_used"] < max_followups
        and not current["is_followup"]
        and current["phase"] not in ("closing", "candidate_questions")
    )
    targets = list(current["targets"]) or ["communication"]
    inp = TurnInput(
        lang=lang,
        occupation_id=setup["occupation_id"],
        persona_name=persona.display_name(lang),
        persona_role=persona.display_role("en"),
        persona_style=persona.style,
        company=setup["company"],
        candidate=setup.get("candidate") or {},
        phase=current["phase"],
        question=current["text"],
        targets=targets,
        probe=current["probe"],
        followup_allowed=followup_allowed,
        answer=clean_answer,
        recent=_recent(state),
        posting=setup.get("posting", ""),
    )
    degraded = False
    try:
        result = brain.assess_turn(kb, inp)
    except LLMError as exc:
        # Graceful degradation: the interview continues on the rule-based coach.
        log.warning("model call failed (%s) - degrading this turn to the offline coach", exc.code)
        result = OfflineBrain().assess_turn(kb, inp)
        degraded = True
    _usage_add(state, result.usage)

    fallback = OfflineBrain().assess_turn(kb, inp).data
    assessment, bridge, follow_up = _sanitize(
        result.data,
        answer=clean_answer,
        targets=targets,
        lang=lang,
        followup_allowed=followup_allowed,
        persona_name=persona.display_name(lang),
        fallback=fallback,
    )
    if degraded:
        assessment["degraded"] = True  # type: ignore[typeddict-unknown-key]
    if screen == "personal_data" or assessment.get("flag") == "personal_data":
        assessment["privacy_note"] = phrases.localized(phrases.PERSONAL_DATA_NOTE, flang)  # type: ignore[typeddict-unknown-key]
    if assessment.get("flag") == "distress":
        state["safety_pause"] = True

    turn: TurnRecord = {
        "idx": len(state["turns"]),
        "question": current,
        "answer": clean_answer,
        "assessment": assessment,
        "bridge": bridge,
        "retry_of": retry_of,
        "usage": result.usage.as_dict(),
    }
    state["turns"].append(turn)
    state["last_feedback"] = assessment

    # 4. advance through the plan
    candidate_asked = "?" in answer
    _advance(state, follow_up, candidate_asked, max_followups)
    nxt = state["current"]
    reaction = bridge or phrases.pick_ack(lang, seed=len(state["turns"]))
    if nxt["phase"] == "closing":
        state["interviewer_message"] = f"{reaction} {nxt['text']}"
        state["done"] = True
    else:
        state["interviewer_message"] = f"{reaction} {nxt['text']}"
    state["prev"] = snapshot
    return state


def retry(kb: Knowledge, brain: Brain, state: InterviewState, answer: str, **kw) -> InterviewState:
    """Deliberate practice: answer the same question again and see the delta.
    Restores the state from before the last answer, then re-runs the step."""
    prev = state.get("prev")
    if not prev or not state.get("turns"):
        raise ValueError("nothing to retry")
    if not (answer or "").strip():
        raise ValueError("Enter an answer before retrying")
    if guard.screen(answer) == "distress":
        paused = copy.deepcopy(state)
        paused["safety_pause"] = True
        paused["interviewer_message"] = ""
        return paused
    last = state["turns"][-1]
    restored: InterviewState = copy.deepcopy(prev)
    new_state = step(kb, brain, restored, answer, retry_of=last["idx"], **kw)
    # keep the full history: the old attempt stays visible for the progress delta
    new_turn = new_state["turns"][-1]
    new_turn["previous"] = {  # type: ignore[typeddict-unknown-key]
        "answer": last["answer"],
        "scores": last["assessment"].get("scores", {}),
    }
    # usage of the replaced attempt still counts - it was spent
    for key, value in (last.get("usage") or {}).items():
        new_state["usage"][key] = new_state["usage"].get(key, 0) + value
    new_state["retries"] = state.get("retries", 0) + 1  # type: ignore[typeddict-unknown-key]
    return new_state


def resume_after_pause(state: InterviewState) -> InterviewState:
    state = copy.deepcopy(state)
    state["safety_pause"] = False
    lang = state["setup"]["language"]
    state["interviewer_message"] = (
        state["current"]["text"]
        if state["current"]["phase"] != "closing"
        else phrases.localized(phrases.CLOSING_FALLBACK, lang)
    )
    return state


# ---------------------------------------------------------------------------
# finish
# ---------------------------------------------------------------------------


def criterion_averages(state: InterviewState) -> dict[str, float]:
    buckets: dict[str, list[int]] = {c: [] for c in CRITERIA}
    for turn in state.get("turns", []):
        for crit, score in (turn.get("assessment", {}).get("scores") or {}).items():
            buckets[crit].append(score)
    return {c: round(mean(v), 2) for c, v in buckets.items() if v}


def overall_score(averages: dict[str, float]) -> int:
    if not averages:
        return 0
    return round((mean(averages.values()) - 1) / 3 * 100)


def finish(kb: Knowledge, brain: Brain, state: InterviewState) -> InterviewState:
    state = copy.deepcopy(state)
    setup = state["setup"]
    lang = setup["language"]
    averages = criterion_averages(state)
    compact = [
        {
            "question": t["question"]["text"],
            "answer": t["answer"],
            "scores": t["assessment"].get("scores", {}),
            "strength": t["assessment"].get("strength", ""),
            "tip": t["assessment"].get("tip", ""),
        }
        for t in state.get("turns", [])
    ]
    narrative: dict = {}
    if compact:
        try:
            result = brain.final_report(
                kb, lang=lang, occupation_id=setup["occupation_id"], averages=averages, turns=compact
            )
            _usage_add(state, result.usage)
            narrative = result.data
        except LLMError as exc:
            log.warning("report call failed (%s) - using the offline report", exc.code)
        fallback = (
            OfflineBrain()
            .final_report(
                kb,
                lang=lang,
                occupation_id=setup["occupation_id"],
                averages=averages or {"communication": 2.0},
                turns=compact,
            )
            .data
        )
        narrative = _sanitize_report(narrative, fallback, feedback_lang(lang))

    answered = len([t for t in state.get("turns", []) if t.get("retry_of") is None])
    usage = state.get("usage", {})
    state["report"] = {
        "overall": overall_score(averages),
        "averages": averages,
        "narrative": narrative,
        "answers": answered,
        "planned": answerable_count(state["plan"]),
        "followups": state.get("followups_used", 0),
        "retries": state.get("retries", 0),
        "llm_calls_per_answer": round(usage.get("calls", 0) / max(1, len(state.get("turns", []))), 2),
    }
    state["done"] = True
    return state


def _sanitize_report(raw: dict, fallback: dict, flang: str) -> dict:
    out: dict = {}
    for key, limit in (("headline", 120), ("summary", 600), ("best_moment", 300), ("wise_feedback", 300)):
        text = validate.text_field(raw.get(key), limit)
        out[key] = text if text and validate.lang_ok(text, flang) else fallback.get(key, "")
    strengths = [validate.text_field(s, 240) for s in (raw.get("strengths") or []) if isinstance(s, str)]
    out["strengths"] = [s for s in strengths if s and validate.lang_ok(s, flang)][:3] or fallback["strengths"]
    goals = []
    for g in raw.get("goals") or []:
        if (isinstance(g, dict) and g.get("title") and g.get("how")
                and validate.lang_ok(str(g["title"]), flang) and validate.lang_ok(str(g["how"]), flang)):
            goals.append({"title": validate.text_field(g["title"], 80), "how": validate.text_field(g["how"], 300)})
    out["goals"] = goals[:2] or fallback["goals"]
    return out
