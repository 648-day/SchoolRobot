"""Ollama 调用测试：请求体、message.content 读取、think、各类错误映射与脱敏。

全部通过 httpx.MockTransport 离线运行，不访问真实 Ollama。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.llm_service import (
    LLMConnectionError,
    LLMTimeoutError,
    LLMUpstreamError,
    OllamaLLM,
)

MESSAGES = [{"role": "user", "content": "选课时间怎么规定？"}]


def make_llm(handler, **kwargs) -> OllamaLLM:
    return OllamaLLM(
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:4b",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def raising(exc):
    def handler(request):  # noqa: ARG001
        raise exc

    return handler


def test_success_request_shape_and_content(monkeypatch=None):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "选课以教务处通知为准。[1]", "thinking": "内部思考不应返回"}},
        )

    llm = make_llm(handler)
    answer = llm.chat(MESSAGES)
    assert answer == "选课以教务处通知为准。[1]"
    assert "内部思考" not in answer
    assert captured["path"] == "/api/chat"
    payload = captured["payload"]
    assert payload["model"] == "qwen3.5:4b"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"]["temperature"] == 0.1
    assert payload["messages"] == MESSAGES


def test_think_configurable():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    llm = make_llm(handler, think=True)
    llm.chat(MESSAGES)
    assert captured["payload"]["think"] is True


def test_content_is_stripped():
    llm = make_llm(lambda request: httpx.Response(200, json={"message": {"content": "  答案  "}}))
    assert llm.chat(MESSAGES) == "答案"


def test_connection_error_maps_503_class():
    llm = make_llm(raising(httpx.ConnectError("connection refused")))
    with pytest.raises(LLMConnectionError):
        llm.chat(MESSAGES)


def test_timeout_maps_504_class():
    llm = make_llm(raising(httpx.ReadTimeout("too slow")))
    with pytest.raises(LLMTimeoutError):
        llm.chat(MESSAGES)


def test_model_404_maps_upstream_error():
    llm = make_llm(lambda request: httpx.Response(404, json={"error": "model 'secret-path' not found"}))
    with pytest.raises(LLMUpstreamError) as excinfo:
        llm.chat(MESSAGES)
    assert "qwen3.5:4b" in str(excinfo.value)
    assert "secret-path" not in str(excinfo.value)


def test_server_error_maps_upstream_and_does_not_leak_body():
    llm = make_llm(lambda request: httpx.Response(500, text="SECRET-INTERNAL-DETAIL"))
    with pytest.raises(LLMUpstreamError) as excinfo:
        llm.chat(MESSAGES)
    assert "SECRET-INTERNAL-DETAIL" not in str(excinfo.value)


def test_malformed_json_maps_upstream_error():
    llm = make_llm(lambda request: httpx.Response(200, content=b"{not-json"))
    with pytest.raises(LLMUpstreamError):
        llm.chat(MESSAGES)


@pytest.mark.parametrize(
    "payload",
    [
        {"foo": "bar"},
        {"message": "not-a-dict"},
        {"message": {"content": ""}},
        {"message": {"content": "   "}},
        {"message": {"content": None}},
        {"message": {}},
    ],
)
def test_invalid_shapes_map_upstream_error(payload):
    llm = make_llm(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(LLMUpstreamError):
        llm.chat(MESSAGES)


def test_close_owned_client_is_idempotent():
    llm = make_llm(lambda request: httpx.Response(200, json={"message": {"content": "ok"}}))
    llm.close()
    llm.close()
    assert llm._client.is_closed is True


def test_close_does_not_close_injected_client():
    external = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    llm = OllamaLLM(client=external)
    llm.close()
    assert external.is_closed is False
    external.close()
