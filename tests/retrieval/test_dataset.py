"""评测集校验与仓库 fixture 证据落地测试。

重点：
- 仓库小样本 regression fixture 的每个正例证据（关键词 + 引文）必须在对应
  knowledge_base/cleaned 原文中出现（仅忽略空白差异），不允许编造；
- 结构校验覆盖重复 id / 缺字段 / 未知字段 / 空正例证据 / 负例字段等错误。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluate_retrieval import (
    EvaluationError,
    load_dataset,
    normalize_for_match,
    validate_dataset,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "retrieval_cases.json"


def raw_dataset(*cases: dict) -> dict:
    return {
        "schema_version": 1,
        "name": "测试集",
        "description": "仅测试用",
        "cases": list(cases),
    }


GOOD_POSITIVE = {
    "id": "p1",
    "type": "positive",
    "query": "问题",
    "expected_source": "knowledge_base/cleaned/a.md",
    "evidence": {"keywords": ["证据甲"], "quote": "证据甲在原文里。"},
}
GOOD_NEGATIVE = {
    "id": "n1",
    "type": "negative",
    "query": "负例问题",
    "note": "原文没有。",
}


def test_repo_fixture_loads_and_has_required_scale():
    dataset = load_dataset(FIXTURE_PATH)
    assert dataset.positive_count >= 12
    assert dataset.negative_count >= 4
    sources = {case.expected_source for case in dataset.cases if case.kind == "positive"}
    assert len(sources) >= 6, f"正例需跨至少 6 篇文档，实际 {len(sources)}"
    assert dataset.sha256 and len(dataset.sha256) == 64
    assert "不能泛化" in dataset.description


def test_repo_fixture_evidence_is_grounded_in_source_files():
    dataset = load_dataset(FIXTURE_PATH)
    for case in dataset.cases:
        if case.kind != "positive":
            continue
        assert case.expected_source, f"{case.id} 缺少 expected_source"
        source_path = REPO_ROOT / case.expected_source
        assert source_path.is_file(), f"{case.id} 的 expected_source 不存在：{case.expected_source}"
        text = normalize_for_match(source_path.read_text(encoding="utf-8"))
        for keyword in case.evidence_keywords:
            assert normalize_for_match(keyword) in text, f"{case.id} 证据关键词不在原文：{keyword}"
        assert case.evidence_quote, f"{case.id} 缺少 evidence.quote"
        assert normalize_for_match(case.evidence_quote) in text, (
            f"{case.id} 证据引文不在原文：{case.evidence_quote}"
        )


def test_repo_fixture_negative_cases_declare_no_hit_expectations_only():
    dataset = load_dataset(FIXTURE_PATH)
    for case in dataset.cases:
        if case.kind != "negative":
            continue
        assert case.expected_source is None
        assert case.evidence_keywords == ()
        assert case.note, f"负例 {case.id} 应说明为何预期无命中"


def test_validate_accepts_minimal_dataset():
    dataset = validate_dataset(raw_dataset(GOOD_POSITIVE, GOOD_NEGATIVE))
    assert dataset.positive_count == 1 and dataset.negative_count == 1
    assert dataset.cases[0].evidence_quote == "证据甲在原文里。"


def test_schema_version_must_be_integer_one():
    for bad in (None, 0, 2, "1", 1.0, True):
        raw = raw_dataset(GOOD_POSITIVE)
        if bad is None:
            raw.pop("schema_version")
        else:
            raw["schema_version"] = bad
        with pytest.raises(EvaluationError, match="schema_version"):
            validate_dataset(raw)


def test_duplicate_id_rejected():
    duplicate = dict(GOOD_POSITIVE, query="另一个问题")
    with pytest.raises(EvaluationError, match="id 重复"):
        validate_dataset(raw_dataset(GOOD_POSITIVE, duplicate))


def test_missing_query_rejected():
    broken = {key: value for key, value in GOOD_POSITIVE.items() if key != "query"}
    with pytest.raises(EvaluationError, match="query"):
        validate_dataset(raw_dataset(broken))


def test_missing_expected_source_rejected():
    broken = {key: value for key, value in GOOD_POSITIVE.items() if key != "expected_source"}
    with pytest.raises(EvaluationError, match="expected_source"):
        validate_dataset(raw_dataset(broken))


def test_unknown_field_rejected():
    broken = dict(GOOD_POSITIVE, expected_src="knowledge_base/cleaned/a.md")
    with pytest.raises(EvaluationError, match="未知字段"):
        validate_dataset(raw_dataset(broken))


def test_empty_positive_evidence_rejected():
    broken = dict(GOOD_POSITIVE, evidence={"keywords": []})
    with pytest.raises(EvaluationError, match="keywords"):
        validate_dataset(raw_dataset(broken))


def test_positive_without_evidence_object_rejected():
    broken = {key: value for key, value in GOOD_POSITIVE.items() if key != "evidence"}
    with pytest.raises(EvaluationError, match="evidence"):
        validate_dataset(raw_dataset(broken))


def test_negative_with_expected_source_rejected():
    broken = dict(GOOD_NEGATIVE, expected_source="knowledge_base/cleaned/a.md")
    with pytest.raises(EvaluationError, match="负例"):
        validate_dataset(raw_dataset(broken))


def test_negative_with_evidence_rejected():
    broken = dict(GOOD_NEGATIVE, evidence={"keywords": ["甲"]})
    with pytest.raises(EvaluationError, match="负例"):
        validate_dataset(raw_dataset(broken))


def test_bad_type_rejected():
    broken = dict(GOOD_NEGATIVE, type="unknown")
    with pytest.raises(EvaluationError, match="type"):
        validate_dataset(raw_dataset(broken))


def test_empty_cases_rejected():
    with pytest.raises(EvaluationError, match="cases"):
        validate_dataset(raw_dataset())


def test_top_level_must_be_object():
    with pytest.raises(EvaluationError, match="顶层"):
        validate_dataset([GOOD_POSITIVE])


def test_unknown_top_level_field_rejected():
    raw = raw_dataset(GOOD_POSITIVE)
    raw["trick"] = 1
    with pytest.raises(EvaluationError, match="未知字段"):
        validate_dataset(raw)


def test_dataset_without_positive_rejected():
    with pytest.raises(EvaluationError, match="正例"):
        validate_dataset(raw_dataset(GOOD_NEGATIVE))


def test_load_dataset_reports_missing_and_bad_json(tmp_path: Path):
    with pytest.raises(EvaluationError, match="不存在"):
        load_dataset(tmp_path / "missing.json")

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(EvaluationError, match="合法 JSON"):
        load_dataset(broken)


def test_load_dataset_flow_reads_repo_fixture_and_hashes(tmp_path: Path):
    payload = json.dumps(raw_dataset(GOOD_POSITIVE, GOOD_NEGATIVE), ensure_ascii=False)
    path = tmp_path / "cases.json"
    path.write_text(payload, encoding="utf-8")
    dataset = load_dataset(path)
    assert dataset.path == path
    assert dataset.sha256
