"""评测指标与逐例行为测试：位次、重复来源、无命中、负例、错误、证据覆盖。

只测行为与分母定义；检索器用 stub，不加载任何模型、不访问网络、不写向量库。
"""

from __future__ import annotations

from app.services.retriever import RetrievedChunk
from evaluate_retrieval import (
    EvalCase,
    EvalDataset,
    evidence_covered,
    evaluate,
    match_source,
    summarize,
)


def positive(case_id: str, *, query: str = "问题", source: str = "knowledge_base/cleaned/a.md",
             keywords: tuple[str, ...] = ("证据甲",)) -> EvalCase:
    return EvalCase(
        id=case_id,
        kind="positive",
        query=query,
        expected_source=source,
        evidence_keywords=keywords,
    )


def negative(case_id: str, *, query: str = "负例问题") -> EvalCase:
    return EvalCase(id=case_id, kind="negative", query=query)


def dataset(*cases: EvalCase) -> EvalDataset:
    return EvalDataset(name="t", description="t", cases=tuple(cases))


def chunk(source: str, *, score: float = 1.0, text: str = "这里包含证据甲。",
          chunk_id: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or f"{source}#p0",
        title="标题",
        source=source,
        text=text,
        score=score,
    )


class StubRetriever:
    def __init__(self, mapping: dict[str, object]) -> None:
        self.mapping = mapping
        self.calls: list[tuple[str, int | None]] = []

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        self.calls.append((query, top_k))
        value = self.mapping[query]
        if isinstance(value, Exception):
            raise value
        return list(value)  # type: ignore[arg-type]


def test_hit_at_k_mrr_and_denominators():
    data = dataset(positive("p1"), positive("p2"), positive("p3"))
    retriever = StubRetriever(
        {
            "问题": [],
        }
    )
    outcomes = evaluate(data, retriever, top_k=5)
    assert [item.hit for item in outcomes] == [False, False, False]
    summary = summarize(outcomes, top_k=5)
    assert summary["document_hit_at_k"] == {"hits": 0, "total": 3, "value": 0.0}
    assert summary["mrr"]["value"] == 0.0

    retriever = StubRetriever(
        {
            "问题": [
                chunk("knowledge_base/cleaned/other.md"),
                chunk("knowledge_base/cleaned/a.md"),
            ]
        }
    )
    outcomes = evaluate(dataset(positive("p1")), retriever, top_k=5)
    assert outcomes[0].rank == 2
    assert outcomes[0].hit is True
    assert summarize(outcomes, top_k=5)["mrr"]["value"] == 0.5


def test_first_hit_rank_uses_first_matching_occurrence_for_duplicate_sources():
    # 目标文档前有两条同源结果：首次命中名次按 3 计，重复来源只算第一次
    retriever = StubRetriever(
        {
            "问题": [
                chunk("knowledge_base/cleaned/other.md"),
                chunk("knowledge_base/cleaned/other.md"),
                chunk("knowledge_base/cleaned/a.md"),
                chunk("knowledge_base/cleaned/a.md"),
            ]
        }
    )
    outcomes = evaluate(dataset(positive("p1")), retriever, top_k=5)
    assert outcomes[0].rank == 3
    assert outcomes[0].hit is True
    assert summarize(outcomes, top_k=5)["document_hit_at_k"]["hits"] == 1

    retriever = StubRetriever({"问题": [chunk("knowledge_base/cleaned/a.md"), chunk("a.md")]})
    outcomes = evaluate(dataset(positive("p1")), retriever, top_k=5)
    assert outcomes[0].rank == 1


def test_source_matching_allows_suffix_but_not_different_file():
    assert match_source("knowledge_base/cleaned/a.md", "a.md") is True
    assert match_source("a.md", "knowledge_base/cleaned/a.md") is True
    assert match_source("knowledge_base/cleaned/a.md", "knowledge_base/cleaned/a.md") is True
    assert match_source("knowledge_base/cleaned/b.md", "knowledge_base/cleaned/a.md") is False
    assert match_source("", "a.md") is False
    assert match_source("knowledge_base/cleaned/a.md", "") is False


def test_negative_rejection_counts_only_zero_hits_and_keeps_unrelated_hits():
    data = dataset(negative("n1"), negative("n2"))
    retriever = StubRetriever(
        {
            "负例问题": [],
        }
    )
    outcomes = evaluate(data, retriever, top_k=5)
    assert all(item.rejected is True for item in outcomes)
    summary = summarize(outcomes, top_k=5)
    assert summary["negative_rejection"] == {"rejected": 2, "total": 2, "value": 1.0}

    # 返回无关命中：如实记录，不能被当成拒答成功
    mixed = StubRetriever({"负例问题": [chunk("knowledge_base/cleaned/other.md")]})
    outcomes = evaluate(dataset(negative("n1")), mixed, top_k=5)
    assert outcomes[0].rejected is False
    assert [item.source for item in outcomes[0].results] == ["knowledge_base/cleaned/other.md"]
    summary = summarize(outcomes, top_k=5)
    assert summary["negative_rejection"] == {"rejected": 0, "total": 1, "value": 0.0}


def test_summary_without_negatives_reports_not_applicable():
    retriever = StubRetriever({"问题": [chunk("knowledge_base/cleaned/a.md")]})
    outcomes = evaluate(dataset(positive("p1")), retriever, top_k=5)
    summary = summarize(outcomes, top_k=5)
    assert summary["negative_rejection"] == {"rejected": 0, "total": 0, "value": None}


def test_error_is_not_counted_as_hit_or_rejection():
    data = dataset(positive("p1"), negative("n1"))
    retriever = StubRetriever({"问题": RuntimeError("boom"), "负例问题": RuntimeError("boom")})
    outcomes = evaluate(data, retriever, top_k=5)
    assert outcomes[0].error is not None and "boom" in outcomes[0].error
    assert outcomes[0].hit is False and outcomes[0].evidence_hit is False
    assert outcomes[1].error is not None
    assert outcomes[1].rejected is False  # 错误绝不算拒答成功
    summary = summarize(outcomes, top_k=5)
    assert summary["error_total"] == 2
    assert summary["document_hit_at_k"] == {"hits": 0, "total": 1, "value": 0.0}
    assert summary["negative_rejection"] == {"rejected": 0, "total": 1, "value": 0.0}


def test_error_in_one_case_does_not_stop_other_cases():
    data = dataset(positive("bad"), positive("good"))

    class FlakyRetriever:
        def __init__(self):
            self.count = 0

        def search(self, query, top_k=None):  # noqa: ARG002
            self.count += 1
            if self.count == 1:
                raise RuntimeError("first")
            return [chunk("knowledge_base/cleaned/a.md")]

    outcomes = evaluate(data, FlakyRetriever(), top_k=5)
    assert outcomes[0].error is not None
    assert outcomes[1].error is None and outcomes[1].hit is True


def test_evidence_coverage_requires_all_keywords_in_one_text():
    assert evidence_covered("每学期应选修 15—35 学分课程", ["每学期应选修", "15—35"]) is True
    assert evidence_covered("每学期应选修 15—35 学分课程", ["每学期应选修", "不存在的证据"]) is False
    assert evidence_covered("证据甲", []) is False
    data = dataset(
        positive("covered", keywords=("证据甲",)),
        positive("uncovered", keywords=("证据乙",)),
    )
    retriever = StubRetriever(
        {
            "问题": [chunk("knowledge_base/cleaned/a.md", text="这里包含证据甲。")],
        }
    )
    outcomes = evaluate(data, retriever, top_k=5)
    summary = summarize(outcomes, top_k=5)
    assert summary["evidence_coverage"] == {"covered": 1, "total": 2, "value": 0.5}


def test_evidence_uses_full_retriever_text_not_report_clip():
    # 证据位于报告 200 字裁剪之外、但仍在检索器返回文本内：必须判为覆盖，
    # 并记录匹配位置与“报告片段被截断”，不能制造假阴性。
    full_text = "开" * 250 + "证据甲在原文中" + "尾" * 100
    retriever = StubRetriever({"问题": [chunk("knowledge_base/cleaned/a.md", text=full_text)]})
    outcomes = evaluate(dataset(positive("p1")), retriever, top_k=5, snippet_chars=200)
    outcome = outcomes[0]
    assert outcome.hit is True
    assert outcome.evidence_hit is True
    assert outcome.evidence_rank == 1
    assert outcome.evidence_report_truncated is True
    assert len(outcome.results[0].snippet) == 200
    assert outcome.results[0].text == full_text
    match = outcome.evidence_matches[0]
    assert match.keyword == "证据甲"
    assert match.start == 250
    assert full_text[match.start : match.end] == "证据甲"


def test_evidence_in_report_clip_is_not_marked_truncated():
    retriever = StubRetriever({"问题": [chunk("knowledge_base/cleaned/a.md", text="证据甲在开头")]})
    outcomes = evaluate(dataset(positive("p1")), retriever, top_k=5, snippet_chars=200)
    assert outcomes[0].evidence_hit is True
    assert outcomes[0].evidence_report_truncated is False


def test_evidence_is_restricted_to_expected_source_chunks():
    # 其他文档包含完全一样的关键词：不能冒算成功
    wrong = chunk("knowledge_base/cleaned/b.md", text="证据甲在这里")
    right = chunk("knowledge_base/cleaned/a.md", text="无关正文")
    outcomes = evaluate(dataset(positive("p1")), StubRetriever({"问题": [wrong, right]}), top_k=5)
    outcome = outcomes[0]
    assert outcome.hit is True and outcome.rank == 2
    assert outcome.evidence_hit is False
    assert outcome.evidence_matches == ()

    only_wrong = evaluate(
        dataset(positive("p1")), StubRetriever({"问题": [wrong]}), top_k=5
    )
    assert only_wrong[0].hit is False
    assert only_wrong[0].evidence_hit is False


def test_evidence_keywords_must_share_one_chunk_of_expected_source():
    # 同一目标文档的两个不同片段各含一半关键词：不算覆盖
    first = chunk("knowledge_base/cleaned/a.md", text="只有证据甲")
    second = chunk("knowledge_base/cleaned/a.md", text="只有证据乙")
    retriever = StubRetriever({"问题": [first, second]})
    outcomes = evaluate(
        dataset(positive("p1", keywords=("证据甲", "证据乙"))), retriever, top_k=5
    )
    assert outcomes[0].hit is True
    assert outcomes[0].evidence_hit is False
    assert outcomes[0].evidence_rank is None

    both = chunk("knowledge_base/cleaned/a.md", text="证据甲和证据乙在一起")
    outcomes = evaluate(
        dataset(positive("p1", keywords=("证据甲", "证据乙"))),
        StubRetriever({"问题": [both]}),
        top_k=5,
    )
    assert outcomes[0].evidence_hit is True
    assert outcomes[0].evidence_rank == 1
    assert [match.keyword for match in outcomes[0].evidence_matches] == ["证据甲", "证据乙"]


def test_evaluate_bounds_top_k_and_passes_query():
    retriever = StubRetriever({"问题": [chunk("knowledge_base/cleaned/a.md")]})
    evaluate(dataset(positive("p1", query="问题")), retriever, top_k=99)
    assert retriever.calls == [("问题", 10)]

    retriever = StubRetriever({"问题": [chunk("knowledge_base/cleaned/a.md")]})
    outcomes = evaluate(dataset(positive("p1", query="问题")), retriever, top_k=2)
    assert len(outcomes[0].results) == 1
    assert retriever.calls == [("问题", 2)]


def test_snippet_is_clipped_for_report_but_full_text_kept():
    long_text = "证据甲" + "很长" * 200
    retriever = StubRetriever({"问题": [chunk("knowledge_base/cleaned/a.md", text=long_text)]})
    outcomes = evaluate(dataset(positive("p1")), retriever, top_k=5, snippet_chars=50)
    assert len(outcomes[0].results[0].snippet) == 50
    assert outcomes[0].results[0].snippet_truncated is True
    assert outcomes[0].results[0].text == long_text  # 证据判定仍用完整文本
    assert outcomes[0].evidence_hit is True
