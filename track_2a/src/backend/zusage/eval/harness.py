"""Zusage evaluation harness.

Three layers, from cheapest/most objective to richest:

1. **Calibration** (no judge). Every answer in ``data/eval/answer_bank.yaml``
   carries a gold quality level (weak < solid < strong). The coach scores each
   answer once; we report Spearman ρ between gold level and coach score,
   pairwise ordering accuracy, and the same split by language → consistency.

2. **Full interviews** (no judge). Scripted candidates (profile × level
   schedule × language) run complete interviews through the real engine.
   We measure flow adherence, LLM calls per answer (FHGR gate < 5), latency,
   schema validity, evidence-grounding rate, interviewer language fidelity and
   a legal-safety check (no questions about religion, origin, pregnancy…).

3. **LLM-as-judge** (optional). An open-weights judge model scores each
   transcript on 8 dimensions mirroring the FHGR criteria (quality,
   relevance, appropriateness of interactions and feedback). Configure with
   JUDGE_BASE_URL / JUDGE_API_KEY / JUDGE_MODEL; defaults to the coach
   endpoint. The judge never sees which system produced a transcript.

Systems compared on identical inputs:
    zusage   - the production coach (Apertus, structured single-call prompt)
    naive    - Apertus with a one-line "give feedback" prompt (ablation)
    rules    - the rule-based offline coach (no LLM)

    zusage eval --out results/ [--systems zusage,naive,rules] [--langs de,fr,it,gsw]
                [--limit N] [--judge] [--interviews N]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..config import get_settings
from ..engine import core
from ..engine.brain import ApertusBrain, Brain, BrainResult, OfflineBrain, TurnInput
from ..engine.validate import evidence_in_answer, lang_ok
from ..knowledge import Knowledge, get_knowledge
from ..llm.client import ChatClient, LLMError, Usage
from .scripted import LEVEL_VALUE, LEVELS, answer_for, followup_answer, load_bank

# ---------------------------------------------------------------------------
# statistics helpers (no numpy/scipy dependency)
# ---------------------------------------------------------------------------


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx, ry = _rank(x), _rank(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 3) if den else None


def bootstrap_ci(x: list[float], y: list[float], n: int = 400, seed: int = 7) -> tuple[float, float] | None:
    if len(x) < 10:
        return None
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        idx = [rng.randrange(len(x)) for _ in x]
        value = spearman([x[i] for i in idx], [y[i] for i in idx])
        if value is not None:
            stats.append(value)
    stats.sort()
    return round(stats[int(0.025 * len(stats))], 3), round(stats[int(0.975 * len(stats)) - 1], 3)


# ---------------------------------------------------------------------------
# naive baseline (ablation): Apertus without Zusage's prompt engineering
# ---------------------------------------------------------------------------


class NaiveBrain(ApertusBrain):
    """Same model, same budget - but a one-line prompt and no rubric anchors,
    no grounding rules, no persona. Shows what the prompt design contributes."""

    name = "naive"

    def assess_turn(self, kb: Knowledge, inp: TurnInput) -> BrainResult:
        system = (
            "You are an interview coach. Rate the candidate's answer and give feedback. Reply as JSON: "
            '{"scores": {"' + '": 1-4, "'.join(inp.targets) + '": 1-4}, "strength": "", "tip": "", '
            '"better_answer": "", "evidence": "", "bridge": "", "follow_up": "", "quality": "", "flag": "none"}'
        )
        user = f"Question: {inp.question}\nAnswer: {inp.answer}"
        result = self.client.complete_json(system, user, max_tokens=self.max_tokens)
        return BrainResult(result.data, result.usage, result.model)


# ---------------------------------------------------------------------------
# layer 1: calibration
# ---------------------------------------------------------------------------


def _question_items(kb: Knowledge, bank: dict, langs: list[str]) -> list[tuple[str, str, str, str]]:
    """(qid, phase, occupation, lang) items that have all three gold levels."""
    items = []
    occ_for = {q.id: o.id for o in kb.occupations.values() for q in o.questions}
    for qid, per_lang in bank.items():
        if qid.startswith("_"):
            continue
        q = kb.question(qid)
        if q is None:
            continue
        for lang in langs:
            levels = per_lang.get(lang) or {}
            if all(levels.get(level) for level in LEVELS):
                items.append((qid, q.phase, occ_for.get(qid, _default_occ(lang)), lang))
    return items


def _default_occ(lang: str) -> str:
    return {"fr": "automech_efz", "it": "logistik_eba", "gsw": "detailhandel_efz", "en": "informatik_efz"}.get(
        lang, "fage_efz"
    )


@dataclass
class Scored:
    system: str
    qid: str
    lang: str
    level: str
    score: float | None
    valid_json: bool
    evidence_ok: bool | None
    feedback_lang_ok: bool
    usage: Usage
    output: dict


def score_answer(
    kb: Knowledge, brain: Brain, qid: str, phase: str, occupation: str, lang: str, answer: str
) -> tuple[dict, Usage, bool]:
    q = kb.question(qid, occupation)
    persona = kb.personas["structured"]
    occ = kb.occupations[occupation]
    inp = TurnInput(
        lang=lang,
        occupation_id=occupation,
        persona_name=persona.display_name(lang),
        persona_role=persona.display_role("en"),
        persona_style=persona.style,
        company={"name": occ.company.name, "town": occ.company.town, "facts": list(occ.company.facts)},
        candidate={"first_name": "Sam", "age": 15},
        phase=phase,
        question=q.in_lang(lang),
        targets=list(q.targets) or ["communication"],
        probe=q.probe,
        followup_allowed=True,
        answer=answer,
    )
    try:
        result = brain.assess_turn(kb, inp)
        return result.data, result.usage, True
    except LLMError:
        return {}, Usage(calls=1), False


def run_calibration(kb, bank, systems: dict[str, Brain], langs: list[str], limit: int | None, log) -> list[Scored]:
    items = _question_items(kb, bank, langs)
    random.Random(11).shuffle(items)
    if limit:
        items = items[:limit]
    from concurrent.futures import ThreadPoolExecutor

    from ..engine.validate import clamp_scores

    tasks = [(qid, phase, occ, lang, level, name, brain) for qid, phase, occ, lang in items for level in LEVELS
             for name, brain in systems.items()]

    def work(task) -> Scored:
        qid, phase, occ, lang, level, name, brain = task
        answer = answer_for(bank, qid, phase, lang, level)
        data, usage, ok = score_answer(kb, brain, qid, phase, occ, lang, answer)
        q = kb.question(qid, occ)
        scores = clamp_scores(data.get("scores"), list(q.targets) or ["communication"])
        evidence = data.get("evidence") or ""
        fb_text = " ".join(str(data.get(k) or "") for k in ("strength", "tip"))
        return Scored(
            system=name, qid=qid, lang=lang, level=level,
            score=statistics.mean(scores.values()) if scores else None,
            valid_json=ok and bool(scores),
            evidence_ok=evidence_in_answer(evidence, answer) if evidence else None,
            feedback_lang_ok=lang_ok(fb_text, "de" if lang == "gsw" else lang) if fb_text.strip() else False,
            usage=usage, output=data,
        )

    rows: list[Scored] = []
    with ThreadPoolExecutor(max_workers=int(os.environ.get("EVAL_WORKERS", "6"))) as pool:
        for n, row in enumerate(pool.map(work, tasks), 1):
            rows.append(row)
            if n % 20 == 0:
                log(f"  calibration {n}/{len(tasks)}")
    return rows


def summarize_calibration(rows: list[Scored]) -> dict:
    out: dict = {}
    for system in sorted({r.system for r in rows}):
        mine = [r for r in rows if r.system == system]
        scored = [r for r in mine if r.score is not None]
        gold = [LEVEL_VALUE[r.level] for r in scored]
        pred = [r.score for r in scored]
        # pairwise ordering within the same question & language
        groups: dict[tuple, dict] = defaultdict(dict)
        for r in scored:
            groups[(r.qid, r.lang)][r.level] = r.score
        pairs = correct = 0
        for g in groups.values():
            for lo, hi in (("weak", "solid"), ("solid", "strong"), ("weak", "strong")):
                if lo in g and hi in g:
                    pairs += 1
                    correct += g[hi] > g[lo]
        per_lang = {}
        for lang in sorted({r.lang for r in scored}):
            sub = [r for r in scored if r.lang == lang]
            per_lang[lang] = {
                "n": len(sub),
                "spearman": spearman([LEVEL_VALUE[r.level] for r in sub], [r.score for r in sub]),
                "mean_by_level": {
                    lv: round(statistics.mean([r.score for r in sub if r.level == lv]), 2)
                    for lv in LEVELS
                    if any(r.level == lv for r in sub)
                },
            }
        evidence = [r.evidence_ok for r in mine if r.evidence_ok is not None]
        calls = sum(r.usage.calls for r in mine)
        out[system] = {
            "n": len(mine),
            "valid_rate": round(sum(r.valid_json for r in mine) / max(1, len(mine)), 3),
            "spearman": spearman(gold, pred),
            "spearman_ci95": bootstrap_ci(gold, pred),
            "pairwise_accuracy": round(correct / pairs, 3) if pairs else None,
            "mean_by_level": {
                lv: round(statistics.mean([r.score for r in scored if r.level == lv]), 2)
                for lv in LEVELS
                if any(r.level == lv for r in scored)
            },
            "evidence_grounded_rate": round(sum(evidence) / len(evidence), 3) if evidence else None,
            "feedback_language_ok": round(sum(r.feedback_lang_ok for r in mine) / max(1, len(mine)), 3),
            "per_language": per_lang,
            "consistency_spread": _spread([v["spearman"] for v in per_lang.values()]),
            "calls": calls,
            "avg_latency_ms": round(sum(r.usage.latency_ms for r in mine) / max(1, calls)),
            "avg_tokens_in": round(sum(r.usage.tokens_in for r in mine) / max(1, calls)),
            "avg_tokens_out": round(sum(r.usage.tokens_out for r in mine) / max(1, calls)),
        }
    return out


def _spread(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(max(vals) - min(vals), 3) if len(vals) > 1 else None


def run_adversarial(kb, data_dir: str, systems: dict[str, Brain], langs: list[str], log) -> list[dict]:
    """Items where length/keywords lie about quality (see data/eval/adversarial.yaml)."""
    import yaml

    from ..engine.validate import clamp_scores

    with open(Path(data_dir) / "eval" / "adversarial.yaml", encoding="utf-8") as fh:
        items = [i for i in yaml.safe_load(fh)["items"] if i["lang"] in langs]
    rows = []
    for item in items:
        q = kb.question(item["qid"])
        for name, brain in systems.items():
            data, usage, ok = score_answer(
                kb, brain, item["qid"], q.phase, _default_occ(item["lang"]), item["lang"], item["answer"]
            )
            scores = clamp_scores(data.get("scores"), list(q.targets) or ["communication"])
            score = statistics.mean(scores.values()) if scores else None
            correct = None if score is None else (score >= 2.5) == (item["level"] == "strong")
            rows.append(
                {
                    "system": name,
                    "id": item["id"],
                    "kind": item["kind"],
                    "lang": item["lang"],
                    "level": item["level"],
                    "score": score,
                    "correct": correct,
                    "tip": data.get("tip"),
                    "latency_ms": usage.latency_ms,
                }
            )
        log(f"  adversarial {item['id']} ({item['kind']}, {item['lang']})")
    return rows


def summarize_adversarial(rows: list[dict]) -> dict:
    out = {}
    for system in sorted({r["system"] for r in rows}):
        mine = [r for r in rows if r["system"] == system and r["correct"] is not None]
        by_kind: dict[str, list[bool]] = defaultdict(list)
        for r in mine:
            by_kind[r["kind"]].append(r["correct"])
        out[system] = {
            "n": len(mine),
            "accuracy": round(sum(r["correct"] for r in mine) / max(1, len(mine)), 3),
            "by_kind": {k: round(sum(v) / len(v), 2) for k, v in sorted(by_kind.items())},
            "mean_weak": round(statistics.mean([r["score"] for r in mine if r["level"] == "weak"] or [0]), 2),
            "mean_strong": round(statistics.mean([r["score"] for r in mine if r["level"] == "strong"] or [0]), 2),
        }
    return out


# ---------------------------------------------------------------------------
# layer 2: full interviews
# ---------------------------------------------------------------------------

_ILLEGAL = re.compile(
    r"\b(religion|religiö|religieu|religios|schwanger|enceinte|incinta|pregnan|kinderwunsch|"
    r"herkunft|origine|nationalit|partei|parti politique|partito|sexuelle orientierung|orientation sexuelle|"
    r"krankheit|maladie|malattia)\w*",
    re.IGNORECASE,
)

SCHEDULES = {
    "nervous_then_warm": ["weak", "weak", "solid", "solid", "strong"],
    "steady": ["solid"],
    "strong": ["strong"],
    "struggling": ["weak"],
}


def run_interviews(
    kb, bank, brain: Brain, profiles: list[dict], schedules: dict, log, length: str = "quick"
) -> list[dict]:
    transcripts = []
    for profile in profiles:
        for sched_name, schedule in schedules.items():
            lang = profile["language"]
            setup = {
                "language": lang,
                "occupation_id": profile["target"],
                "length": length,
                "persona_id": ["warm", "structured", "direct"][len(transcripts) % 3],
                "candidate": {
                    "first_name": profile["first_name"],
                    "age": profile["age"],
                    "school": profile["school"],
                    "hobbies": profile["hobbies"],
                    "experience": profile["experience"],
                },
            }
            started = time.time()
            state = core.start(kb, brain, setup, seed=len(transcripts))
            messages = [{"role": "interviewer", "text": state["interviewer_message"]}]
            i = 0
            while not state["done"] and i < 20:
                cur = state["current"]
                level = schedule[min(i, len(schedule) - 1)]
                if cur["is_followup"] and cur["phase"] == "candidate_questions":
                    answer = {
                        "de": "Nein danke, das war alles.",
                        "fr": "Non merci, c'est tout.",
                        "it": "No grazie, è tutto.",
                        "gsw": "Nei merci, das wär's.",
                        "en": "No thanks, that's all.",
                    }[lang]
                elif cur["is_followup"]:
                    answer = followup_answer(bank, lang, level)
                else:
                    answer = answer_for(bank, cur["qid"], cur["phase"], lang, level)
                state = core.step(kb, brain, state, answer)
                fb = state.get("last_feedback") or {}
                messages.append({"role": "candidate", "text": answer, "level": level})
                messages.append(
                    {
                        "role": "coach",
                        "feedback": {k: fb.get(k) for k in ("scores", "strength", "tip", "better_answer", "evidence")},
                    }
                )
                messages.append({"role": "interviewer", "text": state["interviewer_message"]})
                i += 1
            state = core.finish(kb, brain, state)
            interviewer_texts = [m["text"] for m in messages if m["role"] == "interviewer"]
            expected = "de" if lang == "gsw" else lang
            transcripts.append(
                {
                    "profile": profile["id"],
                    "language": lang,
                    "schedule": sched_name,
                    "occupation": profile["target"],
                    "persona": setup["persona_id"],
                    "messages": messages,
                    "report": state["report"],
                    "metrics": {
                        "answers": len(state["turns"]),
                        "followups": state.get("followups_used", 0),
                        "calls": state["usage"]["calls"],
                        "calls_per_answer": round(state["usage"]["calls"] / max(1, len(state["turns"])), 2),
                        "latency_s": round(time.time() - started, 1),
                        "avg_model_latency_ms": round(state["usage"]["latency_ms"] / max(1, state["usage"]["calls"])),
                        "interviewer_lang_ok": round(
                            sum(lang_ok(t, expected if lang != "gsw" else "gsw") for t in interviewer_texts)
                            / len(interviewer_texts),
                            3,
                        ),
                        "degraded_turns": sum(1 for t in state["turns"] if t["assessment"].get("degraded")),
                        "illegal_topic_hits": sum(len(_ILLEGAL.findall(t)) for t in interviewer_texts[1:]),
                        "overall": state["report"]["overall"],
                        "flow_ok": [t["question"]["phase"] for t in state["turns"]]
                        == sorted(
                            [t["question"]["phase"] for t in state["turns"]],
                            key=["intro", "motivation", "strengths", "situational", "candidate_questions"].index,
                        ),
                    },
                }
            )
            log(
                f"  interview {len(transcripts)}: {profile['id']} {lang} {sched_name} → overall "
                f"{state['report']['overall']}, {transcripts[-1]['metrics']['calls_per_answer']} calls/answer"
            )
    return transcripts


def summarize_interviews(transcripts: list[dict]) -> dict:
    if not transcripts:
        return {}
    m = [t["metrics"] for t in transcripts]
    by_sched: dict[str, list[int]] = defaultdict(list)
    by_lang: dict[str, list[int]] = defaultdict(list)
    for t in transcripts:
        by_sched[t["schedule"]].append(t["report"]["overall"])
        by_lang[t["language"]].append(t["report"]["overall"])
    return {
        "n": len(transcripts),
        "calls_per_answer": round(statistics.mean(x["calls_per_answer"] for x in m), 2),
        "max_calls_per_answer": max(x["calls_per_answer"] for x in m),
        "avg_model_latency_ms": round(statistics.mean(x["avg_model_latency_ms"] for x in m)),
        "interviewer_language_ok": round(statistics.mean(x["interviewer_lang_ok"] for x in m), 3),
        "flow_ok_rate": round(sum(x["flow_ok"] for x in m) / len(m), 3),
        "followups_per_interview": round(statistics.mean(x["followups"] for x in m), 2),
        "degraded_turn_rate": round(sum(x["degraded_turns"] for x in m) / max(1, sum(x["answers"] for x in m)), 3),
        "illegal_topic_hits": sum(x["illegal_topic_hits"] for x in m),
        "overall_by_schedule": {k: round(statistics.mean(v), 1) for k, v in by_sched.items()},
        "overall_by_language": {k: round(statistics.mean(v), 1) for k, v in by_lang.items()},
    }


# ---------------------------------------------------------------------------
# layer 3: LLM-as-judge
# ---------------------------------------------------------------------------

JUDGE_DIMENSIONS = {
    "interview_realism": "Does the interviewer behave like a real Swiss training company (natural, polite, formal register, on-topic)?",
    "question_relevance": "Are the questions relevant to the apprenticeship and appropriate for a 15-year-old?",
    "adaptivity": "Does the interviewer react to the answers (sensible follow-ups when vague, moves on when complete)?",
    "feedback_specificity": "Is the coach feedback specific to what the candidate actually said (not generic)?",
    "feedback_actionability": "Does each tip give one concrete, doable next step?",
    "constructiveness": "Is the feedback encouraging, honest and developmentally appropriate for adolescents (no shaming)?",
    "faithfulness": "Is feedback grounded in the transcript, with no invented facts about the candidate or company?",
    "language_quality": "Is the language correct, natural and consistently in the interview language?",
}


def judge_prompt(transcript: dict) -> tuple[str, str]:
    dims = "\n".join(f"- {k}: {v}" for k, v in JUDGE_DIMENSIONS.items())
    system = (
        "You are an expert evaluator of job-interview training for Swiss apprenticeship applicants (age 14-17). "
        "Score the transcript on each dimension from 1 (poor) to 5 (excellent). Be strict and calibrated. "
        f"Dimensions:\n{dims}\nReply ONLY with JSON: "
        + '{"scores": {"<dimension>": <1-5>}, "comment": "<one sentence>"}'
    )
    lines = []
    for m in transcript["messages"]:
        if m["role"] == "interviewer":
            lines.append(f"INTERVIEWER: {m['text']}")
        elif m["role"] == "candidate":
            lines.append(f"CANDIDATE: {m['text']}")
        else:
            fb = m["feedback"]
            lines.append(f"COACH: strength={fb.get('strength')!r} tip={fb.get('tip')!r} scores={fb.get('scores')}")
    narrative = transcript["report"].get("narrative", {})
    lines.append(f"FINAL REPORT: {json.dumps(narrative, ensure_ascii=False)[:1200]}")
    return system, "\n".join(lines)[:14000]


def run_judge(transcripts: list[dict], client: ChatClient, log) -> list[dict]:
    out = []
    for i, t in enumerate(transcripts, 1):
        system, user = judge_prompt(t)
        try:
            res = client.complete_json(system, user, max_tokens=300)
            scores = {k: int(v) for k, v in (res.data.get("scores") or {}).items() if k in JUDGE_DIMENSIONS}
            out.append(
                {
                    "system": t.get("system"),
                    "profile": t["profile"],
                    "language": t["language"],
                    "schedule": t["schedule"],
                    "scores": scores,
                    "comment": res.data.get("comment", ""),
                }
            )
        except (LLMError, ValueError, TypeError) as exc:
            out.append({"system": t.get("system"), "profile": t["profile"], "error": str(exc)})
        log(f"  judged {i}/{len(transcripts)}")
    return out


def summarize_judge(rows: list[dict]) -> dict:
    out = {}
    for system in sorted({r.get("system") for r in rows if r.get("scores")}):
        mine = [r for r in rows if r.get("system") == system and r.get("scores")]
        out[system] = {
            d: round(statistics.mean(r["scores"][d] for r in mine if d in r["scores"]), 2)
            for d in JUDGE_DIMENSIONS
            if any(d in r["scores"] for r in mine)
        }
        out[system]["overall"] = round(statistics.mean(v for k, v in out[system].items()), 2)
        by_lang: dict[str, list[float]] = defaultdict(list)
        for r in mine:
            by_lang[r["language"]].append(statistics.mean(r["scores"].values()))
        out[system]["by_language"] = {k: round(statistics.mean(v), 2) for k, v in by_lang.items()}
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zusage eval")
    parser.add_argument("--out", default="eval-results")
    parser.add_argument("--systems", default="zusage,naive,rules")
    parser.add_argument("--langs", default="de,fr,it,gsw,en")
    parser.add_argument("--limit", type=int, default=None, help="max calibration items (question×language)")
    parser.add_argument("--interviews", type=int, default=8, help="profiles for full-interview runs (0 = skip)")
    parser.add_argument("--schedules", default=",".join(SCHEDULES))
    parser.add_argument("--judge", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    kb = get_knowledge(settings.data_dir)
    bank = load_bank(settings.data_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        log_lines.append(msg)

    systems: dict[str, Brain] = {}
    wanted = args.systems.split(",")
    if settings.llm_enabled:

        def client() -> ChatClient:
            return ChatClient(
                settings.llm_base_url,
                settings.llm_api_key,
                settings.llm_name,
                timeout_s=settings.llm_timeout_s,
                temperature=0.0,
            )

        if "zusage" in wanted:
            systems["zusage"] = ApertusBrain(client(), max_tokens=settings.llm_max_tokens)
        if "naive" in wanted:
            systems["naive"] = NaiveBrain(client(), max_tokens=settings.llm_max_tokens)
    else:
        log("! no LLM configured - evaluating the rule-based coach only")
    if "rules" in wanted or not systems:
        systems["rules"] = OfflineBrain()

    langs = args.langs.split(",")
    log(f"• calibration over {', '.join(systems)} in {', '.join(langs)}")
    rows = run_calibration(kb, bank, systems, langs, args.limit, log)
    calibration = summarize_calibration(rows)
    (out / "calibration_rows.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "system": r.system,
                    "qid": r.qid,
                    "lang": r.lang,
                    "level": r.level,
                    "score": r.score,
                    "valid": r.valid_json,
                    "evidence_ok": r.evidence_ok,
                    "feedback_lang_ok": r.feedback_lang_ok,
                    "latency_ms": r.usage.latency_ms,
                    "tokens_in": r.usage.tokens_in,
                    "tokens_out": r.usage.tokens_out,
                    "output": r.output,
                },
                ensure_ascii=False,
            )
            for r in rows
        ),
        encoding="utf-8",
    )

    log("• adversarial set")
    adv_rows = run_adversarial(kb, settings.data_dir, systems, langs, log)
    adversarial = summarize_adversarial(adv_rows)
    (out / "adversarial_rows.json").write_text(json.dumps(adv_rows, ensure_ascii=False, indent=1), encoding="utf-8")

    interviews: dict = {}
    all_transcripts: list[dict] = []
    if args.interviews:
        profiles = [p for p in kb.profiles if p["language"] in langs][: args.interviews]
        schedules = {k: SCHEDULES[k] for k in args.schedules.split(",") if k in SCHEDULES}
        for name in [s for s in ("zusage", "rules") if s in systems]:
            log(f"• full interviews with {name}")
            transcripts = run_interviews(kb, bank, systems[name], profiles, schedules, log)
            for t in transcripts:
                t["system"] = name
            interviews[name] = summarize_interviews(transcripts)
            all_transcripts += transcripts
        (out / "transcripts.json").write_text(
            json.dumps(all_transcripts, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    judge: dict = {}
    if args.judge and all_transcripts:
        base = os.environ.get("JUDGE_BASE_URL") or settings.llm_base_url
        model = os.environ.get("JUDGE_MODEL") or settings.llm_name
        key = os.environ.get("JUDGE_API_KEY") or settings.llm_api_key
        log(f"• LLM-as-judge with {model}")
        judged = run_judge(all_transcripts, ChatClient(base, key, model, temperature=0.0, timeout_s=120), log)
        (out / "judgements.json").write_text(json.dumps(judged, ensure_ascii=False, indent=1), encoding="utf-8")
        judge = {"model": model, "results": summarize_judge(judged)}

    summary = {
        "model": settings.llm_name if settings.llm_enabled else "offline",
        "calibration": calibration,
        "adversarial": adversarial,
        "interviews": interviews,
        "judge": judge,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
    log(f"✓ results written to {out}/summary.json")
    for name, c in calibration.items():
        log(
            f"  {name:7s} ρ={c['spearman']} pairwise={c['pairwise_accuracy']} valid={c['valid_rate']} "
            f"means={c['mean_by_level']}"
        )
    for name, a in adversarial.items():
        log(f"  {name:7s} adversarial accuracy={a['accuracy']} by kind={a['by_kind']}")
    for name, s in interviews.items():
        log(
            f"  {name:7s} interviews: {s['calls_per_answer']} calls/answer, lang_ok={s['interviewer_language_ok']}, "
            f"flow_ok={s['flow_ok_rate']}, by schedule={s['overall_by_schedule']}"
        )
    return 0
