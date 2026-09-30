"""评测 CLI 与报告安全测试。

覆盖：
- 危险输出路径（评测集 / 知识库 / 仓库向量库 / fixture / backend / .git）拒绝；
- 已存在文件只允许覆盖本工具报告，其他 JSON / 非 JSON 一律拒绝；
- 报告不含本机绝对路径，来源与片段中的盘符被脱敏；
- chroma：父进程复制原库并拉起子进程，子进程退出后清理临时副本；原库保持不变；
  缺依赖 / 缺库 / 子进程失败 / 子进程无结果 → 退出非 0 且不写报告；
- 任一案例出错时退出非 0 且不写出报告。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import evaluate_retrieval as ev
from app.core.config import Settings
from app.services.retriever import RetrievedChunk

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "retrieval_cases.json"
DRIVE_RE = re.compile(r"[A-Za-z]:[\\/]")


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def tiny_dataset(path: Path, *, source_file: str = "doc.md", query: str = "选课") -> Path:
    payload = {
        "schema_version": 1,
        "name": "tiny",
        "description": "tiny",
        "cases": [
            {
                "id": "p1",
                "type": "positive",
                "query": query,
                "expected_source": source_file,
                "evidence": {"keywords": ["办理退选"], "quote": "办理退选手续"},
            },
            {
                "id": "n1",
                "type": "negative",
                "query": "量子纠缠如何超光速通信",
                "note": "域外",
            },
        ],
    }
    return write_json(path, payload)


def child_report() -> dict:
    zero = {"hits": 0, "total": 0, "value": None}
    return {
        "schema_version": ev.SCHEMA_VERSION,
        "kind": ev.REPORT_KIND,
        "generated_at": "2026-01-01T00:00:00",
        "mode": "chroma",
        "top_k": 5,
        "dataset": {
            "name": "tiny",
            "description": "tiny",
            "path": "tests/fixtures/retrieval_cases.json",
            "sha256": "",
            "positive_total": 0,
            "negative_total": 0,
        },
        "library": {},
        "summary": {
            "top_k": 5,
            "case_total": 0,
            "positive_total": 0,
            "negative_total": 0,
            "error_total": 0,
            "document_hit_at_k": dict(zero),
            "mrr": {"reciprocal_rank_sum": 0.0, "total": 0, "value": None},
            "evidence_coverage": {"covered": 0, "total": 0, "value": None},
            "negative_rejection": {"rejected": 0, "total": 0, "value": None},
            "definitions": {},
        },
        "cases": [],
        "disclaimer": [],
    }


class FakeCompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def install_fake_chroma_child(
    monkeypatch,
    *,
    returncode: int = 0,
    payload: dict | None = None,
    write_result: bool = True,
    on_run=None,
) -> dict:
    """把父进程拉起的子进程替换为离线 fake：按需写出子进程结果文件。"""
    launched: dict = {}

    def fake_run(command, **kwargs):
        launched["command"] = list(command)
        launched["kwargs"] = kwargs
        if on_run is not None:
            on_run(launched["command"])
        result_path = Path(command[command.index("--worker-result") + 1])
        if returncode == 0 and write_result:
            data = payload if payload is not None else child_report()
            result_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return FakeCompletedProcess(returncode)

    monkeypatch.setattr(ev.subprocess, "run", fake_run)
    return launched


@pytest.fixture(autouse=True)
def default_settings(monkeypatch):
    """CLI 测试不依赖本机环境变量 / backend/.env。"""
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls, *a, **k: Settings()))


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "doc.md").write_text(
        "# 选课管理办法\n\n学生应在规定时间内办理退选手续，逾期按通知处理。\n\n"
        "本科生弹性学习年限为四年制本科为 3 至 6 年。\n",
        encoding="utf-8",
    )
    return kb


def test_output_path_rejects_protected_locations(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir()
    db = tmp_path / "db"
    db.mkdir()
    dataset = tmp_path / "cases.json"
    dataset.write_text("{}", encoding="utf-8")

    base_kwargs = {
        "dataset_path": dataset,
        "knowledge_base_dir": kb,
        "vector_db_path": db,
    }
    with pytest.raises(ev.EvaluationError, match="评测集"):
        ev.resolve_output_path(dataset, **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="知识库"):
        ev.resolve_output_path(kb / "report.json", **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="原向量库"):
        ev.resolve_output_path(db / "report.json", **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="知识库"):
        ev.resolve_output_path(REPO_ROOT / "knowledge_base" / "report.json", **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="向量库"):
        ev.resolve_output_path(REPO_ROOT / "vectorstore" / "report.json", **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="fixture"):
        ev.resolve_output_path(REPO_ROOT / "tests" / "fixtures" / "report.json", **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="后端"):
        ev.resolve_output_path(REPO_ROOT / "backend" / "report.json", **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="git"):
        ev.resolve_output_path(REPO_ROOT / ".git" / "report.json", **base_kwargs)
    with pytest.raises(ev.EvaluationError, match=".json"):
        ev.resolve_output_path(tmp_path / "report.txt", **base_kwargs)
    already_dir = tmp_path / "report.json"
    already_dir.mkdir()
    with pytest.raises(ev.EvaluationError, match="目录"):
        ev.resolve_output_path(already_dir, **base_kwargs)
    with pytest.raises(ev.EvaluationError, match="--output"):
        ev.resolve_output_path("", **base_kwargs)

    allowed = ev.resolve_output_path(tmp_path / "reports" / "out.json", **base_kwargs)
    assert allowed == (tmp_path / "reports" / "out.json").resolve()


def test_output_path_overwrite_rules(tmp_path: Path):
    own = tmp_path / "own.json"
    write_json(own, {"kind": ev.REPORT_KIND, "schema_version": ev.SCHEMA_VERSION})
    assert ev.resolve_output_path(own) == own.resolve()

    foreign_json = tmp_path / "package.json"
    write_json(foreign_json, {"name": "frontend", "version": "0.0.1"})
    with pytest.raises(ev.EvaluationError, match="拒绝覆盖"):
        ev.resolve_output_path(foreign_json)

    foreign_kind = tmp_path / "other_report.json"
    write_json(foreign_kind, {"kind": "something-else", "schema_version": 1})
    with pytest.raises(ev.EvaluationError, match="拒绝覆盖"):
        ev.resolve_output_path(foreign_kind)

    bad_schema = tmp_path / "bad_schema.json"
    write_json(bad_schema, {"kind": ev.REPORT_KIND, "schema_version": "1"})
    with pytest.raises(ev.EvaluationError, match="拒绝覆盖"):
        ev.resolve_output_path(bad_schema)

    not_json = tmp_path / "readme.json"
    not_json.write_text("这不是 JSON", encoding="utf-8")
    with pytest.raises(ev.EvaluationError, match="拒绝覆盖"):
        ev.resolve_output_path(not_json)

    new_path = tmp_path / "brand-new.json"
    assert ev.resolve_output_path(new_path) == new_path.resolve()


def test_write_report_creates_parents_and_sanitizes_absolute_paths(tmp_path: Path):
    case = ev.EvalCase(id="p1", kind="positive", query="q", expected_source="a.md",
                       evidence_keywords=("证据",))
    chunk = RetrievedChunk(
        chunk_id="c1",
        title="t",
        source="D:/SchoolRobot-main/knowledge_base/cleaned/doc.md",
        text="正文包含 D:\\secret\\dir\\file.txt 这样的本机路径",
        score=0.5,
    )
    outcome = ev.CaseOutcome(
        case=case,
        results=(ev.CaseResult(1, chunk.source, 0.5, "c1", chunk.text, chunk.text, False),),
        elapsed_ms=1.0, rank=1, hit=True, evidence_hit=True,
    )
    report = ev.build_report(
        dataset=ev.EvalDataset(name="t", description="t", cases=(case,)),
        mode="keyword",
        top_k=5,
        outcomes=[outcome],
        library={"knowledge_base": "knowledge_base/cleaned"},
        generated_at="2026-01-01T00:00:00",
    )
    output = ev.write_report(report, tmp_path / "nested" / "report.json")
    text = output.read_text(encoding="utf-8")
    assert DRIVE_RE.search(text) is None
    payload = json.loads(text)
    result = payload["cases"][0]["results"][0]
    assert result["source"] == "doc.md"
    assert "file.txt" in result["snippet"]
    assert "secret" not in result["snippet"]
    assert result["text_length"] == len(chunk.text)


def test_keyword_cli_end_to_end(tmp_path: Path, kb_dir: Path):
    dataset = tiny_dataset(tmp_path / "cases.json")
    output = tmp_path / "out" / "keyword.json"
    code = ev.run(
        [
            "--mode", "keyword",
            "--dataset", str(dataset),
            "--knowledge-base", str(kb_dir),
            "--output", str(output),
            "--top-k", "3",
        ]
    )
    assert code == ev.EXIT_OK
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["kind"] == ev.REPORT_KIND
    assert payload["mode"] == "keyword"
    assert payload["top_k"] == 3
    assert payload["dataset"]["path"].startswith("<repo 外>/")
    assert payload["summary"]["positive_total"] == 1
    assert payload["summary"]["negative_total"] == 1
    assert payload["library"]["knowledge_base"].startswith("<repo 外>/")
    positive = next(item for item in payload["cases"] if item["type"] == "positive")
    assert positive["expected_behavior"] == "hit_expected_source"
    assert positive["hit"] is True
    assert positive["rank"] == 1
    assert positive["evidence_hit"] is True
    assert positive["evidence_rank"] == 1
    assert positive["evidence_matches"][0]["keyword"] == "办理退选"
    assert positive["results"][0]["text_length"] >= 1
    negative = next(item for item in payload["cases"] if item["type"] == "negative")
    assert negative["expected_behavior"] == "no_hit"
    assert negative["rejected"] is True
    assert DRIVE_RE.search(output.read_text(encoding="utf-8")) is None


def test_cli_usage_errors_do_not_write_report(tmp_path: Path):
    output = tmp_path / "out.json"
    code = ev.run(
        ["--mode", "keyword", "--dataset", str(tmp_path / "missing.json"),
         "--output", str(output)]
    )
    assert code == ev.EXIT_USAGE
    assert not output.exists()

    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    code = ev.run(
        ["--mode", "keyword", "--dataset", str(broken), "--output", str(output)]
    )
    assert code == ev.EXIT_USAGE
    assert not output.exists()

    good = tiny_dataset(tmp_path / "cases.json")
    code = ev.run(["--mode", "keyword", "--dataset", str(good)])
    assert code == ev.EXIT_USAGE
    assert not output.exists()

    # 已存在的非本工具文件不可覆盖（内容与 mtime 均不变）
    protect = tmp_path / "keep.json"
    write_json(protect, {"name": "别动我"})
    before = protect.read_bytes()
    code = ev.run(
        ["--mode", "keyword", "--dataset", str(good), "--knowledge-base",
         str(tmp_path / "kb"), "--output", str(protect)]
    )
    assert code == ev.EXIT_USAGE
    assert protect.read_bytes() == before

    # 危险输出路径同样不写文件，且不改动评测集
    fixture_before = FIXTURE_PATH.read_bytes()
    code = ev.run(
        ["--mode", "keyword", "--dataset", str(broken), "--output", str(FIXTURE_PATH)]
    )
    assert code == ev.EXIT_USAGE
    assert FIXTURE_PATH.read_bytes() == fixture_before


def test_cli_missing_knowledge_base_is_unavailable(tmp_path: Path):
    dataset = tiny_dataset(tmp_path / "cases.json")
    output = tmp_path / "out.json"
    code = ev.run(
        [
            "--mode", "keyword",
            "--dataset", str(dataset),
            "--knowledge-base", str(tmp_path / "does-not-exist"),
            "--output", str(output),
        ]
    )
    assert code == ev.EXIT_UNAVAILABLE
    assert not output.exists()


def test_chroma_missing_dependency_fails_without_report(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    db = tmp_path / "vector-db"
    db.mkdir()
    (db / "chroma.sqlite3").write_bytes(b"")
    output = tmp_path / "out.json"
    monkeypatch.setattr(ev, "_find_spec", lambda name: None)

    code = ev.run(
        [
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(db),
            "--output", str(output),
        ]
    )
    assert code == ev.EXIT_UNAVAILABLE
    assert not output.exists()


def test_chroma_missing_vector_db_and_sqlite_fail(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    output = tmp_path / "out.json"
    monkeypatch.setattr(ev, "_find_spec", lambda name: object())

    code = ev.run(
        ["--mode", "chroma", "--dataset", str(dataset),
         "--vector-db", str(tmp_path / "nope"), "--output", str(output)]
    )
    assert code == ev.EXIT_USAGE
    assert not output.exists()

    empty_db = tmp_path / "empty-db"
    empty_db.mkdir()
    code = ev.run(
        ["--mode", "chroma", "--dataset", str(dataset),
         "--vector-db", str(empty_db), "--output", str(output)]
    )
    assert code == ev.EXIT_USAGE
    assert not output.exists()


def test_copy_library_to_temp_copies_and_cleans_up(tmp_path: Path):
    source = tmp_path / "original-db"
    (source / "uuid-dir").mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"sqlite")
    (source / "uuid-dir" / "data_level0.bin").write_bytes(b"data")
    before = sorted(str(path.relative_to(source)) for path in source.rglob("*"))

    temp_root = ev._copy_library_to_temp(source)
    try:
        target = temp_root / "chroma"
        assert target != source
        assert (target / "chroma.sqlite3").is_file()
        assert (target / "uuid-dir" / "data_level0.bin").read_bytes() == b"data"
    finally:
        ev._cleanup_temp_dir(temp_root)

    assert not temp_root.exists(), "临时副本必须清理"
    after = sorted(str(path.relative_to(source)) for path in source.rglob("*"))
    assert before == after, "原库目录不允许被改写"


def test_copy_library_failure_cleans_temp_and_raises(tmp_path: Path, monkeypatch):
    created: list[Path] = []
    real_mkdtemp = ev.tempfile.mkdtemp

    def fake_mkdtemp(**kwargs):
        path = Path(real_mkdtemp(**kwargs))
        created.append(path)
        return str(path)

    def broken_copytree(*args, **kwargs):  # noqa: ARG001
        raise OSError("copy failed")

    monkeypatch.setattr(ev.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(ev.shutil, "copytree", broken_copytree)

    with pytest.raises(ev.EvaluationError, match="复制"):
        ev._copy_library_to_temp(tmp_path)
    assert created and all(not path.exists() for path in created)


def test_cleanup_temp_dir_warns_when_locked(tmp_path: Path, monkeypatch, capsys):
    leftover = tmp_path / "leftover"
    leftover.mkdir()
    monkeypatch.setattr(ev.shutil, "rmtree", lambda *a, **k: None)
    ev._cleanup_temp_dir(leftover)
    assert "未能删除" in capsys.readouterr().err


def test_chroma_parent_uses_subprocess_on_temp_copy(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    db = tmp_path / "original-db"
    db.mkdir()
    (db / "chroma.sqlite3").write_bytes(b"sqlite")
    (db / "marker.bin").write_bytes(b"marker")
    output = tmp_path / "out.json"

    monkeypatch.setattr(ev, "_find_spec", lambda name: object())
    monkeypatch.setattr(
        ev, "build_retriever", lambda settings: pytest.fail("父进程不得构造检索器 / 打开向量库")
    )
    seen: dict = {}

    def on_run(command):
        vdb = Path(command[command.index("--vector-db") + 1])
        workspace = vdb.parent
        seen["vdb"] = vdb
        seen["copy_ready"] = (vdb / "chroma.sqlite3").is_file()
        marker = json.loads(
            (workspace / ev.WORKER_MARKER_NAME).read_text(encoding="utf-8")
        )
        seen["token_matches"] = (
            marker["token"] == command[command.index("--worker-token") + 1]
        )
        seen["marker_matches_db"] = Path(marker["vector_db"]) == vdb
        seen["marker_matches_result"] = Path(marker["result"]).name == ev.WORKER_RESULT_NAME

    launched = install_fake_chroma_child(monkeypatch, on_run=on_run)
    code = ev.run(
        [
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(db),
            "--output", str(output),
        ]
    )
    assert code == ev.EXIT_OK
    assert seen["vdb"] != db and seen["copy_ready"] is True
    assert seen["token_matches"] is True
    assert seen["marker_matches_db"] is True
    assert seen["marker_matches_result"] is True
    assert not seen["vdb"].parent.exists(), "子进程退出后必须删除临时副本"
    assert (db / "chroma.sqlite3").read_bytes() == b"sqlite"
    assert (db / "marker.bin").read_bytes() == b"marker"

    command = launched["command"]
    assert command[:3] == [ev.sys.executable, "-X", "utf8"]
    assert command[command.index("--mode") + 1] == "chroma"
    result_index = command.index("--worker-result")
    assert Path(command[result_index + 1]).name == ev.WORKER_RESULT_NAME

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["kind"] == ev.REPORT_KIND
    assert payload["library"]["opened_from"] == "temporary-copy"
    assert payload["library"]["worker"] == "subprocess"
    assert payload["library"]["vector_db"].endswith("original-db")
    assert payload["library"]["snippet_max_chars"] == 500
    assert payload["library"]["content_weight"] == 0.6
    assert payload["library"]["structure_weight"] == 0.4
    assert DRIVE_RE.search(output.read_text(encoding="utf-8")) is None


def test_chroma_child_failure_aborts_without_report(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    db = tmp_path / "original-db"
    db.mkdir()
    (db / "chroma.sqlite3").write_bytes(b"sqlite")
    output = tmp_path / "out.json"
    monkeypatch.setattr(ev, "_find_spec", lambda name: object())
    seen: dict = {}

    def on_run(command):
        seen["vdb"] = Path(command[command.index("--vector-db") + 1])

    install_fake_chroma_child(monkeypatch, returncode=2, on_run=on_run)
    code = ev.run(
        ["--mode", "chroma", "--dataset", str(dataset),
         "--vector-db", str(db), "--output", str(output)]
    )
    assert code == ev.EXIT_UNAVAILABLE
    assert not output.exists(), "子进程失败时不得写出可能被误读为通过的报告"
    assert not seen["vdb"].parent.exists()


def test_chroma_child_without_result_or_bad_result_aborts(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    db = tmp_path / "original-db"
    db.mkdir()
    (db / "chroma.sqlite3").write_bytes(b"sqlite")
    output = tmp_path / "out.json"
    monkeypatch.setattr(ev, "_find_spec", lambda name: object())

    install_fake_chroma_child(monkeypatch, write_result=False)
    code = ev.run(
        ["--mode", "chroma", "--dataset", str(dataset),
         "--vector-db", str(db), "--output", str(output)]
    )
    assert code == ev.EXIT_UNAVAILABLE
    assert not output.exists()

    install_fake_chroma_child(monkeypatch, payload={"foo": "bar"})
    code = ev.run(
        ["--mode", "chroma", "--dataset", str(dataset),
         "--vector-db", str(db), "--output", str(output)]
    )
    assert code == ev.EXIT_UNAVAILABLE
    assert not output.exists()


def make_worker_workspace(tmp_path: Path, monkeypatch, *, token: str = "unit-token"):
    """构造父进程风格的临时工作区（把系统 TEMP 指向 tmp_path）。"""
    monkeypatch.setattr(ev, "_system_temp", lambda: tmp_path.resolve())
    workspace = tmp_path / f"{ev.TEMP_PREFIX}unit"
    (workspace / "chroma").mkdir(parents=True)
    (workspace / "chroma" / "chroma.sqlite3").write_bytes(b"sqlite")
    result = workspace / ev.WORKER_RESULT_NAME
    (workspace / ev.WORKER_MARKER_NAME).write_text(
        json.dumps(
            {
                "schema_version": ev.SCHEMA_VERSION,
                "kind": ev.REPORT_KIND,
                "token": token,
                "vector_db": str(workspace / "chroma"),
                "result": str(result),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return workspace, result, token


def test_worker_rejects_original_library_and_bad_paths(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    monkeypatch.setattr(ev, "_find_spec", lambda name: object())
    monkeypatch.setattr(ev, "build_retriever", lambda settings: pytest.fail("拒绝时不得构造检索器"))

    # 1) 结果路径不在父进程工作区（系统 TEMP 直下）
    outside = tmp_path / "worker_result.json"
    code = ev.run(
        [
            "--worker-result", str(outside),
            "--worker-token", "t",
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(tmp_path / "whatever" / "chroma"),
        ]
    )
    assert code == ev.EXIT_USAGE
    assert not outside.exists()

    # 2) 看似合法的工作区，但 vector-db 指向仓库原库
    workspace, result, token = make_worker_workspace(tmp_path, monkeypatch)
    code = ev.run(
        [
            "--worker-result", str(result),
            "--worker-token", token,
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(REPO_ROOT / "vectorstore" / "chroma"),
        ]
    )
    assert code == ev.EXIT_USAGE
    assert not result.exists()
    assert (REPO_ROOT / "vectorstore" / "chroma" / "chroma.sqlite3").is_file()

    # 3) 结果文件名不符父进程约定
    code = ev.run(
        [
            "--worker-result", str(workspace / "other.json"),
            "--worker-token", token,
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(workspace / "chroma"),
        ]
    )
    assert code == ev.EXIT_USAGE
    assert not (workspace / "other.json").exists()

    # 4) keyword 模式不允许走 worker
    code = ev.run(
        [
            "--worker-result", str(result),
            "--worker-token", token,
            "--mode", "keyword",
            "--dataset", str(dataset),
            "--vector-db", str(workspace / "chroma"),
        ]
    )
    assert code == ev.EXIT_USAGE
    assert not result.exists()


def test_worker_rejects_token_mismatch_and_missing_marker(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    monkeypatch.setattr(ev, "_find_spec", lambda name: object())
    monkeypatch.setattr(ev, "build_retriever", lambda settings: pytest.fail("拒绝时不得构造检索器"))
    workspace, result, token = make_worker_workspace(tmp_path, monkeypatch)

    code = ev.run(
        [
            "--worker-result", str(result),
            "--worker-token", "wrong-token",
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(workspace / "chroma"),
        ]
    )
    assert code == ev.EXIT_USAGE
    assert not result.exists()

    (workspace / ev.WORKER_MARKER_NAME).unlink()
    code = ev.run(
        [
            "--worker-result", str(result),
            "--worker-token", token,
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(workspace / "chroma"),
        ]
    )
    assert code == ev.EXIT_USAGE
    assert not result.exists()


def test_worker_accepts_parent_workspace_and_writes_result(tmp_path: Path, monkeypatch):
    dataset = tiny_dataset(tmp_path / "cases.json")
    workspace, result, token = make_worker_workspace(tmp_path, monkeypatch)
    opened: dict = {}

    class QuietRetriever:
        def search(self, query, top_k=None):  # noqa: ARG002
            return []

    def fake_build(settings):
        opened["db"] = Path(settings.vector_db_path)
        return QuietRetriever()

    monkeypatch.setattr(ev, "_find_spec", lambda name: object())
    monkeypatch.setattr(ev, "build_retriever", fake_build)
    code = ev.run(
        [
            "--worker-result", str(result),
            "--worker-token", token,
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(workspace / "chroma"),
        ]
    )
    assert code == ev.EXIT_OK
    assert opened["db"] == workspace / "chroma"
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["kind"] == ev.REPORT_KIND
    assert payload["mode"] == "chroma"
    assert payload["library"] == {}


def test_cli_ignores_model_path_in_keyword_mode(tmp_path: Path, kb_dir: Path, capsys):
    dataset = tiny_dataset(tmp_path / "cases.json")
    output = tmp_path / "out.json"
    code = ev.run(
        ["--mode", "keyword", "--dataset", str(dataset), "--knowledge-base", str(kb_dir),
         "--output", str(output), "--model-path", "D:/models/bge-local"]
    )
    assert code == ev.EXIT_OK
    captured = capsys.readouterr()
    assert "忽略 --model-path" in captured.err
    text = output.read_text(encoding="utf-8")
    assert DRIVE_RE.search(text) is None


def test_resolve_model_path_only_converts_existing_local_relative_path(tmp_path: Path, monkeypatch):
    """模型 ID 语义保持原样；仅真实存在的本地相对路径按仓库根解析为绝对路径。"""
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    assert ev._resolve_model_path(None) is None
    assert ev._resolve_model_path("BAAI/bge-large-zh-v1.5") == "BAAI/bge-large-zh-v1.5"
    assert ev._resolve_model_path("no/such/local") == "no/such/local"
    absolute = tmp_path / "anywhere"
    assert ev._resolve_model_path(str(absolute)) == str(absolute)
    local = tmp_path / "storage" / "vector_db" / "models" / "bge"
    local.mkdir(parents=True)
    assert Path(ev._resolve_model_path("storage/vector_db/models/bge")) == local.resolve()


def test_chroma_child_receives_repo_root_resolved_model_path(tmp_path: Path, monkeypatch):
    """异地 CWD 执行时，相对本地模型路径必须按仓库根解析后再传给子进程。"""
    repo = tmp_path / "repo"
    model_dir = repo / "models" / "bge"
    model_dir.mkdir(parents=True)
    monkeypatch.setattr(ev, "REPO_ROOT", repo)

    dataset = tiny_dataset(tmp_path / "cases.json")
    db = tmp_path / "original-db"
    db.mkdir()
    (db / "chroma.sqlite3").write_bytes(b"sqlite")
    output = tmp_path / "out.json"
    monkeypatch.setattr(ev, "_find_spec", lambda name: object())
    launched = install_fake_chroma_child(monkeypatch)

    foreign_cwd = tmp_path / "elsewhere"
    foreign_cwd.mkdir()
    monkeypatch.chdir(foreign_cwd)

    code = ev.run(
        [
            "--mode", "chroma",
            "--dataset", str(dataset),
            "--vector-db", str(db),
            "--model-path", "models/bge",
            "--output", str(output),
        ]
    )
    assert code == ev.EXIT_OK
    command = launched["command"]
    sent = Path(command[command.index("--model-path") + 1])
    assert sent.is_absolute(), "异地 CWD 时相对本地模型路径必须解析为绝对路径"
    assert sent == model_dir.resolve()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["library"]["embedding_model"] == "bge"
