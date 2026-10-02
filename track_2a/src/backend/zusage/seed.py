"""Demo workspace seed - a realistic Sek-I class, generated, not hand-planted.

The seed runs every demo student through *real* interviews with the
scripted candidates from ``data/eval/answer_bank.yaml`` and the offline
coach - the exact engine code path a live session takes - so dashboards,
progress charts, drills and the teacher cockpit show genuine engine output.

Everything here is fictional and labelled as demo data in the UI.
Disable with ``ZUSAGE_SEED_DEMO=false`` for production deployments.
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, select

from .db import Application, Classroom, Interview, StudentProfile, User, utcnow
from .engine import core
from .engine.brain import OfflineBrain
from .eval.scripted import answer_for, followup_answer, load_bank
from .knowledge import Knowledge
from .learning import schedule_drills
from .security import hash_password

log = logging.getLogger("zusage.seed")

DEMO_PASSWORD = os.environ.get("ZUSAGE_DEMO_PASSWORD", "zusage-demo")
CLASS_CODE = "CHUR26"

# (username, consent, level schedule per past session, confidence (before, after) per session)
_STUDENT_PLAN = {
    "lea": (True, [["weak", "weak", "solid"], ["solid", "weak", "solid"], ["solid", "strong", "solid"]],
            [(2, 3), (2, 3), (3, 4)]),
    "noah": (True, [["solid", "strong", "solid"], ["strong", "solid", "strong"]], [(4, 4), (4, 5)]),
    "elif": (False, [["weak", "solid", "weak"], ["solid", "solid", "weak"]], [(3, 3), (3, 4)]),
    "luca": (True, [["weak", "weak", "weak"]], [(1, 2)]),
    "chloe": (True, [["solid", "solid", "strong"], ["strong", "strong", "solid"]], [(3, 4), (4, 4)]),
    "amar": (False, [["weak", "solid", "solid"], ["solid", "solid", "strong"], ["solid", "strong", "strong"]],
             [(2, 3), (3, 4), (3, 4)]),
    "mara": (True, [["strong", "strong", "solid"]], [(4, 4)]),
    "giulia": (False, [], []),
}

_APPS = {
    "lea": [
        ("Pflegezentrum Calanda", "fage_efz", "Chur", "interview", 3, 4),
        ("Spital Limmattal-Ost", "fage_efz", "Zürich", "applied", None, 13),
        ("Spitex Prättigau", "fage_efz", "Schiers", "schnupper", None, 2),
        ("Klinik Sonnmatt", "fage_efz", "Chur", "rejected", None, 20),
    ],
    "noah": [("Alpina Software AG", "informatik_efz", "St. Gallen", "offer", None, 3),
             ("Bodensee Digital GmbH", "informatik_efz", "Rorschach", "interview", 6, 5)],
    "elif": [("Velo & Sport Aare GmbH", "detailhandel_efz", "Bern", "applied", None, 11),
             ("Modehaus Töss", "detailhandel_efz", "Winterthur", "schnupper", None, 4)],
    "luca": [("Transalpin Logistik AG", "logistik_eba", "Bellinzona", "applied", None, 15)],
    "chloe": [("Garage du Léman SA", "automech_efz", "Lausanne", "interview", 9, 3)],
    "amar": [("Hotel Lago Ceresio", "koch_efz", "Lugano", "applied", None, 6),
             ("Restaurant Zytglogge", "koch_efz", "Bern", "offer", None, 2)],
    "mara": [("Rhätia Treuhand AG", "kaufmann_efz", "Chur", "interview", 2, 1)],
    "giulia": [("Kita Sunnehuus", "fabe_efz", "Luzern", "interested", None, 1)],
}

LEA_POSTING = """Lehrstelle Fachfrau/Fachmann Gesundheit EFZ (Start August)
Pflegezentrum Calanda, Chur - 120 Bewohnerinnen und Bewohner, familiäres Team
Du begleitest ältere Menschen im Alltag, unterstützt bei der Körperpflege und beim Essen.
Du misst Blutdruck und Puls und dokumentierst deine Beobachtungen.
Wir bieten: eigene Lernendenbetreuung, Lernendenausflug, 6 Wochen Ferien.
Du bist: einfühlsam, zuverlässig, teamfähig und hast Freude am Umgang mit älteren Menschen."""


FIXTURE = Path("demo") / "seed_sessions.json"


def _load_fixtures(data_dir: str) -> dict:
    """Recorded Apertus sessions (``zusage record-seed``) make the demo class show
    real model feedback even when the server runs without an LLM endpoint."""
    path = Path(data_dir) / FIXTURE
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def session_plan(kb: Knowledge) -> list[tuple[str, int, dict, list[str]]]:
    """(username, index, setup, level schedule) for every seeded session."""
    plan = []
    for profile in kb.profiles:
        _consent, schedules, _conf = _STUDENT_PLAN.get(profile["id"], (False, [], []))
        for k, schedule in enumerate(schedules):
            setup = {
                "language": profile["language"],
                "occupation_id": profile["target"],
                "persona_id": ["warm", "structured", "direct"][min(k, 2)],
                "mode": "training",
                "length": "full" if k % 2 == 0 else "quick",
                "candidate": {"first_name": profile["first_name"], "age": profile["age"],
                              "school": profile["school"], "hobbies": profile["hobbies"],
                              "experience": profile["experience"]},
            }
            plan.append((profile["id"], k, setup, schedule))
    return plan


def _run_scripted(kb: Knowledge, bank: dict, setup: dict, schedule: list[str], seed: int, brain=None) -> dict:
    brain = brain or OfflineBrain()
    state = core.start(kb, brain, setup, seed=seed)
    i = 0
    while not state.get("done"):
        level = schedule[min(i * len(schedule) // 9, len(schedule) - 1)] if schedule else "solid"
        current = state["current"]
        if current.get("is_followup"):
            answer = followup_answer(bank, setup["language"], level)
            if current["phase"] == "candidate_questions":
                answer = {"de": "Nein, danke, das war alles.", "fr": "Non merci, c'est tout.",
                          "it": "No grazie, è tutto.", "gsw": "Nei, merci, das wär's.",
                          "en": "No, thank you, that's all."}[setup["language"]]
        else:
            answer = answer_for(bank, current["qid"], current["phase"], setup["language"], level)
        state = core.step(kb, brain, state, answer or "Ja.")
        i += 1
    return core.finish(kb, brain, state)


def seed_demo(engine, kb: Knowledge, data_dir: str) -> None:
    with Session(engine) as session:
        if session.exec(select(User).where(User.username == "frau.meier")).first():
            return
        log.info("seeding demo workspace (class code %s)", CLASS_CODE)
        rng = random.Random(26)
        now = utcnow()
        bank = load_bank(data_dir)
        fixtures = _load_fixtures(data_dir)
        pw = hash_password(DEMO_PASSWORD)

        teacher = User(username="frau.meier", display_name="Frau Meier", password_hash=pw, role="teacher",
                       onboarded=True)
        session.add(teacher)
        classroom = Classroom(name="3. Sek A", school="Oberstufe Chur (Demo)", teacher_id=teacher.id, code=CLASS_CODE)
        session.add(classroom)

        for profile in kb.profiles:
            username = profile["id"]
            consent, schedules, confidence = _STUDENT_PLAN.get(username, (False, [], []))
            student = User(username=username, display_name=profile["first_name"], password_hash=pw, role="student",
                           ui_lang="de" if profile["language"] == "gsw" else profile["language"],
                           class_id=classroom.id, consent_share=consent, onboarded=True)
            session.add(student)
            stories = [{"title": "Schnupperlehre", "text": profile["experience"]}]
            session.add(StudentProfile(user_id=student.id, data={
                "age": profile["age"], "school": profile["school"], "canton": profile["canton"],
                "hobbies": profile["hobbies"], "experience": profile["experience"], "stories": stories,
                "target_occupation_id": profile["target"], "interview_language": profile["language"],
            }))

            n = len(schedules)
            plans = [p for p in session_plan(kb) if p[0] == username]
            for _user, k, setup, schedule in plans:
                days_ago = (n - k) * 6 + rng.randint(0, 2)
                recorded = fixtures.get(f"{username}:{k}")
                state = recorded["state"] if recorded else _run_scripted(kb, bank, setup, schedule,
                                                                         seed=k + len(username))
                created = now - timedelta(days=days_ago, hours=rng.randint(1, 8))
                report = state["report"]
                iv = Interview(
                    user_id=student.id, occupation_id=profile["target"], language=profile["language"],
                    persona_id=setup["persona_id"], mode="training", length=setup["length"], status="completed",
                    state=state, report=report, overall=report["overall"],
                    confidence_before=confidence[k][0], confidence_after=confidence[k][1],
                    answers=len(state["turns"]), model=recorded["model"] if recorded else "demo-seed (rule-based)",
                    created_at=created,
                    completed_at=created + timedelta(minutes=14),
                )
                session.add(iv)
                schedule_drills(session, iv, now=created)

            for company, occ_id, town, status, interview_in, updated_ago in _APPS.get(username, []):
                updated = now - timedelta(days=updated_ago)
                app = Application(
                    user_id=student.id, company=company, occupation_id=occ_id, town=town, status=status,
                    title=kb.occupations[occ_id].label("de"),
                    posting=LEA_POSTING if company == "Pflegezentrum Calanda" else "",
                    interview_at=(now + timedelta(days=interview_in)).replace(hour=14, minute=0, second=0,
                                                                            microsecond=0)
                    if interview_in else None,
                    contact_name="Frau Casutt" if company == "Pflegezentrum Calanda" else "",
                    history=[{"to": "interested", "at": (updated - timedelta(days=10)).isoformat()},
                             {"from": "interested", "to": status, "at": updated.isoformat()}],
                    created_at=updated - timedelta(days=10), updated_at=updated,
                )
                session.add(app)
        session.commit()
