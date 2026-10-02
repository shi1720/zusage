"""Output validation - the "trust, but verify" layer between Apertus and users.

An 8B model will occasionally return a score of 7, quote words the student
never said, or slip into the wrong language. Every model output passes
through these deterministic checks before a teenager ever sees it:

- scores are clamped to the rubric scale and restricted to targeted criteria;
- the evidence quote must actually occur in the student's answer
  (anti-hallucination: feedback is grounded in what was really said);
- interviewer text must be in the interview language (stop-word detector);
- empty / too long fields fall back to hand-written phrases.
"""

from __future__ import annotations

import re
import unicodedata

from ..knowledge import CRITERIA

_STOP = {
    "de": {"und", "ich", "die", "der", "das", "ist", "nicht", "sie", "es", "mit", "ein", "eine", "zu", "auf",
           "für", "sind", "wie", "haben", "habe", "bei", "uns", "auch", "was", "wir", "dass", "ihre", "ihnen",
           "warum", "würden", "können", "mir", "sehr", "gut", "schön", "danke", "im", "wenn"},
    "gsw": {"isch", "ich", "und", "nöd", "mer", "händ", "gsi", "öppis", "chli", "bitzeli", "wänd", "mached",
            "säged", "gönd", "chönd", "dass", "vo", "mit", "au", "scho", "üs", "wie", "was", "sind", "es", "bi",
            "gärn", "merci", "guet", "wieso", "hät", "wo"},
    "fr": {"et", "je", "le", "la", "les", "est", "pas", "vous", "une", "un", "de", "des", "pour", "que", "qui",
           "dans", "avec", "sur", "votre", "nous", "merci", "bien", "très", "comment", "pourquoi", "êtes", "avez",
           "c'est", "ce", "du", "au"},
    "it": {"e", "io", "il", "la", "le", "è", "non", "lei", "una", "un", "di", "per", "che", "con", "sono", "ha",
           "del", "della", "molto", "grazie", "bene", "come", "perché", "suo", "sua", "nel", "gli", "anche", "ci",
           "mi", "ho"},
    "en": {"and", "i", "the", "is", "not", "you", "a", "an", "of", "to", "for", "that", "with", "are", "your",
           "we", "us", "thank", "thanks", "very", "good", "how", "why", "what", "it", "in", "on", "do", "have"},
}

_WORD = re.compile(r"[\wäöüàâçéèêëîïôûùœ'’]+", re.IGNORECASE)


def detect_lang(text: str) -> str | None:
    """Tiny stop-word language identifier for de / gsw / fr / it / en.

    Good enough to catch the failure that matters (an Italian interview
    suddenly continuing in English); returns None when unsure.
    """
    words = [w.lower().replace("’", "'") for w in _WORD.findall(text or "")]
    if len(words) < 3:
        return None
    scores = {lang: sum(1 for w in words if w in stop) for lang, stop in _STOP.items()}
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] == 0:
        return None
    return best


def lang_ok(text: str, expected: str) -> bool:
    found = detect_lang(text)
    if found is None:
        return True  # too short to judge - don't punish
    if expected in ("de", "gsw"):
        return found in ("de", "gsw")
    return found == expected


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def evidence_in_answer(evidence: str, answer: str) -> bool:
    """Require a contiguous quote, ignoring punctuation and letter case."""
    ev, ans = _norm(evidence), _norm(answer)
    if not ev:
        return False
    return f" {ev} " in f" {ans} "


def clamp_scores(raw: object, targets: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(raw, dict):
        return out
    allowed = set(targets) if targets else set(CRITERIA)
    for key, value in raw.items():
        crit = str(key).strip().lower().replace("-", "_").replace(" ", "_")
        if crit == "selfawareness":
            crit = "self_awareness"
        if crit not in allowed:
            continue
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError, OverflowError):
            continue
        out[crit] = max(1, min(4, score))
    return out


def text_field(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    value = " ".join(value.replace("\u2014", ",").split())
    if len(value) > limit:
        cut = value[:limit]
        value = cut[: cut.rfind(" ")] + "…" if " " in cut else cut
    return value


QUALITIES = {"strong", "solid", "weak", "off_topic", "empty"}
FLAGS = {"none", "distress", "inappropriate", "personal_data"}


_THIRD = re.compile(
    r"\b(der|die) (kandidat|kandidatin|bewerber|bewerberin|lernende)\b|\b(le|la) candidat|\bil candidato|"
    r"\bla candidata|\bthe (candidate|applicant)\b|\b(er|sie) zeigt\b",
    re.IGNORECASE,
)
_SENT = re.compile(r"(?<=[.!?…])\s+")


def third_person(text: str) -> bool:
    """Coach text must talk TO the student, not ABOUT them."""
    return bool(_THIRD.search(text or ""))


def swiss_spelling(text: str) -> str:
    return (text or "").replace("ß", "ss")


def split_questions(text: str) -> tuple[str, list[str]]:
    """Split a text into its statements and its questions."""
    statements, questions = [], []
    for sent in _SENT.split((text or "").strip()):
        if not sent:
            continue
        (questions if sent.rstrip().endswith("?") else statements).append(sent.strip())
    return " ".join(statements), questions


def first_sentences(text: str, n: int) -> str:
    parts = [p for p in _SENT.split((text or "").strip()) if p]
    return " ".join(parts[:n])


def strip_self_address(text: str, persona_name: str) -> str:
    """Remove a leading vocative of the interviewer's own name ("Herr Keller, ...")."""
    if not text or not persona_name:
        return text
    pattern = re.compile(rf"^\s*{re.escape(persona_name)}\s*[,:!.-]\s*", re.IGNORECASE)
    out = pattern.sub("", text)
    return out[:1].upper() + out[1:] if out and out != text else out


def shorten_quote(evidence: str, answer: str, max_words: int = 15) -> str:
    """Whole-answer 'quotes' are useless as evidence: keep the first 12 words."""
    words = (evidence or "").split()
    if len(words) <= max_words:
        return evidence
    return " ".join(words[:12])


_INFORMAL = {
    "de": re.compile(
        r"\b(du|dich|dir|dein|deine|deinen|deinem|deiner|deines|würdest|kannst|hast|bist|willst)\b", re.IGNORECASE
    ),
    "gsw": re.compile(r"\b(du|dich|dir|dis|dini|dim|dinere|chasch|hesch|bisch|wotsch)\b", re.IGNORECASE),
    "fr": re.compile(r"\b(tu|toi|ton|ta|tes|t'as|peux-tu|as-tu|es-tu)\b", re.IGNORECASE),
    "it": re.compile(r"\b(tu|ti|tuo|tua|tuoi|tue|puoi|hai|sei)\b", re.IGNORECASE),
}
_GRADING = re.compile(
    r"\b(vage|zu kurz|mehr details|bleibt unklar|vague|trop court|plus de détails|troppo breve|più dettagli|"
    r"too short|more details|keine konkrete)\b",
    re.IGNORECASE,
)


def formal_ok(text: str, lang: str) -> bool:
    """The interviewer uses the formal register (Sie / vous / Lei)."""
    pattern = _INFORMAL.get(lang)
    return not (pattern and pattern.search(text or ""))


def grades_answer(text: str) -> bool:
    """Interviewers react to content; judging the answer is the coach's job."""
    return bool(_GRADING.search(text or ""))


_FORMAL_COACH = {"fr": re.compile(r"\bvous\b", re.IGNORECASE), "it": re.compile(r"\b(Lei|Suo|Sua|Suoi)\b")}


def informal_ok(text: str, lang: str) -> bool:
    """The coach speaks informally (du / tu) - teens, not job applicants."""
    pattern = _FORMAL_COACH.get(lang)
    return not (pattern and pattern.search(text or ""))
