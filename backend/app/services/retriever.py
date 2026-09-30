"""检索实现（学生 C 第 1 阶段）。

两种显式模式，不互相静默回退：
- KeywordRetriever：读取 KNOWLEDGE_BASE_DIR 下的 md/txt，启发式词元匹配（中文双字词 +
  英文/数字单词）。零 embedding 依赖，供本机开发默认使用。排序用 IDF 加权覆盖度 +
  命中强度，并带有通用低相关门槛（min_coverage）；分数是启发式相关度，不是向量相似度。
- ChromaRetriever：只读查询（不创建集合、不执行 add / delete / rebuild）B 的
  school_documents_content / school_documents_structure
  集合，显式 query_embeddings，双路按 ID 加权融合；结构路命中时从内容集合取正文，
  摘要不会当正文使用。缺依赖 / 缺目录 / 缺集合 / 向量库或模型故障都会明确抛
  RetrieverUnavailable（接口层 503），不静默换模式。
"""

from __future__ import annotations

import logging
import math
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.core.config import REPO_ROOT, Settings

logger = logging.getLogger(__name__)

DEFAULT_SNIPPET_CHARS = 500
DEFAULT_CHROMA_MIN_SCORE = 0.35
DEFAULT_KEYWORD_MIN_COVERAGE = 0.2
MAX_TOP_K = 10
_SUPPORTED_EXTENSIONS = (".md", ".txt")
# 合并后的段落上限，避免"未完结段落全部合并"把整篇文档变成一个超长块
_MAX_PARAGRAPH_CHARS = 1200

_ASCII_WORD_RE = re.compile(r"[a-z0-9_]+")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
_LIST_ITEM_RE = re.compile(
    r"^(?:[（(]\s*[一二三四五六七八九十百0-9]+\s*[）)]|[0-9]+\s*[.、]|[①②③④⑤⑥⑦⑧⑨⑩]|[·•\-*]\s)"
)
_STRONG_END_RE = re.compile(r"[。！？!?]$")


class RetrieverUnavailable(RuntimeError):
    """检索暂不可用（目录缺失 / 依赖缺失 / 集合缺失 / 向量库故障等），接口层映射为 503。"""


@dataclass
class RetrievedChunk:
    """一条检索结果；source 为安全的仓库相对路径，不含盘符。"""

    chunk_id: str
    title: str
    source: str
    text: str
    score: float


def bounded_top_k(value: int | None, default: int = 5) -> int:
    """把 top_k 限制在 1..MAX_TOP_K。"""
    if value is None:
        value = default
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, MAX_TOP_K))


def _safe_source(path_like: Any) -> str:
    """把元数据里的路径变成不泄露盘符 / 用户目录的相对来源。"""
    raw = str(path_like or "").replace("\\", "/").strip()
    if not raw:
        return ""
    marker = "knowledge_base/"
    index = raw.lower().find(marker)
    if index >= 0:
        return raw[index:]
    if re.match(r"^[a-zA-Z]:/", raw):
        return Path(raw).name
    return raw.rsplit("/", 1)[-1]


def _repo_relative(path: Path, fallback_root: Path) -> str:
    """优先输出仓库相对路径；临时目录场景退回相对 fallback_root 或纯文件名。"""
    resolved = path.resolve()
    for root in (REPO_ROOT, fallback_root):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    return path.name


# ---------------------------------------------------------------- keyword 模式


def _query_terms(text: str) -> dict[str, float]:
    """中文友好词元：英文/数字词 + 中文双字词 + 短整段短语（权重更高）。"""
    lowered = text.lower()
    terms: dict[str, float] = {}
    for match in _ASCII_WORD_RE.finditer(lowered):
        word = match.group(0)
        if len(word) >= 2:
            terms[word] = max(terms.get(word, 0.0), 1.5)
    for match in _CJK_RUN_RE.finditer(lowered):
        run = match.group(0)
        if len(run) == 1:
            terms[run] = max(terms.get(run, 0.0), 0.5)
            continue
        if len(run) <= 8:
            terms[run] = max(terms.get(run, 0.0), 3.0)
        for index in range(len(run) - 1):
            bigram = run[index : index + 2]
            terms[bigram] = max(terms.get(bigram, 0.0), 1.0)
    return terms


def _score_paragraph(
    paragraph: str,
    terms: dict[str, float],
    idf: dict[str, float],
    idf_cap: float,
    title_lower: str,
) -> tuple[float, float]:
    """返回 (coverage, score)。

    coverage = 命中词元的 IDF 权重 / 查询词元的 IDF 总权重，用来做通用低相关门槛；
    score 再叠加命中强度与标题命中，限制在 0..1 便于排序。
    """
    text = paragraph.lower()
    total_idf = 0.0
    matched_idf = 0.0
    hits = 0.0
    title_matched_idf = 0.0
    for term in terms:
        term_idf = idf.get(term, idf_cap)
        total_idf += term_idf
        count = text.count(term)
        if not count:
            continue
        matched_idf += term_idf
        hits += term_idf * min(count, 3)
        if term in title_lower:
            title_matched_idf += term_idf
    if total_idf <= 0 or matched_idf <= 0:
        return 0.0, 0.0
    coverage = matched_idf / total_idf
    strength = min(1.0, hits / (3.0 * total_idf))
    title_bonus = min(1.0, title_matched_idf / total_idf)
    score = 0.7 * coverage + 0.25 * strength + 0.05 * title_bonus
    return coverage, score


def _split_paragraphs(text: str) -> list[str]:
    """切成有界的检索段落，并保持相邻条款 / 列举的关联。

    - 空行分块；
    - 标题块并入紧随其后的正文，但正文结束后标题不会继续"粘住"后续条款；
    - 列举项（（一）/ 1. / ① / ·）并入上一段，如"处分种类分为："+ 红色列表；
    - 上一段没有句末标点时并入下一段（原文里条款被空行截断的情况）。
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_blocks: list[str] = []
    for block in re.split(r"\n\s*\n", normalized):
        line = " ".join(part.strip() for part in block.split("\n") if part.strip())
        if line:
            raw_blocks.append(line)

    paragraphs: list[str] = []
    current = ""
    current_is_heading = False
    for block in raw_blocks:
        block_is_heading = bool(_HEADING_RE.match(block))
        if not current:
            current = block
            current_is_heading = block_is_heading
            continue
        is_list_item = bool(_LIST_ITEM_RE.match(block))
        unfinished = not _STRONG_END_RE.search(current)
        should_merge = (current_is_heading or is_list_item or unfinished) and not (
            block_is_heading and not current_is_heading
        )
        if should_merge and len(current) + len(block) + 1 <= _MAX_PARAGRAPH_CHARS:
            current = f"{current} {block}"
            current_is_heading = False
        else:
            if len(current) >= 4:
                paragraphs.append(current)
            current = block
            current_is_heading = block_is_heading
    if current and len(current) >= 4:
        paragraphs.append(current)
    return paragraphs


def _extract_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            return match.group(1).strip()
    return path.stem


def _match_positions(paragraph: str, terms: dict[str, float]) -> list[int]:
    lowered = paragraph.lower()
    positions = [lowered.find(term) for term in terms]
    return [position for position in positions if position >= 0]


def _bounded_snippet(text: str, limit: int, positions: list[int] | None = None) -> str:
    """严格不超过 limit 个字符；长段落优先把命中词周围的内容截进来。"""
    if len(text) <= limit:
        return text
    if limit <= 1:
        return "…"[:limit]
    position = min(positions) if positions else None
    if position is None or position < limit - 1:
        return text[: limit - 1] + "…"
    # 先取一个围绕命中的候选窗口，再按省略号占位收缩，保证命中词留在窗口内
    start = max(0, position - limit // 3)
    end = min(len(text), start + limit)
    start = max(0, end - limit)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    budget = max(1, limit - len(prefix) - len(suffix))
    start = max(0, position - budget // 2)
    start = min(start, max(0, len(text) - budget))
    end = start + budget
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


@dataclass
class _KeywordDoc:
    title: str
    source: str
    paragraphs: list[str]


class KeywordRetriever:
    """无 embedding 依赖的本地文本检索（启发式，不冒充向量检索）。"""

    def __init__(
        self,
        knowledge_base_dir: Path | str,
        *,
        top_k: int = 5,
        snippet_max_chars: int = DEFAULT_SNIPPET_CHARS,
        min_score: float = 0.0,
        min_coverage: float = DEFAULT_KEYWORD_MIN_COVERAGE,
    ) -> None:
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.top_k = bounded_top_k(top_k)
        self.snippet_max_chars = max(50, int(snippet_max_chars))
        self.min_score = float(min_score)
        self.min_coverage = float(min_coverage)
        self._docs: list[_KeywordDoc] | None = None
        self._idf: dict[str, float] = {}
        self._idf_cap = 0.0
        self._lock = threading.Lock()

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        limit = bounded_top_k(self.top_k if top_k is None else top_k)
        docs = self._load_docs()
        terms = _query_terms(query)
        if not terms or not docs:
            return []
        ranked: list[tuple[float, float, RetrievedChunk]] = []
        for doc in docs:
            title_lower = doc.title.lower()
            for position, paragraph in enumerate(doc.paragraphs):
                coverage, score = _score_paragraph(
                    paragraph, terms, self._idf, self._idf_cap, title_lower
                )
                if coverage < self.min_coverage or score <= self.min_score:
                    continue
                ranked.append(
                    (
                        coverage,
                        score,
                        RetrievedChunk(
                            chunk_id=f"{doc.source}#p{position}",
                            title=doc.title,
                            source=doc.source,
                            text=_bounded_snippet(
                                paragraph, self.snippet_max_chars, _match_positions(paragraph, terms)
                            ),
                            score=round(score, 4),
                        ),
                    )
                )
        ranked.sort(key=lambda item: (-item[1], -item[0], item[2].source, item[2].chunk_id))
        return [item[2] for item in ranked[:limit]]

    def _load_docs(self) -> list[_KeywordDoc]:
        """惰性加载知识库文档与 IDF 统计；目录缺失 / 全部不可读时抛 503。"""
        docs = self._docs
        if docs is not None:
            return docs
        with self._lock:
            if self._docs is None:
                self._docs = self._build_index()
        return self._docs

    def _build_index(self) -> list[_KeywordDoc]:
        root = self.knowledge_base_dir
        if not root.is_dir():
            raise RetrieverUnavailable("知识库目录不存在，请检查 KNOWLEDGE_BASE_DIR 配置")
        try:
            files = [path for ext in _SUPPORTED_EXTENSIONS for path in sorted(root.rglob(f"*{ext}"))]
        except OSError as exc:
            raise RetrieverUnavailable("知识库目录不可读取，请检查目录权限") from exc

        # 排除 README（大小写不敏感），只保留真实文档文件
        files = [path for path in files if path.is_file() and "readme" not in path.stem.lower()]

        docs: list[_KeywordDoc] = []
        failed = 0
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                failed += 1
                logger.warning("跳过不可读取的知识库文件 %s：%s", path.name, exc)
                continue
            paragraphs = _split_paragraphs(text)
            if not paragraphs:
                continue
            docs.append(
                _KeywordDoc(
                    title=_extract_title(text, path),
                    source=_repo_relative(path, root),
                    paragraphs=paragraphs,
                )
            )

        if files and not docs and failed == len(files):
            raise RetrieverUnavailable("知识库文件均不可读取，请检查文件编码与权限")
        if not docs:
            logger.warning("知识库为空或没有可检索的 md/txt 文档：%s", root.name)

        # 段落级 IDF：高频通用词权重低，避免"学生"这类词淹没关键问题
        document_frequency: dict[str, int] = {}
        paragraph_count = 0
        for doc in docs:
            for paragraph in doc.paragraphs:
                paragraph_count += 1
                for term in _query_terms(paragraph):
                    document_frequency[term] = document_frequency.get(term, 0) + 1
        self._idf = {
            term: math.log(1.0 + paragraph_count / (1.0 + freq))
            for term, freq in document_frequency.items()
        }
        # 未登录词与极罕见词按 df=2 封顶，避免生僻组合无限抬高覆盖度分母
        self._idf_cap = math.log(1.0 + paragraph_count / 2.0) if paragraph_count else 0.0
        return docs


# ---------------------------------------------------------------- chroma 模式


class _SentenceTransformerEmbedder:
    """仅本地加载的句向量封装（不会联网下载模型）。"""

    def __init__(self, model: Any) -> None:
        self.model = model

    def encode_one(self, text: str) -> list[float]:
        vectors = self.model.encode([text], normalize_embeddings=True, batch_size=1)
        vector = vectors[0]
        return vector.tolist() if hasattr(vector, "tolist") else list(vector)


class ChromaRetriever:
    """双路向量检索适配器，直接适配 B 的 *_content / *_structure 集合。

    注意：只读查询——不创建集合、不执行 add / delete / rebuild、不下载模型
    （local_files_only）；查询通过 chromadb 打开持久化目录，可能触发底层元数据
    维护，联调旧库前请先备份。缺依赖 / 缺目录 / 缺集合 / 查询失败都明确报 503，
    不静默回退 keyword 模式；客户端与嵌入模型惰性初始化并加锁，避免并发首请求
    重复加载模型。
    """

    def __init__(
        self,
        persist_directory: Path | str,
        *,
        content_collection_name: str = "school_documents_content",
        structure_collection_name: str = "school_documents_structure",
        embedding_model: str = "BAAI/bge-large-zh-v1.5",
        device: str = "cpu",
        top_k: int = 5,
        snippet_max_chars: int = DEFAULT_SNIPPET_CHARS,
        min_score: float = DEFAULT_CHROMA_MIN_SCORE,
        content_weight: float = 0.6,
        structure_weight: float = 0.4,
        embedder: Any | None = None,
        client_factory: Callable[[Path], Any] | None = None,
    ) -> None:
        self.persist_directory = Path(persist_directory)
        self.content_collection_name = content_collection_name
        self.structure_collection_name = structure_collection_name
        self.embedding_model = embedding_model
        self.device = device
        self.top_k = bounded_top_k(top_k)
        self.snippet_max_chars = max(50, int(snippet_max_chars))
        self.min_score = float(min_score)
        self.content_weight = float(content_weight)
        self.structure_weight = float(structure_weight)
        self._embedder = embedder
        self._client_factory = client_factory
        self._client: Any | None = None
        self._lock = threading.Lock()

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        limit = bounded_top_k(self.top_k if top_k is None else top_k)
        client = self._get_client()
        content = self._get_collection(client, self.content_collection_name)
        structure = self._get_collection(client, self.structure_collection_name)
        if _collection_count(content) == 0 and _collection_count(structure) == 0:
            return []

        try:
            vector = self._get_embedder().encode_one(query)
        except RetrieverUnavailable:
            raise
        except Exception as exc:
            logger.warning("查询向量生成失败：%s", type(exc).__name__)
            raise RetrieverUnavailable("查询向量生成失败，请确认嵌入模型可用且与向量库匹配") from exc

        pool = min(max(limit * 2, limit), 20)
        content_hits = self._query(content, vector, pool)
        structure_hits = self._query(structure, vector, pool)

        merged: dict[str, dict[str, Any]] = {}
        for hit in content_hits:
            merged[hit["id"]] = {
                "text": hit["document"],
                "metadata": hit["metadata"],
                "content_score": hit["score"],
                "structure_score": 0.0,
            }
        for hit in structure_hits:
            entry = merged.get(hit["id"])
            if entry is None:
                # structure-only：保留结构路分数，正文稍后从 content 集合取
                merged[hit["id"]] = {
                    "text": None,
                    "metadata": hit["metadata"],
                    "content_score": 0.0,
                    "structure_score": hit["score"],
                }
            else:
                entry["structure_score"] = max(entry["structure_score"], hit["score"])

        results: list[RetrievedChunk] = []
        for chunk_id, entry in merged.items():
            combined = (
                self.content_weight * entry["content_score"]
                + self.structure_weight * entry["structure_score"]
            )
            if combined < self.min_score:
                continue
            text = entry["text"]
            metadata = entry["metadata"] or {}
            if text is None:
                # structure-only：必须从 content 集合取正文，取不到就丢弃
                fetched = self._fetch_content(content, chunk_id)
                if fetched is None:
                    logger.warning("结构路命中 %s 缺少内容集合正文，已跳过", chunk_id)
                    continue
                text, metadata = fetched
            if not isinstance(text, str) or not text.strip():
                continue
            source = _safe_source(metadata.get("file_path") or metadata.get("file_name"))
            title = str(metadata.get("title") or (Path(source).stem if source else "未知文档"))
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    title=title,
                    source=source,
                    text=_bounded_snippet(text, self.snippet_max_chars),
                    score=round(combined, 4),
                )
            )
        results.sort(key=lambda item: (-item.score, item.source, item.chunk_id))
        return results[:limit]

    # ------------------------------------------------------------ 内部工具

    def _get_client(self) -> Any:
        client = self._client
        if client is not None:
            return client
        with self._lock:
            if self._client is None:
                self._client = self._create_client()
        return self._client

    def _create_client(self) -> Any:
        path = self.persist_directory
        if not path.is_dir():
            raise RetrieverUnavailable("向量库目录不存在，请检查 VECTOR_DB_PATH 配置")
        if not (path / "chroma.sqlite3").is_file():
            raise RetrieverUnavailable("向量库目录中没有 chroma.sqlite3，向量库可能尚未构建")
        if self._client_factory is not None:
            try:
                return self._client_factory(path)
            except RetrieverUnavailable:
                raise
            except Exception as exc:
                logger.warning("向量库客户端初始化失败：%s", type(exc).__name__)
                raise RetrieverUnavailable("初始化向量库客户端失败，请检查向量库配置与文件完整性") from exc
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as exc:
            raise RetrieverUnavailable("未安装 chromadb，无法使用 chroma 检索模式") from exc
        try:
            return chromadb.PersistentClient(
                path=str(path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except Exception as exc:
            logger.warning("向量库客户端初始化失败：%s", type(exc).__name__)
            raise RetrieverUnavailable("初始化向量库客户端失败，请检查向量库配置与文件完整性") from exc

    def _get_collection(self, client: Any, name: str) -> Any:
        try:
            return client.get_collection(name=name)
        except Exception as exc:
            logger.warning("读取集合 %s 失败：%s", name, type(exc).__name__)
            raise RetrieverUnavailable(f"向量库中缺少集合 {name}，请先构建向量库") from exc

    def _get_embedder(self) -> Any:
        embedder = self._embedder
        if embedder is not None:
            return embedder
        with self._lock:
            if self._embedder is None:
                self._embedder = self._create_embedder()
        return self._embedder

    def _create_embedder(self) -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RetrieverUnavailable("未安装 sentence-transformers，无法使用 chroma 检索模式") from exc
        try:
            model = SentenceTransformer(
                self.embedding_model,
                device=self.device,
                local_files_only=True,
            )
        except Exception as exc:
            logger.warning("本地嵌入模型加载失败：%s", type(exc).__name__)
            raise RetrieverUnavailable(
                "嵌入模型不可用：本地未找到模型文件，且当前配置不允许联网下载"
            ) from exc
        return _SentenceTransformerEmbedder(model)

    def _query(self, collection: Any, vector: list[float], n_results: int) -> list[dict[str, Any]]:
        try:
            raw = collection.query(
                query_embeddings=[vector],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("向量检索失败：%s", type(exc).__name__)
            raise RetrieverUnavailable("向量检索失败，请确认向量库与嵌入模型版本一致") from exc
        return _flatten_chroma_result(raw)

    def _fetch_content(self, collection: Any, chunk_id: str) -> tuple[str, dict[str, Any]] | None:
        """读取内容集合正文。

        - 数据库/客户端异常或返回结构异常 → RetrieverUnavailable（503）；
        - ID 不存在或正文为空 → None，由调用方按“缺正文”跳过。
        """
        try:
            raw = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
        except Exception as exc:
            logger.warning("读取内容集合失败：%s", type(exc).__name__)
            raise RetrieverUnavailable("读取向量库内容集合失败，请检查向量库文件是否完整") from exc
        if not isinstance(raw, dict):
            logger.warning("内容集合返回格式异常：%s", type(raw).__name__)
            raise RetrieverUnavailable("读取向量库内容集合失败，请检查向量库文件是否完整")
        documents = raw.get("documents") or []
        metadatas = raw.get("metadatas") or []
        document = documents[0] if documents else None
        if not isinstance(document, str) or not document.strip():
            return None
        metadata = metadatas[0] if metadatas and isinstance(metadatas[0], dict) else {}
        return document, metadata


def _collection_count(collection: Any) -> int:
    """读取集合数量；失败说明向量库/连接有问题，明确抛 503 而不是当作空库。"""
    try:
        return int(collection.count())
    except Exception as exc:
        logger.warning("读取集合数量失败：%s", type(exc).__name__)
        raise RetrieverUnavailable("读取向量库集合失败，请检查向量库文件是否完整") from exc


def _flatten_chroma_result(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    ids = (raw.get("ids") or [[]])[0] or []
    documents = (raw.get("documents") or [[]])[0] or []
    metadatas = (raw.get("metadatas") or [[]])[0] or []
    distances = (raw.get("distances") or [[]])[0] or []
    hits: list[dict[str, Any]] = []
    for position, chunk_id in enumerate(ids):
        if not chunk_id:
            continue
        document = documents[position] if position < len(documents) else None
        metadata = metadatas[position] if position < len(metadatas) else None
        distance = 1.0
        if position < len(distances) and distances[position] is not None:
            try:
                distance = float(distances[position])
            except (TypeError, ValueError):
                distance = 1.0
        hits.append(
            {
                "id": str(chunk_id),
                "document": document,
                "metadata": metadata if isinstance(metadata, dict) else {},
                "score": 1.0 / (1.0 + max(distance, 0.0)),
            }
        )
    return hits


def build_retriever(settings: Settings) -> KeywordRetriever | ChromaRetriever:
    """按配置构造检索器；未知模式直接报错，不静默回退。"""
    mode = (settings.retrieval_mode or "").strip().lower()
    if mode == "keyword":
        return KeywordRetriever(
            settings.knowledge_base_dir,
            top_k=settings.top_k,
            snippet_max_chars=settings.snippet_max_chars,
            min_score=settings.score_threshold or 0.0,
            min_coverage=settings.min_coverage,
        )
    if mode == "chroma":
        min_score = DEFAULT_CHROMA_MIN_SCORE if settings.score_threshold is None else settings.score_threshold
        return ChromaRetriever(
            settings.vector_db_path,
            content_collection_name=settings.content_collection_name,
            structure_collection_name=settings.structure_collection_name,
            embedding_model=settings.embedding_model_name,
            device=settings.embedding_device,
            top_k=settings.top_k,
            snippet_max_chars=settings.snippet_max_chars,
            min_score=min_score,
            content_weight=settings.content_weight,
            structure_weight=settings.structure_weight,
        )
    raise RetrieverUnavailable(
        f"不支持的 RETRIEVAL_MODE：{settings.retrieval_mode}（仅支持 keyword 或 chroma）"
    )
