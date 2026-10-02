"""Real HTTP checks, including five live languages. No API key is required.
Run: uv run --project src/backend python scripts/e2e.py --url https://zusage.web.app
"""
import argparse
import json
import time
from pathlib import Path

import httpx

from zusage.config import Settings
from zusage.eval.scripted import answer_for, load_bank


def checked(response):
    response.raise_for_status()
    return response.json()


def run(url):
    bank = load_bank(Settings().data_dir)
    results = []
    for idx, language in enumerate(["de", "fr", "it", "en", "gsw"]):
        with httpx.Client(base_url=url, timeout=60) as client:
            checked(client.post("/api/auth/demo/student"))
            before = checked(client.get("/api/me"))
            assert checked(client.get("/api/me"))["id"] == before["id"]
            apps = checked(client.get("/api/applications"))
            assert apps and checked(client.get("/api/dashboard"))["due_drills"]
            started = time.perf_counter()
            iv = checked(client.post("/api/interviews", json={"occupation_id": "fage_efz", "language": language,
                          "persona_id": ["warm", "structured", "direct"][idx % 3], "length": "quick",
                          "mode": "real" if language == "it" else "training", "confidence_before": 2}))
            evidence_count = 0
            degraded = 0
            for turn in range(18):
                if iv["done"]:
                    break
                phase = iv["current"]["phase"]
                qid = {"intro": "intro_free", "strengths": "str_strength", "candidate_questions": "candidate_questions"}.get(phase, "")
                answer = answer_for(bank, qid, phase, language, "strong")
                if phase == "candidate_questions":
                    answer = {"de": "Nein, danke, das war alles.", "fr": "Non merci, c'est tout.",
                              "it": "No grazie, è tutto.", "en": "No, thank you, that is all.",
                              "gsw": "Nei, merci, das wär's."}[language]
                iv = checked(client.post(f"/api/interviews/{iv['id']}/answer", json={"answer": answer}))
                if language == "it" and not iv["done"]:
                    assert iv["last_feedback"] is None
                for feedback in [iv.get("last_feedback") or {}]:
                    if feedback.get("evidence"):
                        evidence_count += 1
                    degraded += int(bool(feedback.get("degraded")))
            assert iv["done"] and iv["status"] == "completed"
            final = checked(client.post(f"/api/interviews/{iv['id']}/finish", json={"confidence_after": 4}))
            assert final["report"]["averages"] and final["report"]["narrative"]["headline"]
            assert final["usage"]["calls_per_answer"] < 5
            assert client.post(f"/api/interviews/{iv['id']}/answer", json={"answer": "Again"}).status_code == 409
            checked(client.get("/api/progress"))
            checked(client.get("/api/me/export"))
            # A second visitor must not see the first visitor's interview.
            checked(client.post("/api/auth/demo/student"))
            assert client.get(f"/api/interviews/{iv['id']}").status_code == 404
            results.append({"language": language, "answers": final["usage"]["answers"],
                            "model_calls": final["usage"]["llm_calls"],
                            "calls_per_answer": final["usage"]["calls_per_answer"],
                            "degraded_turns": degraded, "feedback_with_evidence": evidence_count,
                            "duration_s": round(time.perf_counter() - started, 2), "passed": True})
            print(json.dumps(results[-1]), flush=True)
    with httpx.Client(base_url=url, timeout=60) as client:
        checked(client.post("/api/auth/demo/teacher"))
        classroom = checked(client.get("/api/classes"))[0]
        overview = checked(client.get(f"/api/classes/{classroom['id']}"))
        assert len(overview["students"]) == 8
        for student in overview["students"]:
            detail = checked(client.get(f"/api/classes/{classroom['id']}/students/{student['id']}"))
            if not student["consent_share"]:
                assert all("detail" not in s for s in detail["sessions"])
        print("Teacher cockpit and transcript consent: passed", flush=True)
    return {"url": url, "languages": results, "teacher_consent": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    report = run(args.url)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
