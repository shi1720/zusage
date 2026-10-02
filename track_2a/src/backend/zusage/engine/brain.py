"""The coach's "brain": a port with two adapters.

- :class:`ApertusBrain`  - Apertus 1.5 via any OpenAI-compatible endpoint.
- :class:`OfflineBrain`  - a transparent, rule-based stand-in (no network).

Both take the same structured inputs and return the same JSON shapes, which
is what lets the whole product, its tests and CI run without credentials,
and lets the evaluation harness compare "Apertus" against a heuristic
baseline on identical inputs (see ``zusage.eval``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

from ..knowledge import Knowledge, feedback_lang
from ..llm.client import ChatClient, Usage
from . import prompts

log = logging.getLogger("zusage.brain")


@dataclass
class TurnInput:
    lang: str
    occupation_id: str
    persona_name: str
    persona_role: str
    persona_style: str
    company: dict
    candidate: dict
    phase: str
    question: str
    targets: list[str]
    probe: str
    followup_allowed: bool
    answer: str
    recent: list[tuple[str, str]] = field(default_factory=list)
    posting: str = ""


@dataclass
class BrainResult:
    data: dict
    usage: Usage
    model: str


class Brain(Protocol):
    name: str
    model: str

    def assess_turn(self, kb: Knowledge, inp: TurnInput) -> BrainResult: ...

    def final_report(self, kb: Knowledge, *, lang: str, occupation_id: str, averages: dict[str, float],
                     turns: list[dict]) -> BrainResult: ...

    def tailor(self, kb: Knowledge, *, lang: str, occupation_id: str, posting: str) -> BrainResult: ...


# ---------------------------------------------------------------------------
# Apertus
# ---------------------------------------------------------------------------


class ApertusBrain:
    name = "apertus"

    def __init__(self, client: ChatClient, max_tokens: int = 900):
        self.client = client
        self.model = client.model
        self.max_tokens = max_tokens

    def assess_turn(self, kb: Knowledge, inp: TurnInput) -> BrainResult:
        system = prompts.turn_system_prompt(
            lang=inp.lang, persona_name=inp.persona_name, persona_role=inp.persona_role,
            persona_style=inp.persona_style, company=inp.company["name"], town=inp.company["town"],
        )
        user = prompts.turn_user_prompt(
            kb, lang=inp.lang, occupation_id=inp.occupation_id, company_facts=list(inp.company["facts"]),
            candidate=inp.candidate, phase=inp.phase, question=inp.question, targets=inp.targets,
            probe=inp.probe, followup_allowed=inp.followup_allowed, recent=inp.recent, answer=inp.answer,
            posting=inp.posting,
        )
        result = self.client.complete_json(system, user, max_tokens=self.max_tokens)
        return BrainResult(result.data, result.usage, result.model)

    def final_report(self, kb: Knowledge, *, lang: str, occupation_id: str, averages: dict[str, float],
                     turns: list[dict]) -> BrainResult:
        occ = kb.occupations[occupation_id]
        result = self.client.complete_json(
            prompts.report_system_prompt(lang),
            prompts.report_user_prompt(occupation_label=occ.label(lang), averages=averages, turns=turns),
            max_tokens=700,
        )
        return BrainResult(result.data, result.usage, result.model)

    def tailor(self, kb: Knowledge, *, lang: str, occupation_id: str, posting: str) -> BrainResult:
        occ = kb.occupations[occupation_id]
        result = self.client.complete_json(
            prompts.tailor_system_prompt(lang),
            prompts.tailor_user_prompt(occupation_label=occ.label(lang), posting=posting),
            max_tokens=300,
        )
        return BrainResult(result.data, result.usage, result.model)


# ---------------------------------------------------------------------------
# Offline (rule-based) - honest, deterministic, multilingual
# ---------------------------------------------------------------------------

_EXAMPLE_MARKERS = (
    "zum beispiel", "z.b.", "z. b.", "als ich", "einmal", "letzten", "letztes", "schnupper", "im lager", "bispiel",
    "won ich", "wo n ich", "wo ich", "par exemple", "une fois", "quand j", "lors de", "pendant mon stage", "stage",
    "per esempio", "una volta", "quando ho", "durante lo stage", "for example", "once", "when i", "last year",
    "during my",
)
_RESULT_MARKERS = (
    "danach", "dann", "deshalb", "gelernt", "geschafft", "resultat", "ergebnis", "alors", "ensuite", "appris",
    "résultat", "réussi", "poi", "quindi", "imparato", "risultato", "riuscit", "then", "learned", "result",
    "managed", "so that",
)
_MOTIVATION_MARKERS = (
    "weil", "interess", "gefällt", "gfallt", "spass", "freude", "fasziniert", "parce que", "intéress", "plaît",
    "passion", "aime", "perché", "interess", "piace", "passione", "because", "interested", "enjoy", "love", "like",
)
_SELF_MARKERS = (
    "stärke", "schwäche", "verbesser", "manchmal", "ungeduld", "zuverlässig", "force", "faiblesse", "améliorer",
    "parfois", "punto di forza", "debolezza", "miglior", "a volte", "strength", "weakness", "improve", "sometimes",
)
_IMPOLITE = ("scheiss", "egal", "keine ahnung", "kei ahnig", "putain", "m'en fous", "boh", "cazzo", "whatever")

_T = {
    "strength": {
        "de": "Gut: Du hast mit «{q}» eine klare Aussage gemacht.",
        "fr": "Bien : avec « {q} », tu as fait une affirmation claire.",
        "it": "Bene: con «{q}» hai detto qualcosa di chiaro.",
        "en": "Good: with “{q}” you made a clear statement.",
    },
    "strength_effort": {
        "de": "Gut, dass du geantwortet hast - jeder Versuch ist Training.",
        "fr": "C'est bien d'avoir répondu - chaque essai est un entraînement.",
        "it": "Bene che tu abbia risposto: ogni tentativo è allenamento.",
        "en": "Good that you answered - every attempt is practice.",
    },
    "tip": {
        "examples": {
            "de": "Nenne ein konkretes Beispiel: wann, wo, was hast DU gemacht und was kam dabei heraus?",
            "fr": "Donne un exemple concret : quand, où, qu'as-TU fait et quel a été le résultat ?",
            "it": "Fai un esempio concreto: quando, dove, cosa hai fatto TU e qual è stato il risultato?",
            "en": "Give one concrete example: when, where, what did YOU do and what was the result?",
        },
        "motivation": {
            "de": "Erkläre, WARUM dich dieser Beruf interessiert - am besten mit einem Erlebnis aus der Schnupperlehre.",
            "fr": "Explique POURQUOI ce métier t'intéresse - idéalement avec une expérience de ton stage.",
            "it": "Spiega PERCHÉ questa professione ti interessa, magari con un'esperienza dello stage.",
            "en": "Explain WHY this job interests you - ideally with something you experienced in a trial day.",
        },
        "clarity": {
            "de": "Starte mit deiner Hauptaussage in einem Satz und begründe sie dann.",
            "fr": "Commence par ton message principal en une phrase, puis justifie-le.",
            "it": "Inizia con il tuo messaggio principale in una frase, poi motivalo.",
            "en": "Start with your main point in one sentence, then give your reason.",
        },
        "self_awareness": {
            "de": "Nenne eine echte Stärke oder Schwäche und sag, was du konkret daran arbeitest.",
            "fr": "Cite une vraie force ou faiblesse et dis ce que tu fais concrètement pour progresser.",
            "it": "Indica un vero punto di forza o debolezza e cosa fai concretamente per migliorare.",
            "en": "Name a real strength or weakness and say what you actually do to work on it.",
        },
        "communication": {
            "de": "Antworte in ganzen, höflichen Sätzen - so wirkst du sicherer.",
            "fr": "Réponds en phrases complètes et polies - tu paraîtras plus sûr·e de toi.",
            "it": "Rispondi con frasi complete e cortesi: sembrerai più sicuro/a.",
            "en": "Answer in full, polite sentences - you'll come across as more confident.",
        },
        "relevance": {
            "de": "Bleib bei der Frage und verbinde deine Antwort mit der Lehrstelle.",
            "fr": "Reste sur la question et relie ta réponse à la place d'apprentissage.",
            "it": "Resta sulla domanda e collega la risposta al posto di apprendistato.",
            "en": "Stay on the question and connect your answer to the apprenticeship.",
        },
    },
    "better": {
        "de": "Ich interessiere mich sehr für diesen Beruf, weil [dein Grund]. Zum Beispiel habe ich in [Situation] "
        "[was du gemacht hast], und dabei habe ich gemerkt, dass [was du gelernt hast].",
        "fr": "Ce métier m'intéresse beaucoup parce que [ta raison]. Par exemple, pendant [situation], j'ai "
        "[ce que tu as fait] et j'ai remarqué que [ce que tu as appris].",
        "it": "Questa professione mi interessa molto perché [il tuo motivo]. Per esempio, durante [situazione] ho "
        "[cosa hai fatto] e ho capito che [cosa hai imparato].",
        "en": "I'm really interested in this job because [your reason]. For example, during [situation] I "
        "[what you did], and I realised that [what you learned].",
    },
    "follow_up": {
        "de": "Können Sie mir dazu ein konkretes Beispiel geben?",
        "fr": "Pouvez-vous me donner un exemple concret ?",
        "it": "Può farmi un esempio concreto?",
        "en": "Could you give me a concrete example of that?",
        "gsw": "Chönd Sie mir döt es konkrets Bispiel gäh?",
    },
    "candidate_answer": {
        "de": "Gute Frage! Das kläre ich gerne genau ab und melde mich bei Ihnen.",
        "fr": "Bonne question ! Je vais me renseigner précisément et je reviendrai vers vous.",
        "it": "Bella domanda! Mi informo con precisione e le faccio sapere.",
        "en": "Good question! I'll check the details and get back to you.",
        "gsw": "Gueti Frag! Das kläri gern ab und mälde mich bi Ihne.",
    },
}


def _has(text: str, markers: tuple[str, ...]) -> bool:
    return any(m in text for m in markers)


def _first_words(answer: str, n: int = 8) -> str:
    words = answer.split()
    return " ".join(words[:n])


class OfflineBrain:
    """Rule-based coach used when no Apertus endpoint is configured.

    It is intentionally simple and fully transparent - and it doubles as the
    heuristic BASELINE in the evaluation harness, so we can show how much
    Apertus adds over keyword rules.
    """

    name = "offline"
    model = "rule-based-baseline"

    def assess_turn(self, kb: Knowledge, inp: TurnInput) -> BrainResult:
        answer = inp.answer.strip()
        low = answer.lower()
        words = len(re.findall(r"\w+", answer))
        flang = feedback_lang(inp.lang)
        has_example = _has(low, _EXAMPLE_MARKERS)
        has_result = _has(low, _RESULT_MARKERS)
        impolite = _has(low, _IMPOLITE)

        if words == 0:
            quality = "empty"
        elif words < 6:
            quality = "weak"
        elif words >= 35 and has_example:
            quality = "strong"
        else:
            quality = "solid" if words >= 15 else "weak"

        base = 1 if words < 6 else 2 if words < 15 else 3
        raw = {
            "clarity": base if words < 120 else 2,
            "relevance": base,
            "motivation": min(4, base + (1 if _has(low, _MOTIVATION_MARKERS) else -1)),
            "self_awareness": min(4, base + (1 if _has(low, _SELF_MARKERS) else -1)),
            "communication": max(1, (base + (1 if words >= 25 else 0)) - (2 if impolite else 0)),
            "examples": (4 if has_result and words >= 30 else 3) if has_example else (1 if words < 15 else 2),
        }
        scores = {c: max(1, min(4, raw[c])) for c in inp.targets}

        weakest = min(scores, key=scores.get) if scores else "clarity"
        followup = ""
        if inp.followup_allowed and inp.phase not in ("candidate_questions", "intro") and (
            words < 12 or not has_example
        ):
            followup = _T["follow_up"].get(inp.lang) or _T["follow_up"]["en"]

        bridge = ""
        if inp.phase == "candidate_questions" and "?" in answer:
            bridge = _T["candidate_answer"].get(inp.lang) or _T["candidate_answer"]["en"]

        data = {
            "scores": scores,
            "evidence": _first_words(answer) if words >= 3 else "",
            "strength": (_T["strength"][flang].format(q=_first_words(answer, 6)) if words >= 6
                         else _T["strength_effort"][flang]),
            "tip": _T["tip"][weakest][flang],
            "better_answer": _T["better"][flang],
            "quality": quality,
            "follow_up": followup,
            "bridge": bridge,
            "flag": "none",
        }
        return BrainResult(data, Usage(), self.model)

    def final_report(self, kb: Knowledge, *, lang: str, occupation_id: str, averages: dict[str, float],
                     turns: list[dict]) -> BrainResult:
        flang = feedback_lang(lang)
        ranked = sorted(averages.items(), key=lambda kv: kv[1], reverse=True)
        top = [kb.criterion_name(c, flang) for c, _ in ranked[:2]]
        low = [c for c, _ in ranked[-2:]][::-1]
        texts = {
            "de": ("Du bist auf einem guten Weg!", "Du hast das ganze Gespräch durchgezogen. Am stärksten warst du "
                   "bei {a} und {b}.", "Deine Stärke: {x}.", "Ich gebe dir dieses Feedback, weil ich weiss, dass "
                   "du das Niveau für eine Zusage erreichen kannst."),
            "fr": ("Tu es sur la bonne voie !", "Tu as mené tout l'entretien jusqu'au bout. Tes points les plus forts : "
                   "{a} et {b}.", "Ta force : {x}.", "Je te donne ce retour parce que je sais que tu peux atteindre "
                   "le niveau pour décrocher ta place."),
            "it": ("Sei sulla buona strada!", "Hai portato a termine tutto il colloquio. I tuoi punti più forti: "
                   "{a} e {b}.", "Il tuo punto di forza: {x}.", "Ti do questo feedback perché so che puoi "
                   "raggiungere il livello per ottenere il posto."),
            "en": ("You're on a good path!", "You went through the whole interview. You were strongest at {a} and "
                   "{b}.", "Your strength: {x}.", "I'm giving you this feedback because I know you can reach the "
                   "level needed to get the offer."),
        }[flang]
        data = {
            "headline": texts[0],
            "summary": texts[1].format(a=top[0], b=top[-1]),
            "strengths": [texts[2].format(x=name) for name in top],
            "goals": [{"title": kb.criterion_name(c, flang), "how": _T["tip"][c][flang]} for c in low],
            "best_moment": "",
            "wise_feedback": texts[3],
        }
        return BrainResult(data, Usage(), self.model)

    def tailor(self, kb: Knowledge, *, lang: str, occupation_id: str, posting: str) -> BrainResult:
        return BrainResult({"questions": []}, Usage(), self.model)


def build_brain(settings) -> Brain:
    if settings.llm_enabled:
        client = ChatClient(
            settings.llm_base_url, settings.llm_api_key, settings.llm_name,
            timeout_s=settings.llm_timeout_s, temperature=settings.llm_temperature,
            json_mode=settings.llm_json_mode,
            max_retries=settings.llm_max_retries,
        )
        return ApertusBrain(client, max_tokens=settings.llm_max_tokens)
    return OfflineBrain()
