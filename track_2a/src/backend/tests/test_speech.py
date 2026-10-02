from sqlmodel import Session

from zusage.db import Interview


def setup_voice(student, monkeypatch, language="en"):
    iv = student.post("/api/interviews", json={"occupation_id": "informatik_efz", "language": language}).json()
    service = student.app.state.speech
    service.settings.tts_enabled = True
    calls = []
    def synthesize(text, lang, rate):
        calls.append((text, lang, rate))
        return b"ID3-test-audio"
    monkeypatch.setattr(service, "synthesize", synthesize)
    return iv, calls


def test_speech_only_owned_interviewer_text(student, monkeypatch):
    iv, calls = setup_voice(student, monkeypatch)
    path = f"/api/interviews/{iv['id']}/speech"
    assert student.post(path, json={"text": "Synthesize arbitrary paid text"}).status_code == 400
    assert student.post(path, json={"text": iv["interviewer_message"], "rate": 4}).status_code == 422
    student.post("/api/auth/demo/student")
    assert student.post(path, json={"text": iv["interviewer_message"]}).status_code == 404
    student.post("/api/auth/logout")
    assert student.post(path, json={"text": iv["interviewer_message"]}).status_code == 401
    assert calls == []


def test_speech_caches_private_audio_and_bounds_requests(student, monkeypatch):
    iv, calls = setup_voice(student, monkeypatch, "fr")
    path = f"/api/interviews/{iv['id']}/speech"
    for _ in range(20):
        response = student.post(path, json={"text": iv["interviewer_message"], "rate": 0.85})
        assert response.status_code == 200 and response.content == b"ID3-test-audio"
        assert response.headers["content-type"] == "audio/mpeg"
        assert response.headers["cache-control"] == "private, no-store"
    assert len(calls) == 1 and calls[0][1:] == ("fr", 0.85)
    assert student.post(path, json={"text": iv["interviewer_message"]}).status_code == 429


def test_speech_disabled_pause_and_provider_failure(student, monkeypatch):
    iv, _ = setup_voice(student, monkeypatch)
    service = student.app.state.speech
    path = f"/api/interviews/{iv['id']}/speech"
    service.settings.tts_enabled = False
    assert student.post(path, json={"text": iv["interviewer_message"]}).status_code == 503
    service.settings.tts_enabled = True
    def failure(*args):
        raise ValueError("Secret provider error with private text")
    monkeypatch.setattr(service, "synthesize", failure)
    response = student.post(path, json={"text": iv["interviewer_message"]})
    assert response.status_code == 503 and "Secret provider" not in response.text
    with Session(student.app.state.engine) as session:
        record = session.get(Interview, iv["id"])
        record.state = {**record.state, "safety_pause": True}
        session.add(record)
        session.commit()
    assert student.post(path, json={"text": iv["interviewer_message"]}).status_code == 409
