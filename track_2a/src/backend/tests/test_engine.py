"""Interview engine: full runs, budget, follow-ups, safety, retry, degradation."""

import pytest

from zusage.engine import core
from zusage.engine.brain import OfflineBrain
from zusage.engine.planner import answerable_count, build_plan
from zusage.engine.validate import detect_lang

SETUP = {"occupation_id": "fage_efz", "persona_id": "warm", "mode": "training", "length": "quick",
         "candidate": {"first_name": "Lea", "experience": "Schnupperlehre im Pflegeheim"}}
LONG = "Zum Beispiel habe ich in der Schnupperlehre einer Bewohnerin geholfen, dann habe ich gelernt geduldig zu sein."


def run_interview(kb, brain, lang, answer=LONG, length="quick"):
    state = core.start(kb, brain, {**SETUP, "language": lang, "length": length}, seed=3)
    steps = 0
    while not state["done"]:
        state = core.step(kb, brain, state, answer)
        steps += 1
        assert steps < 25
    return core.finish(kb, brain, state), steps


@pytest.mark.parametrize("lang", ["de", "fr", "it", "en", "gsw"])
def test_full_interview_in_every_language(kb, lang):
    state, steps = run_interview(kb, OfflineBrain(), lang)
    assert state["done"] and state["report"]["overall"] > 0
    assert state["interviewer_message"]
    # pre-written planned questions keep the interview in the right language
    for turn in state["turns"]:
        if not turn["question"]["is_followup"] and lang != "gsw":
            assert detect_lang(turn["question"]["text"]) in (lang, None)


def test_plan_follows_fhgr_flow(kb):
    plan = build_plan(kb, occupation_id="kaufmann_efz", language="de", length="full", seed=1)
    phases = [q["phase"] for q in plan]
    order = ["intro", "motivation", "strengths", "situational", "candidate_questions", "closing"]
    assert [p for p in order if p in phases] == order
    assert phases == sorted(phases, key=order.index)
    assert answerable_count(plan) == 10
    assert answerable_count(build_plan(kb, occupation_id="kaufmann_efz", language="de", length="quick")) == 5


def test_plan_varies_and_targets_focus(kb):
    plans = {tuple(q["qid"] for q in build_plan(kb, occupation_id="koch_efz", language="de", seed=s)) for s in range(8)}
    assert len(plans) > 1  # variation across sessions
    focused = build_plan(kb, occupation_id="koch_efz", language="de", seed=0, focus=["examples"])
    assert "sit_team_conflict" in [q["qid"] for q in focused] or "sit_mistake" in [q["qid"] for q in focused]


def test_budget_one_call_per_answer(kb, fake_brain):
    brain = fake_brain(report={"headline": "Gut gemacht!", "summary": "Du hast das gut gemacht und viel geübt.",
                               "strengths": ["Du bist klar."], "goals": [{"title": "Beispiele", "how": "Übe STAR."}],
                               "wise_feedback": "Ich glaube an dich, du schaffst das."})
    state, steps = run_interview(kb, brain, "de")
    assert brain.calls == steps + 1  # one per answer + one report
    assert state["report"]["llm_calls_per_answer"] < 1.5
    assert state["report"]["narrative"]["headline"] == "Gut gemacht!"


def test_followups_are_capped(kb, fake_brain):
    outputs = [{"scores": {}, "follow_up": "Können Sie das bitte konkreter erklären?", "bridge": "Danke."}] * 20
    state, _ = run_interview(kb, fake_brain(turn_outputs=outputs), "de", length="full")
    assert state["followups_used"] <= 3
    assert sum(1 for t in state["turns"] if t["question"]["is_followup"]) <= 5  # 3 probes + candidate-question loop


def test_empty_answer_reprompts_without_model_call(kb, fake_brain):
    brain = fake_brain()
    state = core.start(kb, brain, {**SETUP, "language": "de"})
    after = core.step(kb, brain, state, "   ")
    assert brain.calls == 0 and after["cursor"] == 0 and not after["turns"]
    assert "Zeit" in after["interviewer_message"]


def test_distress_pauses_without_model_call(kb, fake_brain):
    brain = fake_brain()
    state = core.start(kb, brain, {**SETUP, "language": "de"})
    after = core.step(kb, brain, state, "Ehrlich gesagt will ich nicht mehr leben.")
    assert after["safety_pause"] and brain.calls == 0
    resumed = core.resume_after_pause(after)
    assert not resumed["safety_pause"] and resumed["interviewer_message"]


def test_personal_data_is_redacted_before_the_model(kb, fake_brain):
    seen = {}

    class Spy(fake_brain):
        def assess_turn(self, kb, inp):
            seen["answer"] = inp.answer
            return super().assess_turn(kb, inp)

    state = core.start(kb, Spy(), {**SETUP, "language": "de"})
    after = core.step(kb, Spy(), state, "Ich bin Lea, meine Nummer ist 079 123 45 67.")
    assert "079" not in seen["answer"] and "079" not in after["turns"][0]["answer"]
    assert after["last_feedback"]["privacy_note"]


def test_model_output_is_validated(kb, fake_brain):
    hallucinated = {
        "scores": {"clarity": 9, "examples": 3, "nonsense": 4},
        "evidence": "words the student never said",
        "strength": "Du hast klar geantwortet.",
        "tip": "Nenne ein Beispiel.",
        "quality": "great",
        "follow_up": "Why is that?",  # wrong language → dropped
        "bridge": "That is very interesting indeed, thank you.",  # wrong language → fallback
        "flag": "none",
    }
    state = core.start(kb, fake_brain(turn_outputs=[hallucinated]), {**SETUP, "language": "de"})
    after = core.step(kb, fake_brain(turn_outputs=[hallucinated]), state, "Ich bin Lea und spiele Volleyball im Verein.")
    fb = after["last_feedback"]
    assert fb["evidence"] == ""
    assert set(fb["scores"]) <= {"clarity", "communication", "self_awareness"} and fb["scores"]["clarity"] == 4
    assert fb["quality"] == "solid"
    assert not after["current"]["is_followup"]
    assert "interesting" not in after["interviewer_message"]


def test_retry_keeps_history_and_delta(kb, fake_brain):
    first = {"scores": {"clarity": 2, "communication": 2, "self_awareness": 1}, "bridge": "Danke."}
    second = {"scores": {"clarity": 4, "communication": 3, "self_awareness": 3}, "bridge": "Danke."}
    brain = fake_brain(turn_outputs=[first, second])
    state = core.start(kb, brain, {**SETUP, "language": "de"})
    state = core.step(kb, brain, state, "Ich bin Lea.")
    retried = core.retry(kb, brain, state, "Ich bin Lea, 15, Captain im Volleyball und passe auf meine Cousins auf.")
    assert len(retried["turns"]) == 1
    assert retried["turns"][0]["previous"]["scores"]["clarity"] == 2
    assert retried["turns"][0]["assessment"]["scores"]["clarity"] == 4
    assert retried["usage"]["calls"] == 2  # both attempts are counted against the budget


def test_model_outage_degrades_gracefully(kb, fake_brain):
    state, _ = run_interview(kb, fake_brain(fail=True), "fr")
    assert state["done"] and state["report"]["narrative"]["headline"]
    assert all(t["assessment"].get("degraded") for t in state["turns"])


def test_tailored_questions_from_job_ad(kb, fake_brain):
    tailor = {"questions": [
        {"text": "Was wissen Sie über unser Pflegezentrum in Chur?", "targets": ["motivation"], "probe": "facts"},
        {"text": "Wie würden Sie einer Bewohnerin beim Essen helfen?", "targets": ["examples"], "probe": "steps"},
    ]}
    setup = {**SETUP, "language": "de", "length": "full", "posting": "Pflegezentrum Calanda Chur sucht Lernende FaGe."}
    state = core.start(kb, fake_brain(tailor=tailor), setup)
    qids = [q["qid"] for q in state["plan"]]
    assert "posting_1" in qids and "posting_2" in qids and "mot_why_company" not in qids
