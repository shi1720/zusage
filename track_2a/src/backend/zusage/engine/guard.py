"""Deterministic input guard - runs BEFORE any model call.

Users are minors. Some signals must never depend on an 8B model noticing
them, so a keyword pre-screen catches acute distress and obvious sensitive
personal data in all four languages. The model's own ``flag`` field is a
second, independent layer (defence in depth).
"""

from __future__ import annotations

import re

_DISTRESS = [
    # de / gsw
    r"\bumbringen\b", r"\bsuizid", r"\bselbstmord", r"\bnicht mehr leben\b", r"\bnümme läbe\b",
    r"\britz(e|en)\b.*\barm", r"\bmich (selbst )?verletz", r"\bwerde (zu hause )?geschlagen\b",
    r"\bwill sterben\b", r"\bwott sterbe\b",
    # fr
    r"\bme suicider\b", r"\bsuicide\b", r"\bme tuer\b", r"\bplus envie de vivre\b", r"\bme faire du mal\b",
    r"\bje veux mourir\b",
    # it
    r"\bsuicid", r"\buccidermi\b", r"\bnon voglio più vivere\b", r"\bfarmi del male\b", r"\bvoglio morire\b",
    # en
    r"\bkill myself\b", r"\bsuicid", r"\bwant to die\b", r"\bhurt myself\b", r"\bself[- ]harm",
]
_DISTRESS_RE = re.compile("|".join(_DISTRESS), re.IGNORECASE)

_PHONE_RE = re.compile(r"(\+41|0041|\b0)\s?\(?\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b")
_AHV_RE = re.compile(r"\b756[.\s]?\d{4}[.\s]?\d{4}[.\s]?\d{2}\b")  # Swiss social security number
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_IBAN_RE = re.compile(r"\bCH\d{2}\s?(\d{4}\s?){4}\d\b", re.IGNORECASE)


def screen(answer: str) -> str:
    """Return 'distress' | 'personal_data' | 'none'."""
    if _DISTRESS_RE.search(answer or ""):
        return "distress"
    if any(p.search(answer or "") for p in (_PHONE_RE, _AHV_RE, _EMAIL_RE, _IBAN_RE)):
        return "personal_data"
    return "none"


def redact(answer: str) -> str:
    """Mask contact / ID data before it is stored or sent to the model
    (data minimisation under the Swiss FADP)."""
    text = _AHV_RE.sub("[AHV-Nr.]", answer or "")
    text = _IBAN_RE.sub("[IBAN]", text)
    text = _EMAIL_RE.sub("[E-Mail]", text)
    return _PHONE_RE.sub("[Telefon]", text)
