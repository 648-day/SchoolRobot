"""POST /chat 与 /health 接口测试。

全部离线：检索器与模型客户端都是假的，错误场景用 httpx.MockTransport 模拟。
"""

from __future__ import annotations

import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.llm_service import OllamaLLM
from app.services.rag_service import RAGService, REFUSAL_MESSAGE
from app.services.retriever import ChromaRetriever, RetrievedChunk

CHUNK = RetrievedChunk(
    chunk_id="c1",
    title="选课管理办法",
    source="knowledge_base/cleaned/选课管理办法.md",
    text="学生应当在规定时间内登录教务系统完成选课。",
    score=0.9,
)


class FakeRetriever:
    def __init__(self, chunks=None):
        self.chunks = list(chunks if chunks is not None else [CHUNK])
        self.queries: list[str] = []

    def search(self, query, top_k=None):
        self.queries.append(query)
        limit = len(self.chunks) if top_k is None else top_k
        return self.chunks[:limit]


class FakeLLM:
    def __init__(self, reply="根据参考资料，选课以教务处通知为准。[1]"):
        self.reply = reply
        self.calls: list[list[dict]] = []
        self.closed = False

    def chat(self, messages):
        self.calls.append(messages)
        return self.reply

    def close(self):
        self.closed = True


def make_service(chunks=None, llm=None, **kwargs) -> RAGService:
    return RAGService(
        retriever=FakeRetriever(chunks),
        llm=llm if llm is not None else FakeLLM(),
        prompt="测试系统提示词",
        retrieval_mode="keyword",
        top_k=5,
        **kwargs,
    )


def make_client(service: RAGService, settings: Settings | None = None) -> TestClient:
    return TestClient(create_app(settings=settings or Settings(), rag_service=service))


def make_client_with_llm(handler) -> TestClient:
    llm = OllamaLLM(
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:4b",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return make_client(make_service(llm=llm))


class _FakeEmbedder:
    def encode_one(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeChromaCollection:
    def __init__(self, count=2, *, count_error=None):
        self._count = count
        self.count_error = count_error

    def count(self):
        if self.count_error is not None:
            raise self.count_error
        return self._count

    def query(self, **kwargs):
        raise AssertionError("失败路径不应执行向量查询")

    def get(self, **kwargs):
        raise AssertionError("失败路径不应读取正文")


class _FakeChromaClient:
    def __init__(self, collection):
        self.collection = collection

    def get_collection(self, name):
        return self.collection


def make_chroma_service(tmp_path, *, count_error=None, embedder=None) -> RAGService:
    (tmp_path / "chroma.sqlite3").write_bytes(b"")
    collection = _FakeChromaCollection(count_error=count_error)
    retriever = ChromaRetriever(
        persist_directory=tmp_path,
        client_factory=lambda path: _FakeChromaClient(collection),
        embedder=embedder if embedder is not None else _FakeEmbedder(),
    )
    return RAGService(retriever=retriever, llm=FakeLLM(), prompt="p", retrieval_mode="chroma")


# ------------------------------------------------------------------ 正常路径


def test_chat_happy_path_is_frontend_compatible():
    llm = FakeLLM()
    retriever = FakeRetriever()
    service = RAGService(retriever=retriever, llm=llm, prompt="p", retrieval_mode="keyword")
    client = make_client(service)

    response = client.post("/chat", json={"message": "选课时间怎么规定？"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == llm.reply
    assert body["retrieval_mode"] == "keyword"
    assert body["sources"][0] == {
        "index": 1,
        "title": "选课管理办法",
        "source": "knowledge_base/cleaned/选课管理办法.md",
        "snippet": CHUNK.text,
        "score": 0.9,
    }


def test_chat_trims_message_before_retrieval():
    retriever = FakeRetriever()
    service = RAGService(retriever=retriever, llm=FakeLLM(), prompt="p")
    client = make_client(service)

    response = client.post("/chat", json={"message": "  选课时间  "})

    assert response.status_code == 200
    assert retriever.queries == ["选课时间"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": "\t\n"},
        {"message": 123},
        {"message": None},
        {"message": ["选课"]},
        {"message": "问" * 2001},
    ],
)
def test_invalid_message_rejected_with_422(payload):
    client = make_client(make_service())
    response = client.post("/chat", json=payload)
    assert response.status_code == 422


def test_no_hit_refusal_without_llm_call():
    llm = FakeLLM()
    client = make_client(make_service(chunks=[], llm=llm))
    response = client.post("/chat", json={"message": "火星天气如何"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == REFUSAL_MESSAGE
    assert body["sources"] == []
    assert llm.calls == []


# ------------------------------------------------------------------ 模型错误映射


def test_model_connection_error_returns_503():
    def handler(request):  # noqa: ARG001
        raise httpx.ConnectError("connection refused")

    response = make_client_with_llm(handler).post("/chat", json={"message": "选课"})
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_model_timeout_returns_504():
    def handler(request):  # noqa: ARG001
        raise httpx.ReadTimeout("too slow")

    response = make_client_with_llm(handler).post("/chat", json={"message": "选课"})
    assert response.status_code == 504


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(404, json={"error": "model not found"}),
        lambda request: httpx.Response(500, text="SECRET-INTERNAL-DETAIL"),
        lambda request: httpx.Response(200, content=b"{bad-json"),
        lambda request: httpx.Response(200, json={"message": {"content": ""}}),
    ],
)
def test_model_invalid_responses_return_502(handler):
    response = make_client_with_llm(handler).post("/chat", json={"message": "选课"})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "SECRET-INTERNAL-DETAIL" not in detail
    assert "Traceback" not in detail
    assert "C:\\" not in detail


# ------------------------------------------------------------------ 其它行为


def test_chat_with_memory_not_implemented_yet():
    # A 同学负责；前端任何请求失败都会回落到 /chat（当前该接口未实现，返回 404）
    client = make_client(make_service())
    assert client.post("/chat_with_memory", json={"message": "选课"}).status_code == 404
    assert client.get("/get_history").status_code == 404
    assert client.post("/clear_history").status_code == 404  # 字面量 404 是正确的边界


def test_health_reports_process_and_config_only():
    settings = Settings()
    client = make_client(make_service(), settings=settings)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == ["process", "config"]
    assert body["external_dependencies_checked"] is False
    assert body["retrieval_mode"] == "keyword"
    assert body["model"] == settings.model_name


def test_root_route_still_works():
    client = make_client(make_service())
    assert client.get("/").json() == {"message": "Campus AI Assistant backend is running"}


def test_cors_allows_explicit_local_origins_only():
    client = make_client(make_service())
    allowed = client.options(
        "/chat",
        headers={"Origin": "http://localhost:3333", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.status_code in (200, 204)
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3333"

    denied = client.options(
        "/chat",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert denied.headers.get("access-control-allow-origin") is None


def test_invalid_retrieval_mode_returns_503_without_silent_fallback():
    app = create_app(settings=Settings(retrieval_mode="vector-magic"))
    client = TestClient(app)
    response = client.post("/chat", json={"message": "选课"})
    assert response.status_code == 503
    assert "RETRIEVAL_MODE" in response.json()["detail"]
    # /health 不探测依赖，仍可用
    assert client.get("/health").status_code == 200


def test_chroma_mode_missing_vector_db_returns_503(tmp_path):
    settings = Settings(retrieval_mode="chroma", vector_db_path=tmp_path / "no-db")
    client = TestClient(create_app(settings=settings))
    response = client.post("/chat", json={"message": "选课"})
    assert response.status_code == 503


def test_lifespan_closes_owned_service():
    service = make_service()
    app = create_app(settings=Settings(), rag_service=service)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert service.llm.closed is True


def test_import_does_not_load_heavy_dependencies():
    import app.main  # noqa: F401

    assert "torch" not in sys.modules
    assert "sentence_transformers" not in sys.modules
    assert "chromadb" not in sys.modules


def test_chroma_collection_count_failure_returns_503_without_leaking(tmp_path):
    service = make_chroma_service(tmp_path, count_error=RuntimeError("SECRET-DB-PATH"))
    response = make_client(service).post("/chat", json={"message": "选课"})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "SECRET-DB-PATH" not in detail
    assert "RuntimeError" not in detail
    assert "Traceback" not in detail


def test_chroma_embedding_failure_returns_503_without_leaking(tmp_path):
    class BrokenEmbedder:
        def encode_one(self, text):  # noqa: ARG002
            raise RuntimeError("SECRET-GPU-ERROR")

    service = make_chroma_service(tmp_path, embedder=BrokenEmbedder())
    response = make_client(service).post("/chat", json={"message": "选课"})
    assert response.status_code == 503
    assert "SECRET-GPU-ERROR" not in response.json()["detail"]
