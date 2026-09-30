"""配置模块测试：.env 加载、环境变量优先、路径解析不依赖 CWD、边界收敛。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import REPO_ROOT, Settings

C_ENV_KEYS = (
    "OLLAMA_BASE_URL",
    "MODEL_NAME",
    "OLLAMA_TIMEOUT_SECONDS",
    "OLLAMA_THINK",
    "RETRIEVAL_MODE",
    "KNOWLEDGE_BASE_DIR",
    "VECTOR_DB_PATH",
    "EMBEDDING_MODEL_NAME",
    "EMBEDDING_DEVICE",
    "CONTENT_COLLECTION_NAME",
    "STRUCTURE_COLLECTION_NAME",
    "TOP_K",
    "SNIPPET_MAX_CHARS",
    "MAX_CONTEXT_CHARS",
    "SCORE_THRESHOLD",
    "MIN_COVERAGE",
    "CONTENT_WEIGHT",
    "STRUCTURE_WEIGHT",
    "CORS_ORIGINS",
)


@pytest.fixture
def clean_env(monkeypatch):
    for key in C_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_defaults(clean_env, tmp_path):
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert settings.model_name == "qwen3.5:4b"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_timeout_seconds == 15.0
    assert settings.ollama_think is False
    assert settings.retrieval_mode == "keyword"
    assert settings.top_k == 5
    assert settings.knowledge_base_dir == REPO_ROOT / "knowledge_base" / "cleaned"
    assert settings.vector_db_path == REPO_ROOT / "storage" / "vector_db" / "chroma"
    assert settings.embedding_model_name == "BAAI/bge-large-zh-v1.5"
    assert settings.embedding_device == "cpu"
    assert settings.content_collection_name == "school_documents_content"
    assert settings.structure_collection_name == "school_documents_structure"
    assert settings.score_threshold is None
    assert settings.content_weight == 0.6
    assert settings.structure_weight == 0.4


def test_env_overrides_dotenv(clean_env, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MODEL_NAME=dotenv-model\nOLLAMA_BASE_URL=http://dotenv-host:11434\n",
        encoding="utf-8",
    )
    clean_env.setenv("MODEL_NAME", "env-model")
    settings = Settings.from_env(env_file=env_file)
    # 进程环境变量优先
    assert settings.model_name == "env-model"
    # .env 补充缺失项
    assert settings.ollama_base_url == "http://dotenv-host:11434"


def test_relative_paths_resolve_from_repo_root(clean_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # CWD 改为临时目录，结果不应变化
    clean_env.setenv("KNOWLEDGE_BASE_DIR", "knowledge_base/cleaned")
    clean_env.setenv("VECTOR_DB_PATH", "storage/vector_db/chroma")
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert settings.knowledge_base_dir == REPO_ROOT / "knowledge_base" / "cleaned"
    assert settings.vector_db_path == REPO_ROOT / "storage" / "vector_db" / "chroma"


def test_absolute_path_kept(clean_env, tmp_path):
    custom = tmp_path / "custom_kb"
    clean_env.setenv("KNOWLEDGE_BASE_DIR", str(custom))
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert settings.knowledge_base_dir == custom.resolve()


def test_invalid_and_out_of_range_values(clean_env, tmp_path):
    clean_env.setenv("OLLAMA_TIMEOUT_SECONDS", "abc")
    clean_env.setenv("TOP_K", "999")
    clean_env.setenv("SNIPPET_MAX_CHARS", "10")
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert settings.ollama_timeout_seconds == 15.0  # 非法值回退默认
    assert settings.top_k == 10  # 上限收敛
    assert settings.snippet_max_chars == 50  # 下限收敛

    clean_env.setenv("TOP_K", "0")
    assert Settings.from_env(env_file=tmp_path / "missing.env").top_k == 1

    clean_env.setenv("OLLAMA_TIMEOUT_SECONDS", "-3")
    assert Settings.from_env(env_file=tmp_path / "missing.env").ollama_timeout_seconds == 15.0


def test_score_threshold_optional(clean_env, tmp_path):
    assert Settings.from_env(env_file=tmp_path / "missing.env").score_threshold is None
    clean_env.setenv("SCORE_THRESHOLD", "0.4")
    assert Settings.from_env(env_file=tmp_path / "missing.env").score_threshold == 0.4
    clean_env.setenv("SCORE_THRESHOLD", "not-a-number")
    assert Settings.from_env(env_file=tmp_path / "missing.env").score_threshold is None


def test_think_parsing(clean_env, tmp_path):
    for raw, expected in (("true", True), ("1", True), ("yes", True), ("on", True), ("false", False), ("0", False)):
        clean_env.setenv("OLLAMA_THINK", raw)
        settings = Settings.from_env(env_file=tmp_path / "missing.env")
        assert settings.ollama_think is expected, raw


def test_cors_defaults_are_explicit(clean_env, tmp_path):
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert "*" not in settings.cors_origins
    assert "http://localhost:3333" in settings.cors_origins
    assert "http://127.0.0.1:3333" in settings.cors_origins

    clean_env.setenv("CORS_ORIGINS", "http://a:1, http://b:2")
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert settings.cors_origins == ("http://a:1", "http://b:2")


def test_min_coverage_default_and_override(clean_env, tmp_path):
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert settings.min_coverage == 0.2
    clean_env.setenv("MIN_COVERAGE", "0.35")
    assert Settings.from_env(env_file=tmp_path / "missing.env").min_coverage == 0.35
    clean_env.setenv("MIN_COVERAGE", "9")
    assert Settings.from_env(env_file=tmp_path / "missing.env").min_coverage == 1.0
    clean_env.setenv("MIN_COVERAGE", "-1")
    assert Settings.from_env(env_file=tmp_path / "missing.env").min_coverage == 0.0


def test_retrieval_mode_lowercased(clean_env, tmp_path):
    clean_env.setenv("RETRIEVAL_MODE", "Chroma")
    settings = Settings.from_env(env_file=tmp_path / "missing.env")
    assert settings.retrieval_mode == "chroma"
