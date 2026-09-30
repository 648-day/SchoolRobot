"""请求/响应类型测试：trim、长度边界、类型错误。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.chat import MAX_MESSAGE_CHARS, ChatRequest, ChatResponse, SourceItem


def test_message_is_trimmed():
    request = ChatRequest(message="  选课时间  ")
    assert request.message == "选课时间"


def test_whitespace_only_rejected():
    for raw in ("", "   ", "\t\n ", "\u3000"):
        with pytest.raises(ValidationError):
            ChatRequest(message=raw)


def test_length_boundaries():
    assert ChatRequest(message="问" * MAX_MESSAGE_CHARS).message == "问" * MAX_MESSAGE_CHARS
    with pytest.raises(ValidationError):
        ChatRequest(message="问" * (MAX_MESSAGE_CHARS + 1))


def test_length_counts_after_trim():
    # 前后空白 trim 后正好达到上限，应该通过
    request = ChatRequest(message=" " + "问" * MAX_MESSAGE_CHARS + " ")
    assert len(request.message) == MAX_MESSAGE_CHARS


def test_wrong_types_rejected():
    for raw in (123, None, ["选课"], {"m": 1}, True):
        with pytest.raises(ValidationError):
            ChatRequest(message=raw)


def test_missing_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest()


def test_response_shape():
    response = ChatResponse(
        answer="答案",
        sources=[SourceItem(index=1, title="标题", source="knowledge_base/cleaned/a.md", snippet="片段", score=0.9)],
        retrieval_mode="keyword",
    )
    assert response.model_dump()["sources"][0]["index"] == 1
    assert ChatResponse(answer="x", retrieval_mode="keyword").sources == []
