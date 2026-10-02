from datetime import timedelta

import httpx
import pytest
from sqlmodel import Session

from zusage.db import Interview, utcnow
from zusage.llm.client import ChatClient, LLMError
from zusage.main import _purge_old_transcripts


def test_demo_visitors_have_private_data(client):
    first = client.post("/api/auth/demo/student").json()
    apps = client.get("/api/applications").json()
    client.patch(f"/api/applications/{apps[0]['id']}", json={"company": "Private edit"})
    second = client.post("/api/auth/demo/student").json()
    assert first["id"] != second["id"]
    assert "Private edit" not in [a["company"] for a in client.get("/api/applications").json()]
    assert client.patch(f"/api/applications/{apps[0]['id']}", json={"company": "Attack"}).status_code == 404


def test_demo_teachers_cannot_read_other_visitors(client):
    client.post("/api/auth/demo/teacher")
    first_class = client.get("/api/classes").json()[0]
    client.post("/api/auth/demo/teacher")
    second_class = client.get("/api/classes").json()[0]
    assert first_class["id"] != second_class["id"]
    assert client.get(f"/api/classes/{first_class['id']}").status_code == 404


def test_firebase_cookie_and_api_cache_policy(client):
    response = client.post("/api/auth/demo/student")
    assert "__session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/me").status_code == 200
    assert client.get("/api/me").headers["cache-control"] == "private, no-store"


def test_retry_empty_or_distress_keeps_previous_answer(student):
    iv = student.post("/api/interviews", json={"occupation_id": "koch_efz", "length": "quick"}).json()
    path = f"/api/interviews/{iv['id']}"
    before = student.post(path + "/answer", json={"answer": "Ich koche gern mit meiner Familie."}).json()
    assert student.post(path + "/retry", json={"answer": "  "}).status_code == 409
    paused = student.post(path + "/retry", json={"answer": "I want to kill myself"}).json()
    assert paused["safety_pause"] and paused["turns"] == before["turns"]
    assert student.post(path + "/retry", json={"answer": "Hello"}).status_code == 409
    student.post(path + "/resume")
    assert student.get(path).json()["turns"] == before["turns"]


def test_profile_and_posting_redacted_from_model_state(student):
    private = "secret@example.com"
    student.put("/api/me/profile", json={"data": {"experience": private, "stories": [{"text": private}]}})
    iv = student.post("/api/interviews", json={"occupation_id": "koch_efz", "posting": private}).json()
    exported = student.get("/api/me/export").json()
    state = next(i["state"] for i in exported["interviews"] if i["id"] == iv["id"])
    assert private not in str(state["setup"])


def test_transcript_retention_removes_quotes_retries_and_reports(student):
    iv = student.post("/api/interviews", json={"occupation_id": "koch_efz"}).json()
    path = f"/api/interviews/{iv['id']}"
    student.post(path + "/answer", json={"answer": "Unique personal story about a family holiday."})
    student.post(path + "/retry", json={"answer": "Unique revised story from my own family holiday."})
    student.post(path + "/finish", json={})
    with Session(student.app.state.engine) as session:
        row = session.get(Interview, iv["id"])
        row.created_at = utcnow() - timedelta(days=181)
        session.add(row)
        session.commit()
    _purge_old_transcripts(student.app.state.engine, 180)
    after = student.get(path).json()
    assert after["turns"][0]["answer"] == ""
    assert after["turns"][0]["previous"] is None
    assert after["report"]["narrative"] == {}
    assert after["report"]["averages"]
    assert "Unique" not in str(after)


@pytest.mark.parametrize("body", [None, {}, {"choices": []}, {"choices": [{"message": {"content": []}}]},
                                  {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": "oops"}}])
def test_malformed_gateway_responses_use_defined_error(body):
    client = ChatClient("http://llm/v1", "key", "8b", max_retries=0,
                        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    with pytest.raises(LLMError, match="invalid response"):
        client.complete_json("system", "user")


def test_class_change_revokes_transcript_consent(client):
    client.post("/api/auth/demo/teacher")
    code = client.get("/api/classes").json()[0]["code"]
    client.post("/api/auth/demo/student")
    assert client.get("/api/me").json()["consent_share"]
    assert client.post("/api/me/join-class", json={"code": code}).json()["consent_share"] is False


def test_malformed_profile_rejected_before_starting_interview(student):
    assert student.put("/api/me/profile", json={"data": {"stories": "invalid"}}).status_code == 422
    assert student.put("/api/me/profile", json={"data": {"age": -4}}).status_code == 422


def test_harness_keeps_distress_pause(client):
    auth = {"Authorization": "Bearer zusage-demo"}
    messages = [{"role": "user", "content": "Hello"}]
    client.post("/v1/chat/completions", headers=auth, json={"messages": messages, "user": "safety-test"})
    messages.append({"role": "user", "content": "I want to kill myself"})
    out = client.post("/v1/chat/completions", headers=auth,
                      json={"messages": messages, "user": "safety-test"}).json()
    assert out["zusage"]["safety_pause"]
    assert "147" in out["choices"][0]["message"]["content"]
    assert out["zusage"]["llm_calls"] == 0
