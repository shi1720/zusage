"""Scripted candidates: deterministic answers from ``data/eval/answer_bank.yaml``.

A scripted candidate answers every question at a fixed quality level
(weak / solid / strong) - or following a level *schedule*, e.g. a student who
starts nervous and warms up. Because the answers are fixed, a full interview
is reproducible, and the coach's scores can be checked against the gold
quality level without any LLM judge.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

LEVELS = ("weak", "solid", "strong")
LEVEL_VALUE = {"weak": 1, "solid": 2, "strong": 3}


@lru_cache
def load_bank(data_dir: str) -> dict:
    with open(Path(data_dir) / "eval" / "answer_bank.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["answers"]


def answer_for(bank: dict, qid: str, phase: str, lang: str, level: str) -> str:
    """Pick the scripted answer; fall back by phase, then by language."""
    keys = [qid]
    if phase == "situational" or qid.startswith("posting_2"):
        keys.append("_situational")
    if phase == "motivation":
        keys.append("_motivation")
    keys.append("_situational")
    for lang_try in (lang, "de" if lang == "gsw" else lang, "de"):
        for key in keys:
            entry = bank.get(key, {}).get(lang_try)
            if entry and entry.get(level):
                return entry[level]
    return ""


def followup_answer(bank: dict, lang: str, level: str) -> str:
    return answer_for(bank, "_situational", "situational", lang, level)
