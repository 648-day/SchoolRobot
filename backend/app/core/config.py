"""后端运行时配置（学生 C 第 1 阶段）。

约定：
- 默认读取 backend/.env（若存在），已存在的进程环境变量优先（override=False）。
- 所有相对路径以仓库根目录为基准解析，不依赖当前工作目录 CWD。
- 只读取配置，不打印、不输出任何配置值，避免泄露本地环境信息。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv 已在 backend/requirements.txt 中声明
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失时退化为只读环境变量
    load_dotenv = None  # type: ignore[assignment]

# backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend, [3]=仓库根
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
DEFAULT_ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_PROMPT_FILE = BACKEND_DIR / "app" / "prompts" / "rag_base.txt"

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL_NAME = "qwen3.5:4b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 15.0
DEFAULT_KNOWLEDGE_BASE_DIR = REPO_ROOT / "knowledge_base" / "cleaned"
DEFAULT_VECTOR_DB_PATH = REPO_ROOT / "storage" / "vector_db" / "chroma"
DEFAULT_EMBEDDING_MODEL_NAME = "BAAI/bge-large-zh-v1.5"
DEFAULT_CONTENT_COLLECTION = "school_documents_content"
DEFAULT_STRUCTURE_COLLECTION = "school_documents_structure"
DEFAULT_CORS_ORIGINS = ("http://localhost:3333", "http://127.0.0.1:3333")

TOP_K_MIN = 1
TOP_K_MAX = 10

_TRUE_VALUES = {"1", "true", "yes", "on"}


def resolve_repo_path(value: str | os.PathLike[str]) -> Path:
    """把相对路径按仓库根解析；绝对路径原样保留。"""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _env(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def _env_str(name: str, default: str) -> str:
    return _env(name) or default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in _TRUE_VALUES


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


@dataclass
class Settings:
    """运行时配置（全部可由环境变量覆盖）。"""

    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    model_name: str = DEFAULT_MODEL_NAME
    ollama_timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS
    ollama_think: bool = False

    retrieval_mode: str = "keyword"
    knowledge_base_dir: Path = DEFAULT_KNOWLEDGE_BASE_DIR
    vector_db_path: Path = DEFAULT_VECTOR_DB_PATH
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL_NAME
    embedding_device: str = "cpu"
    content_collection_name: str = DEFAULT_CONTENT_COLLECTION
    structure_collection_name: str = DEFAULT_STRUCTURE_COLLECTION

    top_k: int = 5
    snippet_max_chars: int = 500
    max_context_chars: int = 6000
    score_threshold: float | None = None
    min_coverage: float = 0.2
    content_weight: float = 0.6
    structure_weight: float = 0.4

    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    prompt_file: Path = DEFAULT_PROMPT_FILE

    @classmethod
    def from_env(cls, env_file: Path | str | None = None) -> "Settings":
        """从环境变量构造配置；env_file 默认 backend/.env，环境变量优先。"""
        dotenv_path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
        if load_dotenv is not None and dotenv_path.is_file():
            # override=False：进程环境变量优先，.env 只补充缺失项
            load_dotenv(dotenv_path, override=False)

        timeout = _env_float("OLLAMA_TIMEOUT_SECONDS", DEFAULT_OLLAMA_TIMEOUT_SECONDS)
        if timeout <= 0:
            timeout = DEFAULT_OLLAMA_TIMEOUT_SECONDS

        origins_raw = _env("CORS_ORIGINS")
        if origins_raw:
            cors_origins = tuple(item.strip() for item in origins_raw.split(",") if item.strip())
        else:
            cors_origins = DEFAULT_CORS_ORIGINS

        threshold_raw = _env("SCORE_THRESHOLD")
        threshold: float | None = None
        if threshold_raw is not None:
            try:
                threshold = float(threshold_raw)
            except ValueError:
                threshold = None

        top_k = _env_int("TOP_K", 5)
        top_k = max(TOP_K_MIN, min(top_k, TOP_K_MAX))

        min_coverage = _env_float("MIN_COVERAGE", 0.2)
        min_coverage = max(0.0, min(min_coverage, 1.0))

        return cls(
            ollama_base_url=_env_str("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/"),
            model_name=_env_str("MODEL_NAME", DEFAULT_MODEL_NAME),
            ollama_timeout_seconds=timeout,
            ollama_think=_env_bool("OLLAMA_THINK", False),
            retrieval_mode=_env_str("RETRIEVAL_MODE", "keyword").lower(),
            knowledge_base_dir=resolve_repo_path(_env_str("KNOWLEDGE_BASE_DIR", "knowledge_base/cleaned")),
            vector_db_path=resolve_repo_path(_env_str("VECTOR_DB_PATH", "storage/vector_db/chroma")),
            embedding_model_name=_env_str("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL_NAME),
            embedding_device=_env_str("EMBEDDING_DEVICE", "cpu"),
            content_collection_name=_env_str("CONTENT_COLLECTION_NAME", DEFAULT_CONTENT_COLLECTION),
            structure_collection_name=_env_str("STRUCTURE_COLLECTION_NAME", DEFAULT_STRUCTURE_COLLECTION),
            top_k=top_k,
            snippet_max_chars=max(50, _env_int("SNIPPET_MAX_CHARS", 500)),
            max_context_chars=max(200, _env_int("MAX_CONTEXT_CHARS", 6000)),
            score_threshold=threshold,
            min_coverage=min_coverage,
            content_weight=_env_float("CONTENT_WEIGHT", 0.6),
            structure_weight=_env_float("STRUCTURE_WEIGHT", 0.4),
            cors_origins=cors_origins,
            prompt_file=DEFAULT_PROMPT_FILE,
        )
