"""chroma 检索测试：双路加权融合、structure-only 取正文、阈值、缺失依赖/集合、来源脱敏。

chromadb / sentence-transformers 未安装时也能覆盖主要逻辑（注入假客户端与假嵌入），
并额外验证"缺依赖必须 503、不得静默回退 keyword"。
"""

from __future__ import annotations

import importlib.util
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.retriever import (
    DEFAULT_CHROMA_MIN_SCORE,
    ChromaRetriever,
    KeywordRetriever,
    RetrieverUnavailable,
    build_retriever,
)

_UNSET = object()

KB_SOURCE = "D:/SchoolRobot-main/knowledge_base/cleaned/选课管理办法.md"


class FakeEmbedder:
    def __init__(self):
        self.calls: list[str] = []

    def encode_one(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


class FakeCollection:
    def __init__(self, entries=None, *, query_exclude=(), name="fake"):
        self.entries = list(entries or [])
        self.query_exclude = set(query_exclude)
        self.query_error: Exception | None = None
        self.get_error: Exception | None = None
        self.count_error: Exception | None = None
        self.name = name

    def count(self):
        if self.count_error is not None:
            raise self.count_error
        return len(self.entries)

    def query(self, query_embeddings, n_results, include):  # noqa: ARG002
        if self.query_error is not None:
            raise self.query_error
        visible = [item for item in self.entries if item["id"] not in self.query_exclude][:n_results]
        return {
            "ids": [[item["id"] for item in visible]],
            "documents": [[item.get("document") for item in visible]],
            "metadatas": [[item.get("metadata", {}) for item in visible]],
            "distances": [[item.get("distance", 0.1) for item in visible]],
        }

    def get(self, ids, include=None):  # noqa: ARG002
        if self.get_error is not None:
            raise self.get_error
        wanted = set(ids)
        found = [item for item in self.entries if item["id"] in wanted]
        return {
            "ids": [item["id"] for item in found],
            "documents": [item.get("document") for item in found],
            "metadatas": [item.get("metadata", {}) for item in found],
        }


class FakeClient:
    def __init__(self, collections):
        self.collections = collections

    def get_collection(self, name):
        if name not in self.collections:
            raise ValueError("collection not found")
        return self.collections[name]


def entry(chunk_id, document="正文", distance=0.1, file_path=KB_SOURCE, title="选课管理办法"):
    return {
        "id": chunk_id,
        "document": document,
        "distance": distance,
        "metadata": {"file_path": file_path, "title": title, "chunk_index": 0},
    }


def make_retriever(
    tmp_path,
    content_entries=(),
    structure_entries=(),
    *,
    content_exclude=(),
    structure_exclude=(),
    embedder=_UNSET,
    **kwargs,
):
    (tmp_path / "chroma.sqlite3").write_bytes(b"")
    content = FakeCollection(content_entries, query_exclude=content_exclude, name="content")
    structure = FakeCollection(structure_entries, query_exclude=structure_exclude, name="structure")
    client = FakeClient(
        {"school_documents_content": content, "school_documents_structure": structure}
    )
    kwargs.setdefault("min_score", 0.0)
    retriever = ChromaRetriever(
        persist_directory=tmp_path,
        content_collection_name="school_documents_content",
        structure_collection_name="school_documents_structure",
        client_factory=lambda path: client,
        embedder=FakeEmbedder() if embedder is _UNSET else embedder,
        **kwargs,
    )
    return retriever, content, structure


def test_dual_path_weighted_merge_and_sort(tmp_path):
    content = [entry("c1", distance=0.25), entry("c2", distance=0.5)]
    structure = [entry("c1", document="位置: 第一章", distance=0.5)]
    retriever, _, _ = make_retriever(tmp_path, content, structure)

    results = retriever.search("选课")
    assert [item.chunk_id for item in results] == ["c1", "c2"]
    expected_c1 = 0.6 * (1 / 1.25) + 0.4 * (1 / 1.5)
    expected_c2 = 0.6 * (1 / 1.5)
    assert results[0].score == pytest.approx(expected_c1, abs=1e-3)
    assert results[1].score == pytest.approx(expected_c2, abs=1e-3)
    assert results[0].score > results[1].score


def test_structure_only_hit_uses_content_body(tmp_path):
    content = [entry("c9", document="正文：学生应在规定时间内完成选课。")]
    structure = [entry("c9", document="位置: 第一章 | 关键词: 选课", distance=0.1)]
    retriever, _, _ = make_retriever(tmp_path, content, structure, content_exclude={"c9"})

    results = retriever.search("选课")
    assert len(results) == 1
    assert "正文" in results[0].text
    assert "位置:" not in results[0].text  # 结构摘要不能当正文
    assert results[0].source == "knowledge_base/cleaned/选课管理办法.md"


def test_structure_only_passes_production_default_threshold(tmp_path):
    """结构路分数必须保留：默认 0.35 阈值下也要能取到 content 正文。"""
    assert DEFAULT_CHROMA_MIN_SCORE == 0.35
    (tmp_path / "chroma.sqlite3").write_bytes(b"")
    content = FakeCollection(
        [entry("c9", document="正文：学生应在规定时间内完成选课。")],
        query_exclude={"c9"},
        name="content",
    )
    structure = FakeCollection(
        [entry("c9", document="位置: 第一章 | 关键词: 选课", distance=0.1)],
        name="structure",
    )
    client = FakeClient(
        {"school_documents_content": content, "school_documents_structure": structure}
    )
    retriever = ChromaRetriever(
        persist_directory=tmp_path,
        content_collection_name="school_documents_content",
        structure_collection_name="school_documents_structure",
        client_factory=lambda path: client,
        embedder=FakeEmbedder(),
    )  # 不传 min_score，使用生产默认 0.35

    results = retriever.search("选课")
    assert len(results) == 1
    assert results[0].text.startswith("正文")
    assert results[0].score == pytest.approx(0.4 * (1 / 1.1), abs=1e-3)


def test_structure_only_without_content_is_skipped(tmp_path):
    structure = [entry("c10", document="位置: 未知 | 关键词: 选课")]
    retriever, _, _ = make_retriever(tmp_path, [], structure)
    assert retriever.search("选课") == []


def test_structure_only_missing_content_id_is_skipped_not_503(tmp_path):
    # 内容集合存在，但没有该 ID：属于"缺正文"，跳过而不是 503
    content = [entry("other", document="不相干正文")]
    structure = [entry("c9", document="位置: 未知 | 关键词: 选课")]
    retriever, _, _ = make_retriever(
        tmp_path, content, structure, content_exclude={"c9", "other"}
    )
    assert retriever.search("选课") == []


def test_content_fetch_db_failure_raises_503(tmp_path):
    # 数据库 get 异常是库故障，必须 503，不能当作"缺正文"静默跳过
    content = [entry("c9", document="正文：学生应在规定时间内完成选课。")]
    structure = [entry("c9", document="位置: 第一章 | 关键词: 选课", distance=0.1)]
    retriever, content_collection, _ = make_retriever(
        tmp_path, content, structure, content_exclude={"c9"}
    )
    content_collection.get_error = RuntimeError("database is locked")
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_min_score_filters_low_relevance(tmp_path):
    content = [entry("c3", distance=0.9)]  # 0.6 * 1/1.9 ≈ 0.316
    retriever, _, _ = make_retriever(tmp_path, content, min_score=0.35)
    assert retriever.search("选课") == []
    retriever.min_score = 0.1
    assert len(retriever.search("选课")) == 1


def test_multiple_chunks_ranking_is_stable(tmp_path):
    content = [entry("c1", distance=0.8), entry("c2", distance=0.1), entry("c3", distance=0.4)]
    retriever, _, _ = make_retriever(tmp_path, content)
    ids = [item.chunk_id for item in retriever.search("选课")]
    assert ids == ["c2", "c3", "c1"]


def test_top_k_is_bounded(tmp_path):
    content = [entry(f"c{i}", distance=0.1 + i * 0.05) for i in range(5)]
    retriever, _, _ = make_retriever(tmp_path, content, top_k=2)
    assert len(retriever.search("选课")) == 2
    retriever.top_k = 999
    assert len(retriever.search("选课")) <= 10


def test_empty_collections_skip_embedder(tmp_path):
    retriever, _, _ = make_retriever(tmp_path)
    assert retriever.search("选课") == []
    assert retriever._embedder.calls == []


def test_missing_collection_raises_503(tmp_path):
    (tmp_path / "chroma.sqlite3").write_bytes(b"")
    content = FakeCollection([entry("c1")], name="content")
    client = FakeClient({"school_documents_content": content})
    retriever = ChromaRetriever(
        persist_directory=tmp_path,
        content_collection_name="school_documents_content",
        structure_collection_name="school_documents_structure",
        client_factory=lambda path: client,
        embedder=FakeEmbedder(),
        min_score=0.0,
    )
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_missing_vector_db_directory_raises_503(tmp_path):
    retriever = ChromaRetriever(tmp_path / "no-such-dir", embedder=FakeEmbedder())
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_existing_directory_without_sqlite_raises_503(tmp_path):
    empty = tmp_path / "empty-db"
    empty.mkdir()
    retriever = ChromaRetriever(empty, embedder=FakeEmbedder())
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_query_failure_raises_without_keyword_fallback(tmp_path):
    retriever, content, _ = make_retriever(tmp_path, [entry("c1")])
    content.query_error = RuntimeError("dimension mismatch")
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_collection_count_failure_raises_503_instead_of_empty(tmp_path):
    retriever, content, _ = make_retriever(tmp_path, [entry("c1")])
    content.count_error = RuntimeError("database is locked")
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_client_factory_failure_raises_503(tmp_path):
    (tmp_path / "chroma.sqlite3").write_bytes(b"")

    def broken_factory(path):  # noqa: ARG001
        raise RuntimeError("cannot open database")

    retriever = ChromaRetriever(tmp_path, client_factory=broken_factory, embedder=FakeEmbedder())
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_embedding_encode_failure_raises_503(tmp_path):
    class BrokenEmbedder:
        def encode_one(self, text):  # noqa: ARG002
            raise RuntimeError("cuda out of memory")

    retriever, _, _ = make_retriever(tmp_path, [entry("c1")], embedder=BrokenEmbedder())
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_concurrent_embedder_initialization_loads_once(tmp_path, monkeypatch):
    calls: list[float] = []

    def slow_create(self):  # noqa: ARG001
        calls.append(time.monotonic())
        time.sleep(0.05)
        return FakeEmbedder()

    monkeypatch.setattr(ChromaRetriever, "_create_embedder", slow_create)
    retriever = ChromaRetriever(tmp_path, embedder=None)

    with ThreadPoolExecutor(max_workers=8) as pool:
        embedders = list(pool.map(lambda _: retriever._get_embedder(), range(8)))

    assert len(calls) == 1  # 惰性初始化只执行一次
    assert all(item is embedders[0] for item in embedders)


@pytest.mark.skipif(importlib.util.find_spec("chromadb") is not None, reason="本机已安装 chromadb")
def test_missing_chromadb_dependency_raises_503(tmp_path):
    (tmp_path / "chroma.sqlite3").write_bytes(b"")
    retriever = ChromaRetriever(tmp_path, embedder=FakeEmbedder())
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is not None,
    reason="本机已安装 sentence-transformers",
)
def test_missing_embedding_dependency_raises_503(tmp_path):
    retriever, _, _ = make_retriever(tmp_path, [entry("c1")], embedder=None)
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_source_is_sanitized(tmp_path):
    content = [
        entry("c1", file_path="D:/SchoolRobot-main/knowledge_base/cleaned/选课管理办法.md"),
        entry("c2", file_path="C:\\Users\\someone\\private\\secret.md"),
    ]
    retriever, _, _ = make_retriever(tmp_path, content)
    sources = {item.chunk_id: item.source for item in retriever.search("选课")}
    assert sources["c1"] == "knowledge_base/cleaned/选课管理办法.md"
    assert sources["c2"] == "secret.md"
    for source in sources.values():
        assert ":" not in source
        assert "Users" not in source


def test_build_retriever_modes(tmp_path):
    keyword_settings = Settings(knowledge_base_dir=tmp_path)
    assert isinstance(build_retriever(keyword_settings), KeywordRetriever)

    chroma_settings = Settings(retrieval_mode="chroma", vector_db_path=tmp_path)
    assert isinstance(build_retriever(chroma_settings), ChromaRetriever)

    with pytest.raises(RetrieverUnavailable):
        build_retriever(Settings(retrieval_mode="vector-magic"))
