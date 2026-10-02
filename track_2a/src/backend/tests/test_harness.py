"""OpenAI-compatible facade used by external LLM-as-judge harnesses."""

AUTH = {"Authorization": "Bearer zusage-demo"}


def chat(client, messages, **extra):
    return client.post("/v1/chat/completions", headers=AUTH, json={"model": "zusage", "messages": messages, **extra})


def test_requires_key(client):
    assert client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 401


def test_full_interview_through_chat_api(client):
    msgs = [{"role": "user", "content": '{"language": "fr", "occupation_id": "automech_efz", "length": "quick"}'}]
    r = chat(client, msgs, user="judge-1").json()
    assert r["choices"][0]["message"]["content"].startswith("Bonjour")
    for _ in range(15):
        if r["zusage"]["done"]:
            break
        msgs += [{"role": "assistant", "content": r["choices"][0]["message"]["content"]},
                 {"role": "user", "content": "Par exemple, j'ai réparé le vélo de ma voisine et j'ai appris la patience."}]
        r = chat(client, msgs, user="judge-1", metadata={"feedback_in_content": True}).json()
        assert "[Coach]" in r["choices"][0]["message"]["content"] or r["zusage"]["done"]
    assert r["zusage"]["done"] and r["zusage"]["report"]["overall"] >= 0


def test_replaying_the_same_history_is_idempotent(client):
    msgs = [{"role": "user", "content": "Hallo"}]
    first = chat(client, msgs, user="judge-2").json()
    msgs += [{"role": "assistant", "content": first["choices"][0]["message"]["content"]},
             {"role": "user", "content": "Ich heisse Mia und spiele Handball."}]
    a = chat(client, msgs, user="judge-2").json()
    b = chat(client, msgs, user="judge-2").json()  # retry of the same request
    assert a["choices"][0]["message"]["content"] == b["choices"][0]["message"]["content"]
    assert b["zusage"]["llm_calls"] == a["zusage"]["llm_calls"]
