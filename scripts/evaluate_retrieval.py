#!/usr/bin/env python
"""真实检索器离线评测 CLI（学生 C，开发回归小样本）。

定位与边界：
- 用现有 KeywordRetriever / ChromaRetriever **真实调用**评测 ``--dataset`` 指向的小样本
  回归集（默认 ``tests/fixtures/retrieval_cases.json``），检索逻辑本身不 mock；
- 默认离线：``--mode keyword`` 不加载任何模型；``--mode chroma`` 只读本地向量库、
  本地模型（retriever 内部 ``local_files_only``），不联网下载、不调用 LLM、不改配置；
- 证据覆盖在**检索器返回的完整文本**上判定（受检索器 SNIPPET_MAX_CHARS 限制，默认 500），
  不是报告展示用的 200 字符裁剪片段；且只统计来源匹配 expected_source 的片段；
- chroma 模式先把指定向量库**复制到临时目录**，再在**子进程**里打开副本评测：
  子进程退出即释放 Chroma 全局 client / 文件句柄，父进程随后删除临时副本；
  子进程入口只信任父进程创建、带随机 token 标记的系统 TEMP 工作区（隐藏参数不是访问控制），
  指向仓库原库 / 任意结果路径的调用一律拒绝；原库绝不用 PersistentClient 打开，
  也不创建 / 新增 / 重建集合（不碰后端全局生命周期）；
- 输出只允许新建，或覆盖**本工具自己**的报告（含 kind / schema_version 标识），
  其他已存在文件（如 frontend/package.json）一律拒绝；
- 报告逐例给出 top-k 来源、名次、分数、可审查片段、命中目标文档 / 证据（含匹配位置与
  报告片段是否被截断）/ 耗时；汇总文档级 Hit@K、MRR、证据覆盖率、负例拒绝率，并写明分母与定义。
  小样本只用于开发回归，不命名完整 Recall@K，不能泛化；
- 失败（评测集非法、输出路径危险、缺依赖、库/目录缺失、查询失败、任一案例出错）
  退出非 0，给出明确错误，且**不写出**可能被误读为"通过"的报告。

本模块可被测试导入；``main()`` 只作为 CLI 入口。
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings  # noqa: E402
from app.services.retriever import (  # noqa: E402
    DEFAULT_CHROMA_MIN_SCORE,
    RetrievedChunk,
    RetrieverUnavailable,
    bounded_top_k,
    build_retriever,
)

SCHEMA_VERSION = 1
REPORT_KIND = "retrieval_dev_regression_small_sample"
DEFAULT_DATASET_PATH = REPO_ROOT / "tests" / "fixtures" / "retrieval_cases.json"
REPORT_SNIPPET_CHARS = 200
WORKER_RESULT_NAME = "worker_result.json"
WORKER_MARKER_NAME = "worker_marker.json"
TEMP_PREFIX = "schoolrobot-retrieval-eval-"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_UNAVAILABLE = 2

_DRIVE_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"'，。；、）)】]*")
_WHITESPACE_RE = re.compile(r"\s+")
_ALLOWED_TOP_LEVEL_KEYS = {"schema_version", "name", "description", "cases"}
_ALLOWED_CASE_KEYS = {"id", "type", "query", "expected_source", "evidence", "note"}
_ALLOWED_EVIDENCE_KEYS = {"keywords", "quote"}
_POSITIVE = "positive"
_NEGATIVE = "negative"


class EvaluationError(RuntimeError):
    """评测参数 / 评测集 / 输出路径等问题（退出码 1）。"""


def _display_path(path: Path | str, repo_root: Path = REPO_ROOT) -> str:
    """报告与日志用的安全路径：仓库内用相对路径，仓库外只留文件名。"""
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return f"<repo 外>/{candidate.name}"


def _display_model(model: str | None) -> str | None:
    """模型名可直接展示；本机路径只保留目录名，避免报告泄露绝对路径。"""
    if not model:
        return model
    text = str(model)
    if re.fullmatch(r"[\w.\-]+/[\w.\-]+", text):
        return text
    return Path(text).name


def _is_within(path: Path, base: Path) -> bool:
    return path == base or base in path.parents


def _resolve_model_path(raw: str | None) -> str | None:
    """嵌入模型参数的本地相对路径按仓库根解析；模型 ID 语义保持原样。

    仅当 ``REPO_ROOT / raw`` 确实存在时才视为本地路径并解析为绝对路径，避免异地 CWD
    运行时加载失败；``BAAI/bge-large-zh-v1.5`` 这类模型 ID 不做 Path 转换。
    """
    if not raw:
        return raw
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    local = REPO_ROOT / candidate
    if local.exists():
        return str(local.resolve())
    return raw


def _system_temp() -> Path:
    return Path(tempfile.gettempdir()).resolve()


# ------------------------------------------------------------------ 评测集


@dataclass(frozen=True)
class EvalCase:
    id: str
    kind: str  # positive | negative
    query: str
    expected_source: str | None = None
    evidence_keywords: tuple[str, ...] = ()
    evidence_quote: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class EvalDataset:
    name: str
    description: str
    cases: tuple[EvalCase, ...]
    path: Path | None = None
    sha256: str = ""

    @property
    def positive_count(self) -> int:
        return sum(1 for case in self.cases if case.kind == _POSITIVE)

    @property
    def negative_count(self) -> int:
        return sum(1 for case in self.cases if case.kind == _NEGATIVE)


def _require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"评测集校验失败：{where} 必须是非空字符串")
    return value.strip()


def validate_dataset(raw: Any, *, path: Path | None = None, sha256: str = "") -> EvalDataset:
    """严格校验评测集结构；宁可报错也不静默跳过坏用例。"""
    if not isinstance(raw, dict):
        raise EvaluationError("评测集校验失败：顶层必须是 JSON 对象")
    unknown = sorted(set(raw) - _ALLOWED_TOP_LEVEL_KEYS)
    if unknown:
        raise EvaluationError(f"评测集校验失败：顶层存在未知字段 {unknown}")

    schema_version = raw.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise EvaluationError("评测集校验失败：schema_version 必须是整数 1")
    if schema_version != SCHEMA_VERSION:
        raise EvaluationError(
            f"评测集校验失败：不支持的 schema_version={schema_version}（当前只支持 {SCHEMA_VERSION}）"
        )

    name = _require_text(raw.get("name"), "name")
    description = _require_text(raw.get("description"), "description")
    cases_raw = raw.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise EvaluationError("评测集校验失败：cases 必须是非空数组")

    seen_ids: set[str] = set()
    cases: list[EvalCase] = []
    for index, item in enumerate(cases_raw):
        where = f"cases[{index}]"
        if not isinstance(item, dict):
            raise EvaluationError(f"评测集校验失败：{where} 必须是对象")
        unknown = sorted(set(item) - _ALLOWED_CASE_KEYS)
        if unknown:
            raise EvaluationError(f"评测集校验失败：{where} 存在未知字段 {unknown}")
        case_id = _require_text(item.get("id"), f"{where}.id")
        if case_id in seen_ids:
            raise EvaluationError(f"评测集校验失败：{where}.id 重复：{case_id}")
        seen_ids.add(case_id)
        kind = item.get("type")
        if kind not in (_POSITIVE, _NEGATIVE):
            raise EvaluationError(
                f"评测集校验失败：{where}.type 必须是 {_POSITIVE} 或 {_NEGATIVE}"
            )
        query = _require_text(item.get("query"), f"{where}.query")
        note_raw = item.get("note")
        note = note_raw.strip() if isinstance(note_raw, str) and note_raw.strip() else None

        expected_source: str | None = None
        keywords: tuple[str, ...] = ()
        quote: str | None = None
        if kind == _POSITIVE:
            expected_source = _require_text(item.get("expected_source"), f"{where}.expected_source")
            evidence = item.get("evidence")
            if not isinstance(evidence, dict) or not evidence:
                raise EvaluationError(f"评测集校验失败：{where}.evidence 必须是非空对象")
            unknown = sorted(set(evidence) - _ALLOWED_EVIDENCE_KEYS)
            if unknown:
                raise EvaluationError(
                    f"评测集校验失败：{where}.evidence 存在未知字段 {unknown}"
                )
            keywords_raw = evidence.get("keywords")
            if not isinstance(keywords_raw, list) or not keywords_raw:
                raise EvaluationError(
                    f"评测集校验失败：{where}.evidence.keywords 必须是非空数组（空正例证据不允许）"
                )
            keywords = tuple(
                _require_text(value, f"{where}.evidence.keywords[{position}]")
                for position, value in enumerate(keywords_raw)
            )
            quote = (
                _require_text(evidence.get("quote"), f"{where}.evidence.quote")
                if "quote" in evidence
                else None
            )
        else:
            if item.get("expected_source") not in (None, ""):
                raise EvaluationError(f"评测集校验失败：{where} 是负例，不得声明 expected_source")
            if item.get("evidence") not in (None, {}, []):
                raise EvaluationError(f"评测集校验失败：{where} 是负例，不得声明 evidence")

        cases.append(
            EvalCase(
                id=case_id,
                kind=kind,
                query=query,
                expected_source=expected_source,
                evidence_keywords=keywords,
                evidence_quote=quote,
                note=note,
            )
        )

    dataset = EvalDataset(
        name=name, description=description, cases=tuple(cases), path=path, sha256=sha256
    )
    if dataset.positive_count == 0:
        raise EvaluationError("评测集校验失败：至少需要 1 个正例")
    return dataset


def load_dataset(path: Path | str) -> EvalDataset:
    dataset_path = Path(path)
    try:
        raw_text = dataset_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise EvaluationError(f"评测集不存在：{_display_path(dataset_path)}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise EvaluationError(
            f"评测集不可读取（需要 UTF-8 编码）：{_display_path(dataset_path)}"
        ) from exc
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise EvaluationError(
            f"评测集不是合法 JSON：{exc.msg}（第 {exc.lineno} 行第 {exc.colno} 列）"
        ) from exc
    return validate_dataset(
        raw, path=dataset_path, sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    )


# ------------------------------------------------------------------ 指标与执行


def normalize_for_match(text: Any) -> str:
    """路径 / 证据匹配用归一化：去掉空白并 casefold。"""
    return _WHITESPACE_RE.sub("", str(text or "")).casefold()


def match_source(returned: str, expected: str) -> bool:
    """来源匹配：归一化后相等，或一方是另一方的路径后缀（允许带目录 / 仅文件名）。"""
    left = normalize_for_match(returned).strip("/")
    right = normalize_for_match(expected).strip("/")
    if not left or not right:
        return False
    return left == right or left.endswith("/" + right) or right.endswith("/" + left)


def _fold_indexed(text: str) -> tuple[str, list[int]]:
    """逐字符 casefold，并记录每个折叠字符对应的原文下标（支持大小写展开）。"""
    folded_chars: list[str] = []
    source_index: list[int] = []
    for index, char in enumerate(text):
        for piece in char.casefold():
            folded_chars.append(piece)
            source_index.append(index)
    return "".join(folded_chars), source_index


def find_evidence_range(text: str, keyword: str) -> tuple[int, int] | None:
    """在原文中忽略空白 / 大小写地查找关键词，返回原文坐标 (start, end)。

    坐标相对**检索器返回的文本**；查不到返回 None。用于报告记录证据匹配位置。
    """
    if not text or not keyword:
        return None
    folded, source_index = _fold_indexed(text)
    keep = [index for index, char in enumerate(folded) if not char.isspace()]
    haystack = "".join(folded[index] for index in keep)
    needle = "".join(char for char in keyword.casefold() if not char.isspace())
    if not needle:
        return None
    position = haystack.find(needle)
    if position < 0:
        return None
    start = source_index[keep[position]]
    end = source_index[keep[position + len(needle) - 1]] + 1
    return start, end


def evidence_covered(text: str, keywords: Sequence[str]) -> bool:
    """证据覆盖：同一段文本（而非报告裁剪片段）同时包含全部证据关键词。"""
    if not keywords or any(not keyword or not keyword.strip() for keyword in keywords):
        return False
    return all(find_evidence_range(text, keyword) is not None for keyword in keywords)


def _clip(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    return text[: max(0, limit - 1)] + "…", True


@dataclass(frozen=True)
class CaseResult:
    rank: int
    source: str
    score: float
    chunk_id: str
    text: str  # 检索器真实返回文本：证据判定基准（不写入报告）
    snippet: str  # 报告展示用裁剪片段
    snippet_truncated: bool


@dataclass(frozen=True)
class EvidenceMatch:
    keyword: str
    start: int
    end: int


@dataclass(frozen=True)
class CaseOutcome:
    case: EvalCase
    results: tuple[CaseResult, ...]
    elapsed_ms: float
    error: str | None = None
    # 正例：目标文档首次出现名次（None=未命中）、是否命中、证据是否覆盖
    rank: int | None = None
    hit: bool = False
    evidence_hit: bool = False
    evidence_rank: int | None = None
    evidence_matches: tuple[EvidenceMatch, ...] = ()
    evidence_report_truncated: bool | None = None
    # 负例：是否零命中（出错不计为拒答成功）
    rejected: bool | None = None


def evaluate(
    dataset: EvalDataset,
    retriever: Any,
    *,
    top_k: int,
    snippet_chars: int = REPORT_SNIPPET_CHARS,
    clock: Callable[[], float] = time.perf_counter,
) -> list[CaseOutcome]:
    """逐例真实调用 retriever；案例级异常记录为 error，绝不当作命中或拒答成功。

    证据判定使用检索器返回的完整 text（默认受检索器 SNIPPET_MAX_CHARS 限制，500 字符），
    snippet 只用于报告展示；证据只认可来源匹配 expected_source 的片段。
    """
    limit = bounded_top_k(top_k)
    outcomes: list[CaseOutcome] = []
    for case in dataset.cases:
        start = clock()
        chunks: list[RetrievedChunk] = []
        error: str | None = None
        try:
            chunks = list(retriever.search(case.query, top_k=limit) or [])
        except Exception as exc:  # noqa: BLE001 - 必须如实记录，不得静默吞掉
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = (clock() - start) * 1000.0

        results: list[CaseResult] = []
        for rank, chunk in enumerate(chunks[:limit], start=1):
            full_text = str(chunk.text or "")
            snippet, truncated = _clip(full_text, snippet_chars)
            results.append(
                CaseResult(
                    rank=rank,
                    source=str(chunk.source or ""),
                    score=round(float(chunk.score), 4),
                    chunk_id=str(chunk.chunk_id or ""),
                    text=full_text,
                    snippet=snippet,
                    snippet_truncated=truncated,
                )
            )
        result_tuple = tuple(results)

        if case.kind == _POSITIVE:
            first_rank: int | None = None
            evidence_rank: int | None = None
            evidence_matches: tuple[EvidenceMatch, ...] = ()
            report_truncated: bool | None = None
            if error is None and case.expected_source:
                for result in result_tuple:
                    if not match_source(result.source, case.expected_source):
                        continue
                    if first_rank is None:
                        first_rank = result.rank
                    if evidence_rank is not None:
                        continue
                    ranges = [
                        find_evidence_range(result.text, keyword)
                        for keyword in case.evidence_keywords
                    ]
                    if all(item is not None for item in ranges):
                        evidence_rank = result.rank
                        evidence_matches = tuple(
                            EvidenceMatch(keyword, int(found[0]), int(found[1]))
                            for keyword, found in zip(case.evidence_keywords, ranges)
                        )
                        report_truncated = result.snippet_truncated
            outcomes.append(
                CaseOutcome(
                    case=case,
                    results=result_tuple,
                    elapsed_ms=elapsed_ms,
                    error=error,
                    rank=first_rank,
                    hit=first_rank is not None,
                    evidence_hit=evidence_rank is not None,
                    evidence_rank=evidence_rank,
                    evidence_matches=evidence_matches,
                    evidence_report_truncated=report_truncated,
                )
            )
        else:
            outcomes.append(
                CaseOutcome(
                    case=case,
                    results=result_tuple,
                    elapsed_ms=elapsed_ms,
                    error=error,
                    rejected=error is None and not result_tuple,
                )
            )
    return outcomes


def summarize(outcomes: Sequence[CaseOutcome], *, top_k: int) -> dict[str, Any]:
    """汇总指标；分母写明，错误按保守方向计（正例记未命中，负例不记拒答成功）。"""
    positives = [item for item in outcomes if item.case.kind == _POSITIVE]
    negatives = [item for item in outcomes if item.case.kind == _NEGATIVE]
    errors = [item for item in outcomes if item.error]
    hits = [item for item in positives if item.hit]
    reciprocal_sum = sum(1.0 / item.rank for item in hits if item.rank)
    covered = [item for item in positives if item.evidence_hit]
    rejected = [item for item in negatives if item.rejected]

    def _rate(numerator: float, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    return {
        "top_k": top_k,
        "case_total": len(outcomes),
        "positive_total": len(positives),
        "negative_total": len(negatives),
        "error_total": len(errors),
        "document_hit_at_k": {
            "hits": len(hits),
            "total": len(positives),
            "value": _rate(len(hits), len(positives)),
        },
        "mrr": {
            "reciprocal_rank_sum": round(reciprocal_sum, 4),
            "total": len(positives),
            "value": _rate(round(reciprocal_sum, 4), len(positives)) if positives else None,
        },
        "evidence_coverage": {
            "covered": len(covered),
            "total": len(positives),
            "value": _rate(len(covered), len(positives)),
        },
        "negative_rejection": {
            "rejected": len(rejected),
            "total": len(negatives),
            "value": _rate(len(rejected), len(negatives)),
        },
        "definitions": {
            "document_hit_at_k": (
                "正例中目标文档出现在 top-k 返回来源内的比例。只判文档级命中；"
                "重复来源按首次出现的名次计、只计一次。分母=全部正例（含出错正例，出错记未命中）。"
                "不是完整 Recall@K，不度量片段级召回。"
            ),
            "mrr": (
                "正例首次命中目标文档名次倒数的平均值（1/rank）。未命中或出错记 0。"
                "分母=全部正例。"
            ),
            "evidence_coverage": (
                "正例中存在至少一条**来源匹配 expected_source** 的 top-k 结果，其**检索器返回的"
                "完整文本**（受检索器 SNIPPET_MAX_CHARS 限制，默认 500 字符；不是报告展示用的"
                f"{REPORT_SNIPPET_CHARS} 字符裁剪片段）同时包含全部证据关键词（忽略空白差异）的比例。"
                "报告记录匹配位置（相对检索文本的字符区间）与报告片段是否被截断。"
                "分母=全部正例（含出错正例）。其他文档即使含相同关键词也不计。"
            ),
            "negative_rejection": (
                "负例检索结果为空（零命中）的比例。分母=全部负例；检索出错不计为拒答成功。"
            ),
        },
    }


# ------------------------------------------------------------------ 报告


def _sanitize_text(text: str, repo_root: Path) -> str:
    raw = str(repo_root)
    for candidate in {raw, raw.replace("\\", "/")}:
        if candidate:
            text = text.replace(candidate, "<repo>")
    return _DRIVE_PATH_RE.sub(lambda match: Path(match.group(0)).name, text)


def sanitize_for_report(value: Any, repo_root: Path = REPO_ROOT) -> Any:
    """递归清洗报告；任何字符串都不保留本机绝对路径。"""
    if isinstance(value, str):
        return _sanitize_text(value, repo_root)
    if isinstance(value, dict):
        return {key: sanitize_for_report(item, repo_root) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_for_report(item, repo_root) for item in value]
    return value


def _assert_no_absolute_paths(value: Any, repo_root: Path = REPO_ROOT) -> None:
    repo_text = str(repo_root).replace("\\", "/")
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            normalized = current.replace("\\", "/")
            if _DRIVE_PATH_RE.search(current) or repo_text in normalized:
                raise EvaluationError("报告净化失败：仍包含本机绝对路径，已拒绝写出")
        elif isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return None


def _result_to_report(result: CaseResult) -> dict[str, Any]:
    return {
        "rank": result.rank,
        "source": result.source,
        "score": result.score,
        "chunk_id": result.chunk_id,
        "text_length": len(result.text),
        "snippet": result.snippet,
        "snippet_truncated": result.snippet_truncated,
    }


def _case_to_report(outcome: CaseOutcome) -> dict[str, Any]:
    case = outcome.case
    item: dict[str, Any] = {
        "id": case.id,
        "type": case.kind,
        "query": case.query,
        "expected_behavior": "hit_expected_source" if case.kind == _POSITIVE else "no_hit",
        "status": "error" if outcome.error else "ok",
        "elapsed_ms": round(outcome.elapsed_ms, 2),
        "results": [_result_to_report(result) for result in outcome.results],
    }
    if case.note:
        item["note"] = case.note
    if case.kind == _POSITIVE:
        item["expected_source"] = case.expected_source
        item["expected_evidence_keywords"] = list(case.evidence_keywords)
        if case.evidence_quote:
            item["expected_evidence_quote"] = case.evidence_quote
        item["hit"] = outcome.hit
        item["rank"] = outcome.rank
        item["evidence_hit"] = outcome.evidence_hit
        item["evidence_rank"] = outcome.evidence_rank
        item["evidence_matches"] = [
            {"keyword": match.keyword, "start": match.start, "end": match.end}
            for match in outcome.evidence_matches
        ]
        if outcome.evidence_rank is not None:
            item["evidence_report_snippet_truncated"] = bool(outcome.evidence_report_truncated)
    else:
        item["rejected"] = bool(outcome.rejected)
    if outcome.error:
        item["error"] = outcome.error
    return item


def build_report(
    *,
    dataset: EvalDataset,
    mode: str,
    top_k: int,
    outcomes: Sequence[CaseOutcome],
    library: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "top_k": top_k,
        "dataset": {
            "name": dataset.name,
            "description": dataset.description,
            "path": _display_path(dataset.path) if dataset.path else None,
            "sha256": dataset.sha256,
            "positive_total": dataset.positive_count,
            "negative_total": dataset.negative_count,
        },
        "library": library,
        "summary": summarize(outcomes, top_k=top_k),
        "cases": [_case_to_report(outcome) for outcome in outcomes],
        "disclaimer": [
            "小样本开发回归集，不是 B 的正式评测集 / 独立测试集，不能泛化。",
            "文档级 Hit@K 与证据覆盖率均不是完整 Recall@K；不要据此宣称检索质量达标。",
            "证据判定基于检索器返回完整文本（默认最多 500 字符）且来源匹配 expected_source，"
            "不是报告展示的 200 字符裁剪片段。",
            "keyword 模式分数是启发式相关度，不是向量相似度。",
            "负例命中会如实列出，未通过调阈值或过滤掩盖。",
            "跨模式结果不可直接比较；真实 Chroma / BGE 的质量结论需要在依赖、模型与向量库"
            "一致且可复现的前提下由正式评测集复验，不能用本小样本报告宣称质量达标。",
        ],
    }
    return sanitize_for_report(report)


def _is_own_report(path: Path) -> bool:
    """只认本工具报告（kind + schema_version），用于决定能否覆盖已存在文件。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(raw, dict)
        and raw.get("kind") == REPORT_KIND
        and isinstance(raw.get("schema_version"), int)
        and not isinstance(raw.get("schema_version"), bool)
    )


def resolve_output_path(
    output: str | Path,
    *,
    dataset_path: Path | str | None = None,
    knowledge_base_dir: Path | str | None = None,
    vector_db_path: Path | str | None = None,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """校验并解析输出报告路径。

    - 必须是 .json、不能是目录；
    - 拒绝写入评测集 / 知识库 / 仓库向量库 / 测试 fixture / git / backend；
    - 已存在的文件必须是本工具报告（kind + schema_version），否则拒绝覆盖。
    """
    raw = str(output or "").strip()
    if not raw:
        raise EvaluationError("必须通过 --output 指定报告文件（.json）")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    if resolved.suffix.lower() != ".json":
        raise EvaluationError("--output 必须指向 .json 文件")
    if resolved.exists() and resolved.is_dir():
        raise EvaluationError("--output 指向的是目录，请给出具体的 .json 文件")

    protected: list[tuple[str, Path]] = [
        ("git 目录", (repo_root / ".git").resolve()),
        ("后端目录（含真实 .env 与后端代码）", (repo_root / "backend").resolve()),
        ("知识库目录", (repo_root / "knowledge_base").resolve()),
        ("仓库向量库目录", (repo_root / "vectorstore").resolve()),
        ("测试 fixture 目录", (repo_root / "tests" / "fixtures").resolve()),
    ]
    if dataset_path is not None:
        protected.append(("评测集文件", Path(dataset_path).resolve()))
    if knowledge_base_dir is not None:
        protected.append(("知识库目录", Path(knowledge_base_dir).resolve()))
    if vector_db_path is not None:
        protected.append(("原向量库目录", Path(vector_db_path).resolve()))
    for label, base in protected:
        if _is_within(resolved, base):
            raise EvaluationError(f"拒绝写出：--output 不能指向{label}")
    if resolved.exists() and not _is_own_report(resolved):
        raise EvaluationError(
            "已存在的输出文件不是本工具报告（缺少 kind/schema_version 标识），拒绝覆盖"
        )
    return resolved


def write_report(report: dict[str, Any], output_path: Path) -> Path:
    _assert_no_absolute_paths(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    output_path.write_text(payload, encoding="utf-8")
    return output_path


# ------------------------------------------------------------------ 检索器


def _find_spec(name: str) -> Any:
    return importlib.util.find_spec(name)


def preflight_chroma_dependencies() -> None:
    """缺依赖时提前失败（不联网安装、不加载模型）。"""
    missing = [name for name in ("chromadb", "sentence_transformers") if _find_spec(name) is None]
    if missing:
        raise RetrieverUnavailable(
            "chroma 模式缺少依赖：" + "、".join(missing) + "（请由环境负责人安装，本脚本不下载）"
        )


def _copy_library_to_temp(source: Path) -> Path:
    """把原向量库复制到临时目录（只读原库）；复制失败也会清理临时目录。"""
    temp_root = Path(tempfile.mkdtemp(prefix="schoolrobot-retrieval-eval-"))
    target = temp_root / "chroma"
    try:
        shutil.copytree(source, target)
    except OSError as exc:
        _cleanup_temp_dir(temp_root)
        raise EvaluationError(f"复制向量库到临时目录失败：{type(exc).__name__}") from exc
    return temp_root


def _cleanup_temp_dir(temp_root: Path) -> None:
    """尽力删除临时副本（重试）；失败不静默，给出可定位的警告。"""
    gc.collect()
    for delay in (0.0, 0.2, 0.5):
        if delay:
            time.sleep(delay)
        shutil.rmtree(temp_root, ignore_errors=True)
        if not temp_root.exists():
            return
    print(f"警告：临时向量库副本未能删除（可能仍被占用）：{temp_root}", file=sys.stderr)


def _run_keyword(
    *, dataset: EvalDataset, settings: Settings, top_k: int, knowledge_base: Path
) -> tuple[list[CaseOutcome], dict[str, Any]]:
    if not knowledge_base.is_dir():
        raise RetrieverUnavailable(f"知识库目录不存在：{_display_path(knowledge_base)}")
    effective = replace(
        settings, retrieval_mode="keyword", knowledge_base_dir=knowledge_base, top_k=top_k
    )
    outcomes = evaluate(dataset, build_retriever(effective), top_k=top_k)
    library = {
        "knowledge_base": _display_path(effective.knowledge_base_dir),
        "snippet_max_chars": effective.snippet_max_chars,
        "min_score": effective.score_threshold if effective.score_threshold is not None else 0.0,
        "min_coverage": effective.min_coverage,
    }
    return outcomes, library


def _effective_chroma_settings(
    settings: Settings,
    *,
    top_k: int,
    vector_db: Path,
    model_path: str | None,
    content_collection: str | None,
    structure_collection: str | None,
    device: str | None,
) -> Settings:
    return replace(
        settings,
        retrieval_mode="chroma",
        vector_db_path=vector_db,
        embedding_model_name=model_path or settings.embedding_model_name,
        content_collection_name=content_collection or settings.content_collection_name,
        structure_collection_name=structure_collection or settings.structure_collection_name,
        embedding_device=device or settings.embedding_device,
        top_k=top_k,
    )


def _evaluate_chroma_in_process(
    *,
    dataset: EvalDataset,
    settings: Settings,
    top_k: int,
    vector_db: Path,
    model_path: str | None,
    content_collection: str | None,
    structure_collection: str | None,
    device: str | None,
) -> list[CaseOutcome]:
    """子进程内（或测试内）对给定向量库副本真实调用 ChromaRetriever。"""
    preflight_chroma_dependencies()
    effective = _effective_chroma_settings(
        settings,
        top_k=top_k,
        vector_db=vector_db,
        model_path=model_path,
        content_collection=content_collection,
        structure_collection=structure_collection,
        device=device,
    )
    return evaluate(dataset, build_retriever(effective), top_k=top_k)


def _build_worker_command(
    *,
    dataset_path: Path,
    top_k: int,
    temp_db: Path,
    result_path: Path,
    token: str,
    model_path: str | None,
    content_collection: str,
    structure_collection: str,
    device: str,
) -> list[str]:
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(SCRIPT_PATH),
        "--mode",
        "chroma",
        "--dataset",
        str(dataset_path),
        "--top-k",
        str(top_k),
        "--vector-db",
        str(temp_db),
        "--content-collection",
        content_collection,
        "--structure-collection",
        structure_collection,
        "--device",
        device,
        "--worker-result",
        str(result_path),
        "--worker-token",
        token,
    ]
    if model_path:
        command += ["--model-path", model_path]
    return command


def _validate_worker_request(args: argparse.Namespace) -> tuple[Path, Path]:
    """子进程入口信任校验，返回 (结果文件, 临时向量库副本)。

    ``hidden`` 参数不是访问控制：只接受父进程 ``_run_chroma`` 创建的工作区
    ``<系统 TEMP>/schoolrobot-retrieval-eval-*/``（内含 ``chroma/`` 副本、
    ``worker_marker.json``、``worker_result.json``），且标记中的 token / vector_db /
    result 与参数完全一致。指向仓库原库、任意输出或不匹配临时路径的调用一律拒绝。
    """
    if args.mode != "chroma":
        raise EvaluationError("worker 仅支持 chroma 模式")
    if not args.worker_result or not args.worker_token:
        raise EvaluationError("worker 缺少父进程工作参数（--worker-result / --worker-token）")

    result_path = Path(args.worker_result).resolve()
    workspace = result_path.parent
    system_temp = _system_temp()
    if result_path.name != WORKER_RESULT_NAME:
        raise EvaluationError(f"worker 结果文件名必须是 {WORKER_RESULT_NAME}")
    if workspace.parent != system_temp or not workspace.name.startswith(TEMP_PREFIX):
        raise EvaluationError("worker 结果路径不在父进程临时工作目录内，拒绝执行")

    if not args.vector_db:
        raise EvaluationError("worker 缺少 --vector-db")
    vector_db = Path(args.vector_db).resolve()
    if vector_db.parent != workspace or vector_db.name != "chroma":
        raise EvaluationError("worker 只允许打开父进程复制的临时向量库副本")
    for protected in (
        (REPO_ROOT / "vectorstore").resolve(),
        (REPO_ROOT / "knowledge_base").resolve(),
        (REPO_ROOT / "backend").resolve(),
    ):
        if _is_within(vector_db, protected):
            raise EvaluationError("worker 拒绝打开仓库内目录（原向量库 / 知识库 / 后端）")
    if not (vector_db / "chroma.sqlite3").is_file():
        raise EvaluationError("worker 临时向量库副本缺少 chroma.sqlite3")

    marker_path = workspace / WORKER_MARKER_NAME
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError("worker 缺少父进程工作标记，拒绝执行") from exc
    matches = (
        isinstance(marker, dict)
        and marker.get("kind") == REPORT_KIND
        and marker.get("schema_version") == SCHEMA_VERSION
        and marker.get("token") == args.worker_token
        and isinstance(marker.get("vector_db"), str)
        and isinstance(marker.get("result"), str)
        and Path(marker["vector_db"]).resolve() == vector_db
        and Path(marker["result"]).resolve() == result_path
    )
    if not matches:
        raise EvaluationError("worker 工作标记与参数不匹配，拒绝执行")
    return result_path, vector_db


def _validate_worker_report(report: Any) -> dict[str, Any]:
    if (
        not isinstance(report, dict)
        or report.get("kind") != REPORT_KIND
        or not isinstance(report.get("summary"), dict)
        or not isinstance(report.get("cases"), list)
    ):
        raise RetrieverUnavailable("chroma 评测子进程输出不符合本工具报告约定，评测中止")
    return report


def _run_chroma(
    *,
    dataset: EvalDataset,
    dataset_path: Path,
    settings: Settings,
    top_k: int,
    vector_db: Path,
    model_path: str | None,
    content_collection: str | None,
    structure_collection: str | None,
    device: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """父进程：校验 → 复制原库 → 子进程评测（子进程退出释放 Chroma 资源）→ 清理副本。

    父进程不导入 chromadb、不打开任何向量库；原库只参与 copytree 读取。
    """
    preflight_chroma_dependencies()
    if not vector_db.is_dir():
        raise EvaluationError(f"向量库目录不存在：{_display_path(vector_db)}")
    if not (vector_db / "chroma.sqlite3").is_file():
        raise EvaluationError("向量库目录中没有 chroma.sqlite3，可能尚未构建")

    effective = _effective_chroma_settings(
        settings,
        top_k=top_k,
        vector_db=vector_db,
        model_path=model_path,
        content_collection=content_collection,
        structure_collection=structure_collection,
        device=device,
    )
    library = {
        "vector_db": _display_path(vector_db),
        "opened_from": "temporary-copy",
        "worker": "subprocess",
        "content_collection": effective.content_collection_name,
        "structure_collection": effective.structure_collection_name,
        "embedding_model": _display_model(effective.embedding_model_name),
        "device": effective.embedding_device,
        "snippet_max_chars": effective.snippet_max_chars,
        "content_weight": effective.content_weight,
        "structure_weight": effective.structure_weight,
        "min_score": (
            effective.score_threshold
            if effective.score_threshold is not None
            else DEFAULT_CHROMA_MIN_SCORE
        ),
    }
    if dataset.path is None:
        raise EvaluationError("chroma 子进程需要数据集文件路径")

    temp_root = _copy_library_to_temp(vector_db)
    result_path = temp_root / WORKER_RESULT_NAME
    try:
        token = secrets.token_hex(16)
        try:
            (temp_root / WORKER_MARKER_NAME).write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "kind": REPORT_KIND,
                        "token": token,
                        "vector_db": str(temp_root / "chroma"),
                        "result": str(result_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            raise EvaluationError("无法写出 chroma 子进程工作标记") from exc
        command = _build_worker_command(
            dataset_path=dataset.path,
            top_k=top_k,
            temp_db=temp_root / "chroma",
            result_path=result_path,
            token=token,
            model_path=model_path,
            content_collection=effective.content_collection_name,
            structure_collection=effective.structure_collection_name,
            device=effective.embedding_device,
        )
        completed = subprocess.run(command)
        if completed.returncode != 0:
            raise RetrieverUnavailable(
                f"chroma 评测子进程退出码 {completed.returncode}，评测中止（不写出报告）"
            )
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RetrieverUnavailable("chroma 评测子进程未产出可读取的结果，评测中止") from exc
        return _validate_worker_report(payload), library
    finally:
        _cleanup_temp_dir(temp_root)


# ------------------------------------------------------------------ CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evaluate_retrieval",
        description=(
            "用真实 KeywordRetriever / ChromaRetriever 对小样本回归集离线评测；"
            "默认不下载模型、不调用 LLM、不改配置。"
        ),
    )
    parser.add_argument("--mode", choices=("keyword", "chroma"), default="keyword")
    parser.add_argument(
        "--dataset", default=None, help=f"评测集 JSON（默认 {_display_path(DEFAULT_DATASET_PATH)}）"
    )
    parser.add_argument(
        "--output", default=None, help="报告输出 .json（必填；目录不存在会创建；仅可覆盖本工具报告）"
    )
    parser.add_argument("--top-k", type=int, default=None, help="top-k（默认取配置，1..10）")
    parser.add_argument("--model-path", default=None, help="chroma 专用：本地嵌入模型名或路径")
    parser.add_argument("--vector-db", default=None, help="chroma 专用：向量库目录（默认取配置）")
    parser.add_argument(
        "--knowledge-base", default=None, help="keyword 专用：知识库目录（默认取配置）"
    )
    parser.add_argument("--content-collection", default=None, help="chroma 专用：内容集合名")
    parser.add_argument("--structure-collection", default=None, help="chroma 专用：结构集合名")
    parser.add_argument("--device", default=None, help="chroma 专用：嵌入设备，默认取配置")
    parser.add_argument(
        "--worker-result",
        default=None,
        help=argparse.SUPPRESS,  # 仅供父进程拉起的 chroma 子进程使用
    )
    parser.add_argument(
        "--worker-token",
        default=None,
        help=argparse.SUPPRESS,  # 父进程工作标记随机串，用于子进程入口校验
    )
    return parser


def _resolve_input_path(raw: str | None, default: Path) -> Path:
    if not raw:
        return default
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate


def _print_summary(
    *, mode: str, top_k: int, dataset: EvalDataset, summary: dict[str, Any], written: Path
) -> None:
    hit = summary["document_hit_at_k"]
    mrr = summary["mrr"]
    evidence = summary["evidence_coverage"]
    rejection = summary["negative_rejection"]

    def _fmt(part: dict[str, Any], label: str) -> str:
        value = part["value"]
        return (
            f"{label}：{part.get('hits', part.get('covered', part.get('rejected', 0)))}"
            f"/{part['total']} = {value if value is not None else '不适用'}"
        )

    print(f"检索评测完成（开发回归小样本）：mode={mode} top_k={top_k}")
    print(
        f"评测集：{_display_path(dataset.path) if dataset.path else '<内存>'} "
        f"（正例 {dataset.positive_count} / 负例 {dataset.negative_count}）"
    )
    print(_fmt(hit, f"文档级 Hit@{top_k}"))
    print(f"MRR：{mrr['value']}")
    print(_fmt(evidence, "证据覆盖率"))
    print(_fmt(rejection, "负例拒绝率"))
    print(f"报告已写出：{_display_path(written)}")


def _run_worker(args: argparse.Namespace) -> int:
    """chroma 子进程：校验父进程工作区后才打开临时副本并写出结果 JSON。

    由父进程用独立进程拉起；进程退出后 Chroma 全局 client / Windows 文件锁一并释放。
    校验失败时不会构造检索器、不会写出任何文件。
    """
    try:
        result_path, vector_db = _validate_worker_request(args)
        settings = Settings.from_env()
        top_k = bounded_top_k(args.top_k if args.top_k is not None else settings.top_k)
        dataset_path = _resolve_input_path(args.dataset, DEFAULT_DATASET_PATH)
        dataset = load_dataset(dataset_path)
        outcomes = _evaluate_chroma_in_process(
            dataset=dataset,
            settings=settings,
            top_k=top_k,
            vector_db=vector_db,
            model_path=_resolve_model_path(args.model_path),
            content_collection=args.content_collection,
            structure_collection=args.structure_collection,
            device=args.device,
        )
    except RetrieverUnavailable as exc:
        print(f"检索不可用，子进程中止：{exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    except EvaluationError as exc:
        print(f"子进程参数或数据有误：{exc}", file=sys.stderr)
        return EXIT_USAGE

    errors = [outcome for outcome in outcomes if outcome.error]
    if errors:
        print("检索执行出错，子进程中止（不写结果）：", file=sys.stderr)
        for outcome in errors:
            print(f"  - {outcome.case.id}: {outcome.error}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    report = build_report(
        dataset=dataset, mode=args.mode, top_k=top_k, outcomes=outcomes, library={}
    )
    try:
        result_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        print(f"子进程无法写出结果：{exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    return EXIT_OK


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.worker_result:
        return _run_worker(args)

    mode = args.mode
    try:
        settings = Settings.from_env()
        top_k = bounded_top_k(args.top_k if args.top_k is not None else settings.top_k)
        dataset_path = _resolve_input_path(args.dataset, DEFAULT_DATASET_PATH)
        knowledge_base = _resolve_input_path(args.knowledge_base, settings.knowledge_base_dir)
        vector_db = _resolve_input_path(args.vector_db, settings.vector_db_path)
        output_path = resolve_output_path(
            args.output,
            dataset_path=dataset_path,
            knowledge_base_dir=knowledge_base,
            vector_db_path=vector_db,
        )
        dataset = load_dataset(dataset_path)
        model_path = _resolve_model_path(args.model_path)
        if mode == "keyword":
            if args.model_path:
                print("提示：keyword 模式忽略 --model-path。", file=sys.stderr)
            outcomes, library = _run_keyword(
                dataset=dataset, settings=settings, top_k=top_k, knowledge_base=knowledge_base
            )
            errors = [outcome for outcome in outcomes if outcome.error]
            if errors:
                print("检索执行出错，评测中止（不写出报告）：", file=sys.stderr)
                for outcome in errors:
                    print(f"  - {outcome.case.id}: {outcome.error}", file=sys.stderr)
                return EXIT_UNAVAILABLE
            report = build_report(
                dataset=dataset, mode=mode, top_k=top_k, outcomes=outcomes, library=library
            )
        else:
            report, library = _run_chroma(
                dataset=dataset,
                dataset_path=dataset_path,
                settings=settings,
                top_k=top_k,
                vector_db=vector_db,
                model_path=model_path,
                content_collection=args.content_collection,
                structure_collection=args.structure_collection,
                device=args.device,
            )
            report["library"] = library
            report = sanitize_for_report(report)
    except RetrieverUnavailable as exc:
        print(f"检索不可用，评测中止：{exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    except EvaluationError as exc:
        print(f"评测未开始或参数有误：{exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        written = write_report(report, output_path)
    except (EvaluationError, OSError) as exc:
        print(f"报告写出失败：{exc}", file=sys.stderr)
        return EXIT_USAGE
    _print_summary(
        mode=mode,
        top_k=top_k,
        dataset=dataset,
        summary=report["summary"],
        written=written,
    )
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口：只转发参数与退出码，评测逻辑都在函数里。"""
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
