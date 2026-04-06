"""
向量数据库构建主脚本。

该脚本实现以下功能：
1. 批量读取指定目录下的Markdown文档
2. 文本清洗和预处理
3. 智能文本分块
4. BGE中文向量模型向量化
5. Chroma向量数据库构建和持久化
6. 完整的日志和统计信息输出

配置文件: config.yaml
运行方式: python build_vectordb.py [--rebuild]

作者: AI Assistant
日期: 2026-04-02
"""

import os
import sys      
import time
import logging
import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent))

from document_loader import DocumentLoader, LoadResult
from text_splitter import ChunkProcessor, TextChunk
from vectorstore import ChromaVectorStore, BGEEmbeddings
from dual_vectorstore import DualVectorStore


@dataclass
class VectorDBConfig:
    """向量数据库配置类。"""
    
    docs_directory: str = "d:/SchoolRobot-main/knowledge_base/cleaned"
    vectorstore_directory: str = "d:/SchoolRobot-main/vectorstore/chroma"
    persist_directory: str = "d:/SchoolRobot-main/vectorstore/chroma"
    embedding_model_name: str = "BAAI/bge-large-zh-v1.5"
    model_kwargs: Dict[str, Any] = field(default_factory=lambda: {"device": "cuda"})
    encode_kwargs: Dict[str, Any] = field(default_factory=lambda: {"normalize_embeddings": True})
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 150
    supported_extensions: List[str] = field(default_factory=lambda: [".md"])
    recursive_scan: bool = True
    encoding: str = "utf-8"
    collection_name: str = "school_documents"
    log_level: str = "INFO"
    use_dual_vector: bool = True
    content_weight: float = 0.6
    structure_weight: float = 0.4
    enable_context: bool = True
    context_window: int = 1
    
    @property
    def embedding_model_kwargs(self) -> Dict[str, Any]:
        return self.model_kwargs
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "VectorDBConfig":
        """从YAML文件加载配置。"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        default = cls()
        
        return cls(
            docs_directory=data.get("docs_directory", default.docs_directory),
            vectorstore_directory=data.get("vectorstore_directory", default.vectorstore_directory),
            persist_directory=data.get("vectorstore_directory", default.persist_directory),
            embedding_model_name=data.get("embedding_model_name", default.embedding_model_name),
            model_kwargs=data.get("model_kwargs", default.model_kwargs),
            encode_kwargs=data.get("encode_kwargs", default.encode_kwargs),
            chunk_size=data.get("chunk_size", default.chunk_size),
            chunk_overlap=data.get("chunk_overlap", default.chunk_overlap),
            min_chunk_size=data.get("min_chunk_size", default.min_chunk_size),
            supported_extensions=data.get("supported_extensions", default.supported_extensions),
            recursive_scan=data.get("recursive_scan", default.recursive_scan),
            encoding=data.get("encoding", default.encoding),
            collection_name=data.get("collection_name", default.collection_name),
            log_level=data.get("log_level", default.log_level),
            use_dual_vector=data.get("use_dual_vector", default.use_dual_vector),
            content_weight=data.get("content_weight", default.content_weight),
            structure_weight=data.get("structure_weight", default.structure_weight),
            enable_context=data.get("enable_context", default.enable_context),
            context_window=data.get("context_window", default.context_window)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "docs_directory": self.docs_directory,
            "vectorstore_directory": self.vectorstore_directory,
            "persist_directory": self.persist_directory,
            "embedding_model_name": self.embedding_model_name,
            "model_kwargs": self.model_kwargs,
            "encode_kwargs": self.encode_kwargs,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "min_chunk_size": self.min_chunk_size,
            "supported_extensions": self.supported_extensions,
            "recursive_scan": self.recursive_scan,
            "encoding": self.encoding,
            "collection_name": self.collection_name,
            "log_level": self.log_level,
            "use_dual_vector": self.use_dual_vector,
            "content_weight": self.content_weight,
            "structure_weight": self.structure_weight,
            "enable_context": self.enable_context,
            "context_window": self.context_window
        }
    
    def ensure_directories(self):
        """确保目录存在。"""
        Path(self.docs_directory).mkdir(parents=True, exist_ok=True)
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)


def setup_logging(log_level: int = logging.INFO, name: str = "VectorDBBuilder") -> logging.Logger:
    """设置日志。"""
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def get_config() -> VectorDBConfig:
    """从config.yaml获取配置。"""
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        return VectorDBConfig.from_yaml(str(config_path))
    return VectorDBConfig()


class VectorDBBuilder:
    """向量数据库构建器主类。"""

    def __init__(self, config: Optional[VectorDBConfig] = None):
        """
        初始化向量数据库构建器。

        Args:
            config: 配置对象（可选，默认从config.yaml加载）
        """
        self.config = config or get_config()
        self.logger = logging.getLogger("VectorDBBuilder")
        self.loader: Optional[DocumentLoader] = None
        self.processor: Optional[ChunkProcessor] = None
        self.embeddings: Optional[BGEEmbeddings] = None
        self.vectorstore: Optional[ChromaVectorStore] = None
        self.dual_vectorstore: Optional[DualVectorStore] = None
        self._build_stats: Dict[str, Any] = {}

    def _initialize_components(self) -> bool:
        """初始化各个组件。"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("开始初始化组件...")
            self.logger.info("=" * 60)

            self.loader = DocumentLoader(
                directory=self.config.docs_directory,
                encoding=self.config.encoding,
                recursive=self.config.recursive_scan
            )
            self.logger.info("✓ 文档加载器初始化成功")

            self.processor = ChunkProcessor(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                min_chunk_size=self.config.min_chunk_size
            )
            self.logger.info("✓ 文本分块处理器初始化成功")

            self.logger.info("正在加载BGE向量模型...")
            self.embeddings = BGEEmbeddings(
                model_name=self.config.embedding_model_name,
                model_kwargs=self.config.embedding_model_kwargs,
                encode_kwargs=self.config.encode_kwargs
            )
            self.logger.info(f"✓ BGE向量模型加载成功，向量维度: {self.embeddings.embedding_dim}")

            if self.config.use_dual_vector:
                self.dual_vectorstore = DualVectorStore(
                    persist_directory=self.config.persist_directory,
                    collection_name=self.config.collection_name,
                    embeddings=self.embeddings
                )
                self.logger.info("✓ 双重向量库初始化成功（内容向量 + 结构向量）")
            else:
                self.vectorstore = ChromaVectorStore(
                    persist_directory=self.config.persist_directory,
                    collection_name=self.config.collection_name,
                    embeddings=self.embeddings
                )
                self.logger.info("✓ Chroma向量库初始化成功")

            self.logger.info("所有组件初始化完成！")
            return True

        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            return False

    def _load_documents(self) -> tuple:
        """
        加载文档。
        
        Returns:
            tuple: (load_results, stats)
        """
        try:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("开始加载文档...")
            self.logger.info("=" * 60)

            start_time = time.time()
            load_results, stats = self.loader.load_all(self.config.supported_extensions)
            load_time = time.time() - start_time

            self._build_stats["load"] = {
                "total_files": stats["total_files"],
                "success_count": stats["success_count"],
                "failed_count": stats["failed_count"],
                "total_chars": stats["total_chars"],
                "load_time": load_time,
                "failed_files": stats.get("failed_files", []),
                "failed_reasons": stats.get("failed_reasons", [])
            }

            self.logger.info(f"\n文档加载统计:")
            self.logger.info(f"  - 总文件数: {stats['total_files']}")
            self.logger.info(f"  - 成功加载: {stats['success_count']}")
            self.logger.info(f"  - 加载失败: {stats['failed_count']}")
            self.logger.info(f"  - 总字符数: {stats['total_chars']:,}")
            self.logger.info(f"  - 加载耗时: {load_time:.2f}秒")

            if stats["failed_count"] > 0:
                self.logger.warning("\n加载失败的文件:")
                for i, (file_path, reason) in enumerate(zip(
                    stats.get("failed_files", []),
                    stats.get("failed_reasons", [])
                ), 1):
                    self.logger.warning(f"  {i}. {Path(file_path).name}: {reason}")

            return load_results, stats

        except Exception as e:
            self.logger.error(f"文档加载失败: {e}")
            return [], {}

    def _build_vectorstore(self, load_results: List[LoadResult]) -> bool:
        """构建向量库。"""
        try:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("开始构建向量库...")
            self.logger.info("=" * 60)

            start_time = time.time()

            self.logger.info("步骤1: 准备文档数据...")
            documents = []
            for result in load_results:
                if result.success:
                    documents.append({
                        "content": result.content,
                        "file_path": result.metadata.file_path,
                        "file_name": result.metadata.file_name,
                        "doc_category": result.metadata.doc_category,
                        "title": result.metadata.title
                    })
            self.logger.info(f"  准备完成: {len(documents)} 个文档")

            self.logger.info("步骤2: 执行文本分块...")
            chunks, split_stats = self.processor.process_batch(documents)
            self.logger.info(f"  分块完成: 生成 {len(chunks)} 个文本块")
            self.logger.info(f"  平均每文档: {split_stats.get('avg_chunks_per_doc', 0):.1f} 块")

            if not chunks:
                self.logger.error("  错误: 没有生成任何文本块!")
                return False

            self._build_stats["split"] = {
                "total_chunks": len(chunks),
                "total_documents": len(documents),
                "avg_chunks_per_doc": split_stats.get('avg_chunks_per_doc', 0),
                "split_time": time.time() - start_time
            }

            self.logger.info("步骤3: 向量化并添加到向量库...")
            self.logger.info(f"  向量模型: {self.config.embedding_model_name}")
            self.logger.info(f"  目标集合: {self.config.collection_name}")
            
            if self.config.use_dual_vector:
                self.logger.info(f"  检索模式: 双重向量检索（内容向量 + 结构向量）")
                success = self.dual_vectorstore.add_chunks_dual(chunks)
            else:
                self.logger.info(f"  检索模式: 单一向量检索")
                success = self.vectorstore.add_chunks(chunks)

            build_time = time.time() - start_time

            if self.config.use_dual_vector:
                content_count, structure_count = self.dual_vectorstore.count()
                self._build_stats["vectorstore"] = {
                    "total_chunks": len(chunks),
                    "build_time": build_time,
                    "persist_directory": self.config.persist_directory,
                    "collection_name": self.config.collection_name,
                    "content_vectors": content_count,
                    "structure_vectors": structure_count,
                    "use_dual_vector": True
                }
            else:
                self._build_stats["vectorstore"] = {
                    "total_chunks": len(chunks),
                    "build_time": build_time,
                    "persist_directory": self.config.persist_directory,
                    "collection_name": self.config.collection_name,
                    "use_dual_vector": False
                }

            self.logger.info(f"\n向量库构建统计:")
            self.logger.info(f"  - 添加文本块: {len(chunks)}")
            self.logger.info(f"  - 构建耗时: {build_time:.2f}秒")
            self.logger.info(f"  - 存储路径: {self.config.persist_directory}")
            self.logger.info(f"  - 集合名称: {self.config.collection_name}")
            if self.config.use_dual_vector:
                self.logger.info(f"  - 内容向量数: {content_count}")
                self.logger.info(f"  - 结构向量数: {structure_count}")

            return success

        except Exception as e:
            import traceback
            self.logger.error(f"向量库构建失败: {e}")
            self.logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            return False

    def build(self, rebuild: bool = False) -> bool:
        """
        执行完整的向量库构建流程。

        Args:
            rebuild: 是否重建（清空现有向量库）

        Returns:
            bool: 是否成功
        """
        total_start_time = time.time()

        self.logger.info("\n" + "#" * 60)
        self.logger.info("# 向量数据库构建程序")
        self.logger.info(f"# 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("#" * 60)

        if not self._initialize_components():
            self.logger.error("组件初始化失败，程序退出")
            return False

        if self.config.use_dual_vector:
            if self.dual_vectorstore.exists():
                if rebuild:
                    self.logger.warning("双重向量库已存在，将执行重建操作...")
                    self.dual_vectorstore.clear()
                else:
                    self.logger.warning("双重向量库已存在，如需重建请使用 rebuild=True 参数")
                    return False
        else:
            if self.vectorstore.exists():
                if rebuild:
                    self.logger.warning("向量库已存在，将执行重建操作...")
                    self.vectorstore.clear()
                else:
                    self.logger.warning("向量库已存在，如需重建请使用 rebuild=True 参数")
                    return False

        load_results, _ = self._load_documents()
        
        if not load_results:
            self.logger.error("文档加载失败，程序退出")
            return False

        if not self._build_vectorstore(load_results):
            self.logger.error("向量库构建失败，程序退出")
            return False

        total_time = time.time() - total_start_time
        self._output_final_stats(total_time)

        self.logger.info("\n" + "#" * 60)
        self.logger.info("# 向量数据库构建完成！")
        self.logger.info("#" * 60)

        return True

    def _output_final_stats(self, total_time: float) -> None:
        """输出最终统计信息。"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("构建完成 - 最终统计")
        self.logger.info("=" * 60)

        load_stats = self._build_stats.get("load", {})
        split_stats = self._build_stats.get("split", {})
        vs_stats = self._build_stats.get("vectorstore", {})

        self.logger.info(f"\n【文档加载】")
        self.logger.info(f"  总文件数: {load_stats.get('total_files', 0)}")
        self.logger.info(f"  成功处理: {load_stats.get('success_count', 0)}")
        self.logger.info(f"  处理失败: {load_stats.get('failed_count', 0)}")
        self.logger.info(f"  总字符数: {load_stats.get('total_chars', 0):,}")

        self.logger.info(f"\n【文本分块】")
        self.logger.info(f"  生成块数: {split_stats.get('total_chunks', 0)}")
        self.logger.info(f"  平均每文档: {split_stats.get('avg_chunks_per_doc', 0):.1f}块")

        self.logger.info(f"\n【向量库】")
        self.logger.info(f"  集合名称: {vs_stats.get('collection_name', 'N/A')}")
        self.logger.info(f"  存储路径: {vs_stats.get('persist_directory', 'N/A')}")
        self.logger.info(f"  总文本块: {vs_stats.get('total_chunks', 0)}")
        if vs_stats.get('use_dual_vector', False):
            self.logger.info(f"  检索模式: 双重向量检索")
            self.logger.info(f"  内容向量数: {vs_stats.get('content_vectors', 0)}")
            self.logger.info(f"  结构向量数: {vs_stats.get('structure_vectors', 0)}")
        else:
            self.logger.info(f"  检索模式: 单一向量检索")

        self.logger.info(f"\n【性能】")
        self.logger.info(f"  总耗时: {total_time:.2f}秒 ({total_time/60:.1f}分钟)")
        self.logger.info(f"  文档加载: {load_stats.get('load_time', 0):.2f}秒")
        self.logger.info(f"  文本分块: {split_stats.get('split_time', 0):.2f}秒")
        self.logger.info(f"  向量构建: {vs_stats.get('build_time', 0):.2f}秒")

        self.logger.info(f"\n向量库配置信息:")
        self.logger.info(f"  向量模型: {self.config.embedding_model_name}")
        self.logger.info(f"  向量维度: {self.embeddings.embedding_dim if self.embeddings else 'N/A'}")
        self.logger.info(f"  分块大小: {self.config.chunk_size}")
        self.logger.info(f"  分块重叠: {self.config.chunk_overlap}")

        self._save_build_stats()

    def _save_build_stats(self) -> None:
        """保存构建统计信息。"""
        try:
            stats_file = Path(self.config.persist_directory) / "build_stats.json"
            stats_file.parent.mkdir(parents=True, exist_ok=True)

            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump({
                    "build_time": datetime.now().isoformat(),
                    "config": self.config.to_dict(),
                    "stats": {
                        "load": self._build_stats.get("load", {}),
                        "split": self._build_stats.get("split", {}),
                        "vectorstore": self._build_stats.get("vectorstore", {})
                    }
                }, f, ensure_ascii=False, indent=2)

            self.logger.info(f"\n构建统计已保存至: {stats_file}")

        except Exception as e:
            self.logger.warning(f"保存统计失败: {e}")


def main(rebuild: bool = False):
    """
    主函数入口。
    
    Args:
        rebuild: 是否重建向量库（清空现有数据）
    
    Returns:
        bool: 构建是否成功
    """
    config = get_config()
    
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    setup_logging(log_level=log_level)
    
    config.ensure_directories()
    
    builder = VectorDBBuilder(config)
    return builder.build(rebuild=rebuild)


if __name__ == "__main__":
    import sys
    rebuild = "--rebuild" in sys.argv or "-r" in sys.argv
    success = main(rebuild=rebuild)
    sys.exit(0 if success else 1)
