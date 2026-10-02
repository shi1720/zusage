"""Command-line entry points.

    zusage serve                  run the web app (uvicorn)
    zusage selfcheck [--url U]    end-to-end smoke test over HTTP: sign in, run a
                                  scripted interview, verify report + budget
    zusage simulate [...]         run one scripted interview in the terminal
    zusage eval [...]             run the evaluation harness (see zusage.eval.harness)
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

from .config import get_settings


def _print(msg: str) -> None:
    print(msg, flush=True)


def selfcheck(url: str, lang: str, timeout: float) -> int:
    """Drive a full interview through the public HTTP API - the same path a
    browser or an external LLM-as-judge harness takes."""
    from .eval.scripted import answer_for, followup_answer, load_bank

    bank = load_bank(get_settings().data_dir)
    client = httpx.Client(base_url=url, timeout=timeout)
    deadline = time.time() + 60
    while True:
        try:
            cfg = client.get("/api/config").json()
            break
        except httpx.HTTPError:
            if time.time() > deadline:
                _print(f"✗ server not reachable at {url}")
                return 1
            time.sleep(1)
    _print(f"• server up - coach mode: {cfg['mode']} ({cfg['model']})")
    # a throwaway account, deleted at the end - the demo class stays untouched
    import secrets as _secrets

    username = f"selfcheck-{_secrets.token_hex(3)}"
    r = client.post("/api/auth/register", json={"username": username, "password": _secrets.token_urlsafe(12),
                                                 "display_name": "Lea", "role": "student", "ui_lang": "de"})
    if r.status_code != 200:
        _print(f"✗ sign-up failed: {r.status_code} {r.text[:200]}")
        return 1
    iv = client.post("/api/interviews", json={"occupation_id": "fage_efz", "language": lang, "length": "quick",
                                               "persona_id": "warm", "confidence_before": 2}).json()
    _print(f"• interview started: {iv['interviewer_message'][:110]}…")
    started = time.time()
    steps = 0
    while not iv["done"] and steps < 15:
        current = iv["current"]
        if current["is_followup"]:
            answer = followup_answer(bank, lang, "solid")
        else:
            qid = next((t["qid"] for t in iv["turns"][-1:]), "")
            phase = current["phase"] or "situational"
            answer = answer_for(bank, {"intro": "intro_about_you", "motivation": "mot_why_occupation",
                                       "strengths": "str_strengths", "candidate_questions": "cand_questions"}
                                .get(phase, "_situational"), phase, lang, "strong") or qid
        r = client.post(f"/api/interviews/{iv['id']}/answer", json={"answer": answer})
        if r.status_code != 200:
            _print(f"✗ answer failed: {r.status_code} {r.text[:200]}")
            return 1
        iv = r.json()
        steps += 1
        fb = iv.get("last_feedback") or {}
        _print(f"  ↳ answer {steps}: scores={fb.get('scores')}  next: {iv['interviewer_message'][:70]}…")
    iv = client.post(f"/api/interviews/{iv['id']}/finish", json={"confidence_after": 4}).json()
    report = iv.get("report") or {}
    usage = iv["usage"]
    elapsed = time.time() - started
    ok = iv["status"] == "completed" and report.get("narrative")
    budget_ok = usage["calls_per_answer"] < 5
    _print(f"• report: overall={report.get('overall')} headline={report.get('narrative', {}).get('headline')!r}")
    _print(f"• budget: {usage['llm_calls']} model calls / {usage['answers']} answers = {usage['calls_per_answer']} "
           f"per answer (limit < 5) {'✓' if budget_ok else '✗'} · {elapsed:.1f}s total")
    client.delete("/api/me")
    if ok and budget_ok:
        _print("✓ selfcheck passed - Zusage works end to end")
        return 0
    _print("✗ selfcheck failed")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zusage")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8080)

    p_check = sub.add_parser("selfcheck")
    p_check.add_argument("--url", default="http://localhost:8080")
    p_check.add_argument("--lang", default="de")
    p_check.add_argument("--timeout", type=float, default=120)

    p_sim = sub.add_parser("simulate")
    p_sim.add_argument("--occupation", default="fage_efz")
    p_sim.add_argument("--lang", default="de")
    p_sim.add_argument("--level", default="solid", choices=["weak", "solid", "strong"])
    p_sim.add_argument("--length", default="quick", choices=["quick", "full"])

    sub.add_parser("record-seed", help="record demo-class sessions with the configured Apertus endpoint")

    p_eval = sub.add_parser("eval")
    p_eval.add_argument("args", nargs=argparse.REMAINDER)

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["eval"]:  # pass everything through to the harness parser
        from .eval.harness import main as eval_main

        return eval_main(argv[1:])
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("zusage.main:create_app", factory=True, host=args.host, port=args.port)
        return 0
    if args.cmd == "selfcheck":
        return selfcheck(args.url, args.lang, args.timeout)
    if args.cmd == "record-seed":
        from pathlib import Path

        from .engine.brain import build_brain
        from .eval.scripted import load_bank
        from .knowledge import get_knowledge
        from .seed import FIXTURE, _run_scripted, session_plan

        settings = get_settings()
        if not settings.llm_enabled:
            _print("✗ configure LLM_BASE_URL / LLM_API_KEY first")
            return 1
        kb, brain, bank = get_knowledge(settings.data_dir), build_brain(settings), load_bank(settings.data_dir)
        out: dict = {}
        for username, k, setup, schedule in session_plan(kb):
            state = _run_scripted(kb, bank, setup, schedule, seed=k + len(username), brain=brain)
            state.pop("prev", None)
            out[f"{username}:{k}"] = {"model": f"{settings.llm_name} (recorded)", "state": state}
            _print(f"• {username}:{k} {setup['language']} → overall {state['report']['overall']}, "
                   f"{state['usage']['calls']} calls")
        path = Path(settings.data_dir) / FIXTURE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        _print(f"✓ wrote {path}")
        return 0
    if args.cmd == "simulate":
        from .engine import core
        from .engine.brain import build_brain
        from .eval.scripted import answer_for, followup_answer, load_bank
        from .knowledge import get_knowledge

        settings = get_settings()
        kb, brain = get_knowledge(settings.data_dir), build_brain(settings)
        bank = load_bank(settings.data_dir)
        state = core.start(kb, brain, {"language": args.lang, "occupation_id": args.occupation,
                                       "persona_id": "structured", "length": args.length,
                                       "candidate": {"first_name": "Sam"}})
        while not state["done"]:
            _print(f"\n🎙  {state['interviewer_message']}")
            cur = state["current"]
            answer = (followup_answer(bank, args.lang, args.level) if cur["is_followup"]
                      else answer_for(bank, cur["qid"], cur["phase"], args.lang, args.level))
            _print(f"🧑 {answer}")
            state = core.step(kb, brain, state, answer)
            _print("📝 " + json.dumps(state.get("last_feedback"), ensure_ascii=False))
        state = core.finish(kb, brain, state)
        _print("\n" + json.dumps(state["report"], ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "eval":
        from .eval.harness import main as eval_main

        return eval_main(args.args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
