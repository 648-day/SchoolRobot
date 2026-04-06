# -*- coding: utf-8 -*-
"""
向量化和向量库模块。

该模块负责：
- BGE中文向量模型集成
- 文本向量转换
- Chroma向量数据库初始化和持久化
- 向量库CRUD操作

作者: AI Assistant
日期: 2026-04-02
"""

import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger("VectorDBBuilder.VectorStore")


@dataclass
class EmbeddingResult:
    """向量嵌入结果类。"""
    success: bool
    chunk_index: int
    embedding: Optional[List[float]]
    error_message: Optional[str] = None
    embedding_time: float = 0.0


@dataclass
class VectorStoreStats:
    """向量库统计信息类。"""
    total_chunks: int
    total_documents: int
    collection_name: str
    persist_directory: str
    embedding_model: str
    build_time: float
    avg_embedding_time: float


class BGEEmbeddings:
    """BGE中文嵌入模型封装类。"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        model_kwargs: Optional[Dict[str, Any]] = None,
        encode_kwargs: Optional[Dict[str, Any]] = None
    ):
        """
        初始化BGE嵌入模型。
        """
        self.model_name = model_name
        if model_kwargs is None:
            model_kwargs = {"device": "cuda"}
        elif "device" not in model_kwargs:
            model_kwargs["device"] = "cuda"
        self.model_kwargs = model_kwargs
        self.encode_kwargs = encode_kwargs or {"normalize_embeddings": True, "batch_size": 8}
        self.model = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self) -> None:
        """加载BGE模型（带立即输出日志）。"""
        import sys
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            print("=" * 60, flush=True)
            print("开始加载模型（首次运行需下载模型，请耐心等待）...", flush=True)
            print("=" * 60, flush=True)

            # 检查GPU可用性
            gpu_available = torch.cuda.is_available()
            gpu_count = torch.cuda.device_count() if gpu_available else 0

            if gpu_available:
                current_device = torch.cuda.current_device()
                gpu_name = torch.cuda.get_device_name(current_device)
                gpu_memory = torch.cuda.get_device_properties(current_device).total_memory / (1024**3)
                print(f"[1/4] GPU检测: {gpu_name}, 显存: {gpu_memory:.1f}GB", flush=True)
            else:
                print("[1/4] GPU不可用，将使用CPU", flush=True)

            print(f"[2/4] 模型: {self.model_name}", flush=True)
            print(f"       镜像: {os.environ.get('HF_ENDPOINT', 'default')}", flush=True)

            load_start = time.time()
            print("[3/4] 正在下载模型（约100MB）...", flush=True)
            print("       如果长时间无响应，请检查网络或按 Ctrl+C 取消", flush=True)

            self.model = SentenceTransformer(self.model_name, **self.model_kwargs)
            self.tokenizer = self.model.tokenizer
            load_time = time.time() - load_start

            actual_device = str(self.model.device)
            dim = self.model.get_sentence_embedding_dimension()
            print(f"[4/4] 模型加载完成!", flush=True)
            print(f"=" * 60, flush=True)
            print(f"  耗时: {load_time:.2f}秒", flush=True)
            print(f"  设备: {actual_device}", flush=True)
            print(f"  向量维度: {dim}", flush=True)
            print(f"=" * 60, flush=True)

            logger.info(f"模型加载完成，设备: {actual_device}, 维度: {dim}")

        except KeyboardInterrupt:
            print("\n用户中断，程序退出", flush=True)
            raise
        except ImportError:
            print("错误: 未安装sentence-transformers", flush=True)
            print("请运行: pip install sentence-transformers", flush=True)
            raise
        except Exception as e:
            print(f"错误: 模型加载失败 - {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise

    def embed_query(self, text: str) -> List[float]:
        """
        对查询文本进行向量化。

        Args:
            text: 查询文本

        Returns:
            List[float]: 向量表示
        """
        if not text:
            return [0.0] * self._get_embedding_dim()

        try:
            embedding = self.model.encode(
                text,
                **self.encode_kwargs
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"向量化失败: {e}")
            return [0.0] * self._get_embedding_dim()

    def embed_texts(self, texts: List[str], show_progress: bool = False) -> List[List[float]]:
        """
        批量对文本进行向量化。

        Args:
            texts: 文本列表
            show_progress: 是否显示进度

        Returns:
            List[List[float]]: 向量列表
        """
        if not texts:
            return []

        try:
            embeddings = self.model.encode(
                texts,
                show_progress_bar=show_progress,
                **self.encode_kwargs
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"批量向量化失败: {e}")
            return [[0.0] * self._get_embedding_dim()] * len(texts)

    def _get_embedding_dim(self) -> int:
        """获取向量维度。"""
        if self.model is None:
            return 512

        return self.model.get_sentence_embedding_dimension()

    @property
    def embedding_dim(self) -> int:
        """向量维度属性。"""
        return self._get_embedding_dim()

    @property
    def max_seq_length(self) -> int:
        """最大序列长度属性。"""
        if self.model is None:
            return 512

        return self.model.max_seq_length


class ChromaVectorStore:
    """Chroma向量数据库封装类。"""

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "school_documents",
        embeddings: Optional[BGEEmbeddings] = None
    ):
        """
        初始化Chroma向量库。

        Args:
            persist_directory: 持久化存储目录
            collection_name: 集合名称
            embeddings: 嵌入模型
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embeddings = embeddings

        os.makedirs(persist_directory, exist_ok=True)

        self._client = None
        self._collection = None
        self._initialize()

    def _initialize(self) -> None:
        """初始化Chroma客户端和集合。"""
        try:
            import chromadb
            from chromadb.config import Settings

            logger.info(f"初始化Chroma向量库: {self.persist_directory}")

            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )

            try:
                self._collection = self._client.get_collection(name=self.collection_name)
                logger.info(f"已加载现有集合: {self.collection_name}, 文档数: {self._collection.count()}")
            except Exception:
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "School robot knowledge base"}
                )
                logger.info(f"创建新集合: {self.collection_name}")

        except ImportError:
            logger.error("未安装chromadb，请运行: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"Chroma初始化失败: {e}")
            raise

    def add_chunks(
        self,
        chunks: List[Any],
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        添加文本块到向量库（支持大批量自动分批处理，带进度显示）。
        """
        if not chunks:
            logger.warning("没有文本块需要添加")
            return False

        try:
            BATCH_SIZE = 20
            total_chunks = len(chunks)
            total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE

            if ids is None:
                ids = [f"{chunk.file_path}_{chunk.chunk_index}" for chunk in chunks]

            if self.embeddings:
                logger.info(f"=" * 60)
                logger.info(f"开始向量化处理")
                logger.info(f"  总文本块数: {total_chunks}")
                logger.info(f"  批处理大小: {BATCH_SIZE}")
                logger.info(f"  总批次数: {total_batches}")
                logger.info(f"=" * 60)

                all_embeddings = []
                embedding_start = time.time()

                for batch_idx in range(total_batches):
                    start_idx = batch_idx * BATCH_SIZE
                    end_idx = min(start_idx + BATCH_SIZE, total_chunks)
                    batch_texts = [chunk.content for chunk in chunks[start_idx:end_idx]]

                    batch_embeddings = self.embeddings.embed_texts(batch_texts, show_progress=False)
                    all_embeddings.extend(batch_embeddings)

                    # 计算进度
                    processed = end_idx
                    progress = (processed / total_chunks) * 100
                    bar_length = 30
                    filled = int(bar_length * processed / total_chunks)
                    bar = "█" * filled + "?" * (bar_length - filled)

                    elapsed = time.time() - embedding_start
                    eta = (elapsed / processed) * (total_chunks - processed) if processed > 0 else 0

                    logger.info(f"  [{bar}] {progress:5.1f}% | {processed}/{total_chunks} | 批次 {batch_idx + 1}/{total_batches} | 剩余时间: {eta:.1f}s")

                    import gc
                    gc.collect()

                embeddings = all_embeddings
                total_embedding_time = time.time() - embedding_start
                logger.info(f"向量化完成! 耗时: {total_embedding_time:.2f}秒")
            else:
                logger.error("未配置嵌入模型")
                return False

            # 分批添加到Chroma
            logger.info(f"=" * 60)
            logger.info(f"开始添加到Chroma向量库")
            logger.info(f"=" * 60)

            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, total_chunks)

                batch_metadatas = []
                for chunk in chunks[start_idx:end_idx]:
                    metadata = {
                        "file_path": str(chunk.file_path),
                        "file_name": str(chunk.file_name),
                        "chunk_index": int(chunk.chunk_index),
                        "doc_category": str(chunk.doc_category),
                        "title": str(chunk.title),
                        "start_char": int(chunk.start_char),
                        "end_char": int(chunk.end_char),
                        "is_heading": bool(chunk.is_heading),
                        "heading_level": int(chunk.heading_level) if chunk.heading_level else 0
                    }
                    batch_metadatas.append(metadata)

                self._collection.add(
                    embeddings=embeddings[start_idx:end_idx],
                    documents=[chunk.content for chunk in chunks[start_idx:end_idx]],
                    metadatas=batch_metadatas,
                    ids=ids[start_idx:end_idx]
                )

                # 进度显示
                processed = end_idx
                progress = (processed / total_chunks) * 100
                bar_length = 30
                filled = int(bar_length * processed / total_chunks)
                bar = "█" * filled + "?" * (bar_length - filled)
                logger.info(f"  [{bar}] {progress:5.1f}% | {processed}/{total_chunks}")

            if hasattr(self._client, 'persist'):
                self._client.persist()

            final_count = self._collection.count()
            logger.info(f"向量库当前文档数: {final_count}")
            logger.info(f"成功添加 {len(chunks)} 个文本块到向量库")
            return True

        except Exception as e:
            logger.error(f"添加文本块失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文本。

        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_metadata: 元数据过滤条件

        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        try:
            query_embedding = self.embeddings.embed_query(query) if self.embeddings else None

            if query_embedding is None:
                logger.error("嵌入模型不可用")
                return []

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_metadata,
                include=["documents", "metadatas", "distances"]
            )

            formatted_results = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    formatted_results.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                        "id": results["ids"][0][i] if "ids" in results else None
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def get_by_file(self, file_name: str) -> List[Dict[str, Any]]:
        """
        获取指定文件的所有文本块。

        Args:
            file_name: 文件名

        Returns:
            List[Dict[str, Any]]: 文本块列表
        """
        try:
            results = self._collection.get(
                where={"file_name": file_name},
                include=["documents", "metadatas"]
            )

            chunks = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"]):
                    chunks.append({
                        "content": doc,
                        "metadata": results["metadatas"][i],
                        "id": results["ids"][i] if "ids" in results else None
                    })

            return chunks

        except Exception as e:
            logger.error(f"获取文件文本块失败: {e}")
            return []

    def delete_by_file(self, file_name: str) -> bool:
        """
        删除指定文件的所有文本块。

        Args:
            file_name: 文件名

        Returns:
            bool: 是否成功
        """
        try:
            self._collection.delete(where={"file_name": file_name})
            logger.info(f"已删除文件 {file_name} 的所有文本块")
            return True
        except Exception as e:
            logger.error(f"删除文件文本块失败: {e}")
            return False

    def count(self) -> int:
        """
        获取文本块总数。

        Returns:
            int: 文本块数量
        """
        if self._collection:
            return self._collection.count()
        return 0

    def clear(self) -> bool:
        """
        清空向量库。

        Returns:
            bool: 是否成功
        """
        try:
            if self._client and self.collection_name:
                self._client.delete_collection(name=self.collection_name)
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "School robot knowledge base"}
                )
            logger.info("向量库已清空")
            return True
        except Exception as e:
            logger.error(f"清空向量库失败: {e}")
            return False

    def get_stats(self) -> VectorStoreStats:
        """
        获取向量库统计信息。

        Returns:
            VectorStoreStats: 统计信息
        """
        return VectorStoreStats(
            total_chunks=self.count(),
            total_documents=len(self._get_unique_files()) if self._collection else 0,
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
            embedding_model=self.embeddings.model_name if self.embeddings else "unknown",
            build_time=0.0,
            avg_embedding_time=0.0
        )

    def _get_unique_files(self) -> List[str]:
        """获取向量库中所有唯一文件。"""
        if not self._collection:
            return []

        try:
            results = self._collection.get(include=["metadatas"])
            files = set()
            if results and results.get("metadatas"):
                for metadata in results["metadatas"]:
                    if "file_name" in metadata:
                        files.add(metadata["file_name"])
            return list(files)
        except Exception:
            return []

    def exists(self) -> bool:
        """
        检查向量库是否已存在。

        Returns:
            bool: 是否存在
        """
        try:
            if not os.path.exists(self.persist_directory):
                return False

            if self._collection and self._collection.count() > 0:
                return True

            return False
        except Exception:
            return False
