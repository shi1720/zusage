"""Deterministic interviewer phrases in every supported language.

These are the "safety net" of the conversation: greetings, transitions and
the fallback acknowledgements used whenever the model output is unusable.
Because they are hand-written, the interview can never break language or
register, even if the LLM fails mid-session.
"""

from __future__ import annotations

import random

GREETING = {
    "de": "Grüezi {first_name}! Ich bin {persona}, {role} bei {company} in {town}. Schön, dass Sie da sind. "
    "Wir sprechen heute über Ihre Bewerbung als {occupation}.",
    "fr": "Bonjour {first_name} ! Je suis {persona}, {role} chez {company} à {town}. Merci d'être venu·e. "
    "Nous allons parler aujourd'hui de votre candidature comme {occupation}.",
    "it": "Buongiorno {first_name}! Sono {persona}, {role} presso {company} a {town}. Grazie di essere qui. "
    "Oggi parliamo della sua candidatura come {occupation}.",
    "en": "Hello {first_name}! I'm {persona}, {role} at {company} in {town}. Thanks for coming in. "
    "Today we'll talk about your application as {occupation}.",
    "gsw": "Grüezi {first_name}! Ich bi {persona}, {role} bi {company} in {town}. Schön, sind Sie da. "
    "Mir redet hüt über Ihri Bewerbig als {occupation}.",
}

# Short, neutral acknowledgements - used when the model's bridge is unusable.
ACKS = {
    "de": ["Danke.", "Okay, verstehe.", "Danke für Ihre Antwort.", "Gut, danke."],
    "fr": ["Merci.", "D'accord, je comprends.", "Merci pour votre réponse.", "Bien, merci."],
    "it": ["Grazie.", "D'accordo, capisco.", "Grazie per la risposta.", "Bene, grazie."],
    "en": ["Thank you.", "Okay, I see.", "Thanks for your answer.", "Good, thank you."],
    "gsw": ["Merci.", "Okay, verstah.", "Merci für Ihri Antwort.", "Guet, merci."],
}

EMPTY_REPROMPT = {
    "de": "Kein Problem, nehmen Sie sich Zeit. Möchten Sie es noch einmal versuchen?",
    "fr": "Pas de souci, prenez votre temps. Voulez-vous essayer encore une fois ?",
    "it": "Nessun problema, si prenda il suo tempo. Vuole riprovare?",
    "en": "No problem, take your time. Would you like to try again?",
    "gsw": "Kei Problem, nämed Sie sich Ziit. Wänd Sie's nomal probiere?",
}

# Shown (never spoken by the interviewer persona) when an answer suggests the
# young person may be in distress. 147 is Pro Juventute's free, confidential
# 24/7 helpline for children and young people in Switzerland.
SAFETY_MESSAGE = {
    "de": "Kurze Pause vom Training: Es klingt, als ginge es dir gerade nicht gut. Das ist wichtiger als jedes "
    "Vorstellungsgespräch. Du kannst jederzeit gratis und vertraulich mit Pro Juventute sprechen: Telefon 147 "
    "oder 147.ch (Chat, WhatsApp, SMS). Sprich auch mit einer Lehrperson oder einer Person, der du vertraust.",
    "fr": "Petite pause dans l'entraînement : on dirait que ça ne va pas très bien pour toi en ce moment. C'est plus "
    "important que n'importe quel entretien. Tu peux parler gratuitement et en toute confidentialité avec Pro "
    "Juventute : téléphone 147 ou 147.ch (chat, WhatsApp, SMS). Parles-en aussi à un·e enseignant·e ou à une "
    "personne de confiance.",
    "it": "Una piccola pausa dall'allenamento: sembra che tu in questo momento non stia bene. Questo è più importante "
    "di qualsiasi colloquio. Puoi parlare gratuitamente e in modo confidenziale con Pro Juventute: telefono 147 "
    "o 147.ch (chat, WhatsApp, SMS). Parlane anche con un/a docente o con una persona di fiducia.",
    "en": "A short break from training: it sounds like you're not doing well right now. That matters more than any "
    "interview. In Switzerland you can talk to Pro Juventute for free and confidentially: call 147 or visit "
    "147.ch (chat, WhatsApp, SMS). Please also talk to a teacher or someone you trust.",
}

PERSONAL_DATA_NOTE = {
    "de": "Tipp: Hier im Training brauchst du keine echten Adressen, Telefonnummern oder Gesundheitsdaten anzugeben.",
    "fr": "Astuce : ici, à l'entraînement, tu n'as pas besoin de donner de vraies adresses, numéros ou données de santé.",
    "it": "Consiglio: qui durante l'allenamento non serve indicare indirizzi, numeri di telefono o dati sanitari reali.",
    "en": "Tip: in training you never need to share real addresses, phone numbers or health details.",
}

CLOSING_FALLBACK = {
    "de": "Vielen Dank für das Gespräch!",
    "fr": "Merci beaucoup pour cet entretien !",
    "it": "Grazie mille per il colloquio!",
    "en": "Thank you very much for the conversation!",
    "gsw": "Merci vilmal für das Gspräch!",
}


def pick_ack(lang: str, seed: int) -> str:
    options = ACKS.get(lang) or ACKS["de"]
    return random.Random(seed).choice(options)


def greeting(lang: str, **kw: str) -> str:
    template = GREETING.get(lang) or GREETING["en"]
    if not kw.get("first_name"):
        template = template.replace(" {first_name}", "")
    return template.format(**kw)


def localized(table: dict[str, str], lang: str) -> str:
    return table.get(lang) or table.get("de" if lang == "gsw" else "en") or table["en"]
