from zusage.engine import guard, validate
from zusage.llm.client import extract_json


def test_language_detection():
    assert validate.detect_lang("Warum möchten Sie gerade diese Lehre machen und was gefällt Ihnen?") == "de"
    assert validate.detect_lang("Pourquoi souhaitez-vous faire cet apprentissage chez nous ?") == "fr"
    assert validate.detect_lang("Perché desidera fare proprio questo apprendistato da noi?") == "it"
    assert validate.detect_lang("Why do you want to do this apprenticeship with us?") == "en"
    assert validate.detect_lang("Wieso wänd Sie grad die Lehr mache, isch das öppis für Sie?") in ("gsw", "de")
    assert validate.lang_ok("ok", "fr")  # too short to judge → never punished
    assert not validate.lang_ok("Why do you want to do this apprenticeship with us?", "it")


def test_evidence_must_occur_in_answer():
    answer = "In der Schnupperlehre habe ich einer Frau beim Essen geholfen."
    assert validate.evidence_in_answer("einer Frau beim Essen geholfen", answer)
    assert validate.evidence_in_answer("Einer frau, beim essen geholfen!", answer)
    assert not validate.evidence_in_answer("ich arbeite gerne im Team", answer)
    assert not validate.evidence_in_answer("", answer)


def test_scores_are_clamped_and_restricted():
    scores = validate.clamp_scores({"Clarity": 7, "self-awareness": "2", "motivation": 0, "bogus": 3},
                                   ["clarity", "self_awareness", "motivation"])
    assert scores == {"clarity": 4, "self_awareness": 2, "motivation": 1}
    assert validate.clamp_scores("nonsense", ["clarity"]) == {}


def test_extract_json_is_tolerant():
    assert extract_json('Sure! ```json\n{"a": 1,}\n```') == {"a": 1}
    assert extract_json('prefix {"a": {"b": "x}y"}} suffix') == {"a": {"b": "x}y"}}
    assert extract_json("<|inner_prefix|>thinking {no}<|inner_suffix|>{\"ok\": true}") == {"ok": True}
    assert extract_json("no json here") is None


def test_guard_screens_distress_and_personal_data():
    assert guard.screen("Manchmal will ich nicht mehr leben") == "distress"
    assert guard.screen("je veux mourir") == "distress"
    assert guard.screen("Meine Nummer ist 079 123 45 67") == "personal_data"
    assert guard.screen("Ich spiele gern Volleyball") == "none"
    red = guard.redact("Schreib mir: lea@example.ch oder 079 123 45 67, AHV 756.1234.5678.97")
    assert "@" not in red and "079" not in red and "756.1234" not in red
