import json

import httpx
import pytest

from zusage.llm.client import ChatClient, LLMError


def make_client(handler, retries=0):
    return ChatClient("http://llm/v1", "key", "swiss-ai/Apertus-v1.5-8B", transport=httpx.MockTransport(handler),
                      max_retries=retries)


def reply(content, status=200):
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}],
                                        "usage": {"prompt_tokens": 100, "completion_tokens": 20}})


def test_json_call_counts_usage_and_sends_auth():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return reply('{"ok": true}')

    result = make_client(handler).complete_json("sys", "user")
    assert result.data == {"ok": True} and result.usage.calls == 1 and result.usage.tokens_in == 100
    assert seen["auth"] == "Bearer key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_repair_retry_is_counted():
    answers = iter(["not json at all", '{"fixed": 1}'])
    result = make_client(lambda r: reply(next(answers))).complete_json("s", "u")
    assert result.data == {"fixed": 1} and result.usage.calls == 2


def test_server_rejecting_json_mode_is_downgraded_once():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if "response_format" in body:
            return httpx.Response(400, text="response_format not supported")
        return reply('{"plain": true}')

    client = make_client(handler)
    assert client.complete_json("s", "u").data == {"plain": True}
    assert client.json_mode is False
    client.complete_json("s", "u")
    assert "response_format" not in calls[-1]


@pytest.mark.parametrize("status,code", [(401, "auth"), (429, "rate_limited"), (500, "server")])
def test_errors_are_classified(status, code):
    with pytest.raises(LLMError) as exc:
        make_client(lambda r: httpx.Response(status, text="err")).complete_json("s", "u")
    assert exc.value.code == code


def test_rate_limits_are_retried(monkeypatch):
    monkeypatch.setattr("zusage.llm.client.time.sleep", lambda s: None)
    answers = iter([httpx.Response(429, headers={"retry-after": "1"}), httpx.Response(503), reply('{"ok": 1}')])
    result = make_client(lambda r: next(answers), retries=3).complete_json("s", "u")
    assert result.data == {"ok": 1} and result.usage.calls == 1
