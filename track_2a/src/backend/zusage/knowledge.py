"""The Swiss VET knowledge base: rubric, question bank, occupations, personas.

Everything the coach "knows" about Swiss apprenticeship interviews lives in
human-editable YAML under ``data/`` - so a vocational counsellor can add an
occupation or sharpen a rubric anchor without touching Python. This module
loads and validates it once, and exposes typed accessors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

LANGS = ("de", "fr", "it", "en", "gsw")
UI_LANGS = ("de", "fr", "it", "en")
CRITERIA = ("clarity", "relevance", "motivation", "self_awareness", "communication", "examples")
PHASES = ("intro", "motivation", "strengths", "situational", "candidate_questions", "closing")

LANGUAGE_NAMES = {
    "de": "Standard German (Swiss spelling: use 'ss', never 'ß')",
    "fr": "French",
    "it": "Italian",
    "en": "English",
    "gsw": "Swiss German dialect (Zurich-style Mundart, as written in WhatsApp)",
}


def feedback_lang(lang: str) -> str:
    """Coach feedback is written in the standard language of the region.
    Dialect interviews get feedback in Standard German (what schools teach)."""
    return "de" if lang == "gsw" else lang


@dataclass(frozen=True)
class Question:
    id: str
    phase: str
    difficulty: int
    targets: tuple[str, ...]
    probe: str
    text: dict[str, str]

    def in_lang(self, lang: str) -> str:
        return self.text.get(lang) or self.text.get(feedback_lang(lang)) or self.text["en"]


@dataclass(frozen=True)
class Company:
    name: str
    town: str
    facts: tuple[str, ...]


@dataclass(frozen=True)
class Occupation:
    id: str
    level: str
    field: str
    icon: str
    name: dict[str, str]
    competencies: tuple[str, ...]
    company: Company
    questions: tuple[Question, ...]

    def label(self, lang: str) -> str:
        return self.name.get(feedback_lang(lang)) or self.name["de"]


@dataclass(frozen=True)
class Persona:
    id: str
    difficulty: int
    avatar: str
    name: dict[str, str]
    role: dict[str, str]
    style: str

    def display_name(self, lang: str) -> str:
        return self.name.get(lang) or self.name["de"]

    def display_role(self, lang: str) -> str:
        return self.role.get(feedback_lang(lang)) or self.role["en"]


@dataclass(frozen=True)
class Knowledge:
    rubric: dict
    questions: tuple[Question, ...]
    occupations: dict[str, Occupation]
    personas: dict[str, Persona]
    profiles: tuple[dict, ...] = field(default_factory=tuple)

    def criterion_name(self, criterion: str, lang: str) -> str:
        names = self.rubric["criteria"][criterion]["name"]
        return names.get(feedback_lang(lang)) or names["en"]

    def anchors(self, criterion: str, phase: str | None = None) -> dict[int, str]:
        override = (self.rubric.get("phase_anchors") or {}).get(phase or "", {}).get(criterion)
        source = override or self.rubric["criteria"][criterion]["anchors"]
        return {int(k): v for k, v in source.items()}

    def question(self, qid: str, occupation_id: str | None = None) -> Question | None:
        pool = list(self.questions)
        if occupation_id and occupation_id in self.occupations:
            pool += list(self.occupations[occupation_id].questions)
        else:
            for occ in self.occupations.values():
                pool += list(occ.questions)
        return next((q for q in pool if q.id == qid), None)


def _question(raw: dict) -> Question:
    targets = tuple(raw.get("targets") or ())
    unknown = set(targets) - set(CRITERIA)
    if unknown:
        raise ValueError(f"question {raw['id']}: unknown criteria {unknown}")
    if raw["phase"] not in PHASES:
        raise ValueError(f"question {raw['id']}: unknown phase {raw['phase']}")
    missing = [lang for lang in LANGS if not raw["text"].get(lang)]
    if missing:
        raise ValueError(f"question {raw['id']}: missing languages {missing}")
    return Question(
        id=raw["id"],
        phase=raw["phase"],
        difficulty=int(raw.get("difficulty", 1)),
        targets=targets,
        probe=raw.get("probe", ""),
        text=dict(raw["text"]),
    )


def load_knowledge(data_dir: str | Path) -> Knowledge:
    base = Path(data_dir)

    def read(name: str) -> dict:
        with open(base / name, encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    rubric = read("rubric.yaml")
    if set(rubric["criteria"]) != set(CRITERIA):
        raise ValueError("rubric.yaml must define exactly the six FHGR criteria")

    questions = tuple(_question(q) for q in read("questions.yaml")["questions"])

    occupations: dict[str, Occupation] = {}
    for raw in read("occupations.yaml")["occupations"]:
        company = raw["company"]
        occupations[raw["id"]] = Occupation(
            id=raw["id"],
            level=raw["level"],
            field=raw["field"],
            icon=raw.get("icon", "briefcase"),
            name=dict(raw["name"]),
            competencies=tuple(raw.get("competencies", ())),
            company=Company(company["name"], company["town"], tuple(company["facts"])),
            questions=tuple(_question(q) for q in raw.get("questions", ())),
        )

    personas = {
        raw["id"]: Persona(
            id=raw["id"],
            difficulty=int(raw["difficulty"]),
            avatar=raw.get("avatar", ""),
            name=dict(raw["name"]),
            role=dict(raw["role"]),
            style=" ".join(raw["style"].split()),
        )
        for raw in read("personas.yaml")["personas"]
    }

    profiles_path = base / "profiles.yaml"
    profiles = tuple(read("profiles.yaml")["profiles"]) if profiles_path.exists() else ()

    ids = [q.id for q in questions] + [q.id for o in occupations.values() for q in o.questions]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate question ids: {dupes}")

    return Knowledge(rubric, questions, occupations, personas, profiles)


@lru_cache
def get_knowledge(data_dir: str) -> Knowledge:
    return load_knowledge(data_dir)
