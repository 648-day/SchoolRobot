# -*- coding: utf-8 -*-
"""
双重向量检索模块。

该模块实现：
- 双重向量存储架构（内容向量 + 结构向量）
- 混合检索策略
- 上下文增强检索
- 智能结果融合

作者: AI Assistant
日期: 2026-04-06
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger("VectorDBBuilder.DualVectorStore")


@dataclass
class StructureChunk:
    """结构化文本块类。"""
    content: str
    chunk_index: int
    file_path: str
    file_name: str
    doc_category: str
    title: str
    section_title: str
    section_level: int
    article_numbers: List[str]
    keywords: List[str]


@dataclass
class DualSearchResult:
    """双重检索结果类。"""
    content: str
    metadata: Dict[str, Any]
    content_score: float
    structure_score: float
    combined_score: float
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    section_info: Optional[Dict[str, Any]] = None


class StructureExtractor:
    """结构信息提取器。"""
    
    ARTICLE_PATTERN = re.compile(r'第([一二三四五六七八九十百]+)条')
    SECTION_PATTERN = re.compile(r'^第([一二三四五六七八九十百]+)节\s+(.+)$')
    CHAPTER_PATTERN = re.compile(r'^第([一二三四五六七八九十百]+)章\s+(.+)$')
    
    def extract_section_info(self, text: str, title: str) -> Tuple[str, str, str]:
        """
        提取节级别的结构信息。
        
        Args:
            text: 文本内容
            title: 文档标题
            
        Returns:
            Tuple[str, str, str]: (章节标题, 节标题, 完整路径)
        """
        lines = text.split('\n')
        
        chapter_title = ""
        section_title = ""
        
        for line in lines[:30]:
            chapter_match = self.CHAPTER_PATTERN.match(line.strip())
            if chapter_match:
                chapter_title = f"第{chapter_match.group(1)}章 {chapter_match.group(2)}"
            
            section_match = self.SECTION_PATTERN.match(line.strip())
            if section_match:
                section_title = f"第{section_match.group(1)}节 {section_match.group(2)}"
        
        if section_title and chapter_title:
            full_path = f"{chapter_title} > {section_title}"
        elif section_title:
            full_path = section_title
        elif chapter_title:
            full_path = chapter_title
        else:
            full_path = title or "未知位置"
        
        return chapter_title, section_title, full_path
    
    def extract_structure_info(self, text: str, title: str) -> Tuple[str, List[str], List[str]]:
        """
        提取结构信息。
        
        Args:
            text: 文本内容
            title: 文档标题
            
        Returns:
            Tuple[str, List[str], List[str]]: (摘要, 条目编号列表, 关键词列表)
        """
        lines = text.split('\n')
        
        article_numbers = []
        section_titles = []
        keywords = []
        
        chapter_title, section_title, full_path = self.extract_section_info(text, title)
        
        for line in lines[:20]:
            article_match = self.ARTICLE_PATTERN.search(line)
            if article_match:
                article_numbers.append(article_match.group(0))
            
            section_match = self.SECTION_PATTERN.match(line.strip())
            if section_match:
                section_titles.append(section_match.group(2))
        
        keywords = self._extract_keywords(text)
        
        summary_parts = []
        if full_path:
            summary_parts.append(f"位置: {full_path}")
        if article_numbers:
            summary_parts.append(f"条目: {', '.join(article_numbers[:5])}")
        if keywords:
            summary_parts.append(f"关键词: {', '.join(keywords[:5])}")
        
        summary = " | ".join(summary_parts) if summary_parts else title or "未知文档"
        
        return summary, article_numbers, keywords
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词。"""
        keyword_patterns = [
            r'学生',
            r'管理',
            r'规定',
            r'处分',
            r'奖励',
            r'学籍',
            r'考试',
            r'违纪',
            r'奖学金',
            r'宿舍',
            r'创新创业',
            r'学分',
            r'课程',
            r'毕业',
            r'学位',
            r'入学',
            r'注册',
            r'转专业',
            r'休学',
            r'复学',
            r'退学'
        ]
        
        keywords = []
        for pattern in keyword_patterns:
            if re.search(pattern, text):
                keywords.append(pattern)
        
        return keywords


class DualVectorStore:
    """双重向量存储类。"""
    
    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "school_documents",
        embeddings: Optional[Any] = None
    ):
        """
        初始化双重向量存储。
        
        Args:
            persist_directory: 持久化目录
            collection_name: 集合名称
            embeddings: 嵌入模型
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embeddings = embeddings
        self.structure_extractor = StructureExtractor()
        
        self._client = None
        self._content_collection = None
        self._structure_collection = None
        
        self._initialize()
    
    def _initialize(self) -> None:
        """初始化Chroma客户端和双重集合。"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            logger.info(f"初始化双重向量库: {self.persist_directory}")
            
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            
            content_collection_name = f"{self.collection_name}_content"
            structure_collection_name = f"{self.collection_name}_structure"
            
            try:
                self._content_collection = self._client.get_collection(name=content_collection_name)
                logger.info(f"已加载内容集合: {content_collection_name}, 文档数: {self._content_collection.count()}")
            except Exception:
                self._content_collection = self._client.create_collection(
                    name=content_collection_name,
                    metadata={"description": "Content vectors for school documents"}
                )
                logger.info(f"创建内容集合: {content_collection_name}")
            
            try:
                self._structure_collection = self._client.get_collection(name=structure_collection_name)
                logger.info(f"已加载结构集合: {structure_collection_name}, 文档数: {self._structure_collection.count()}")
            except Exception:
                self._structure_collection = self._client.create_collection(
                    name=structure_collection_name,
                    metadata={"description": "Structure vectors for school documents"}
                )
                logger.info(f"创建结构集合: {structure_collection_name}")
            
        except ImportError:
            logger.error("未安装chromadb，请运行: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"双重向量库初始化失败: {e}")
            raise
    
    def add_chunks_dual(
        self,
        chunks: List[Any],
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        添加文本块到双重向量库（节级别优化）。
        
        Args:
            chunks: 文本块列表
            ids: ID列表
            
        Returns:
            bool: 是否成功
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
            
            logger.info(f"=" * 60)
            logger.info(f"开始双重向量化处理（节级别优化）")
            logger.info(f"  总文本块数: {total_chunks}")
            logger.info(f"  批处理大小: {BATCH_SIZE}")
            logger.info(f"=" * 60)
            
            content_embeddings = []
            structure_embeddings = []
            structure_chunks = []
            
            section_groups = {}
            
            for chunk in chunks:
                chapter_title, section_title, full_path = self.structure_extractor.extract_section_info(
                    chunk.content,
                    chunk.title
                )
                
                section_key = f"{chunk.file_path}|{full_path}"
                
                if section_key not in section_groups:
                    section_groups[section_key] = {
                        'chunks': [],
                        'chapter_title': chapter_title,
                        'section_title': section_title,
                        'full_path': full_path,
                        'file_path': chunk.file_path,
                        'file_name': chunk.file_name,
                        'doc_category': chunk.doc_category,
                        'title': chunk.title
                    }
                
                section_groups[section_key]['chunks'].append(chunk)
            
            logger.info(f"  识别到 {len(section_groups)} 个节级别结构")
            
            embedding_start = time.time()
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, total_chunks)
                batch_chunks = chunks[start_idx:end_idx]
                
                batch_content_texts = [chunk.content for chunk in batch_chunks]
                batch_content_embeddings = self.embeddings.embed_texts(batch_content_texts, show_progress=False)
                content_embeddings.extend(batch_content_embeddings)
                
                for chunk in batch_chunks:
                    chapter_title, section_title, full_path = self.structure_extractor.extract_section_info(
                        chunk.content,
                        chunk.title
                    )
                    
                    section_key = f"{chunk.file_path}|{full_path}"
                    
                    if section_key in section_groups:
                        section_data = section_groups[section_key]
                        
                        all_articles = []
                        all_keywords = set()
                        
                        for c in section_data['chunks']:
                            _, articles, keywords = self.structure_extractor.extract_structure_info(
                                c.content,
                                c.title
                            )
                            all_articles.extend(articles)
                            all_keywords.update(keywords)
                        
                        all_articles = list(dict.fromkeys(all_articles))
                        all_keywords = list(all_keywords)
                        
                        summary_parts = []
                        if section_data['full_path']:
                            summary_parts.append(f"位置: {section_data['full_path']}")
                        if all_articles:
                            summary_parts.append(f"条目: {', '.join(all_articles[:8])}")
                        if all_keywords:
                            summary_parts.append(f"关键词: {', '.join(all_keywords[:8])}")
                        
                        section_summary = " | ".join(summary_parts) if summary_parts else chunk.title or "未知文档"
                        
                        structure_chunk = StructureChunk(
                            content=section_summary,
                            chunk_index=chunk.chunk_index,
                            file_path=chunk.file_path,
                            file_name=chunk.file_name,
                            doc_category=chunk.doc_category,
                            title=chunk.title,
                            section_title=section_data['section_title'],
                            section_level=2 if section_data['section_title'] else 1,
                            article_numbers=all_articles[:8],
                            keywords=all_keywords[:8]
                        )
                        structure_chunks.append(structure_chunk)
                
                batch_structure_texts = [sc.content for sc in structure_chunks[start_idx:end_idx]]
                batch_structure_embeddings = self.embeddings.embed_texts(batch_structure_texts, show_progress=False)
                structure_embeddings.extend(batch_structure_embeddings)
                
                processed = end_idx
                progress = (processed / total_chunks) * 100
                bar_length = 30
                filled = int(bar_length * processed / total_chunks)
                bar = "█" * filled + "?" * (bar_length - filled)
                
                elapsed = time.time() - embedding_start
                eta = (elapsed / processed) * (total_chunks - processed) if processed > 0 else 0
                
                logger.info(f"  [{bar}] {progress:5.1f}% | {processed}/{total_chunks} | 剩余时间: {eta:.1f}s")
                
                import gc
                gc.collect()
            
            total_embedding_time = time.time() - embedding_start
            logger.info(f"双重向量化完成! 耗时: {total_embedding_time:.2f}秒")
            
            logger.info(f"=" * 60)
            logger.info(f"开始添加到内容向量库")
            logger.info(f"=" * 60)
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, total_chunks)
                
                batch_metadatas = []
                for chunk in chunks[start_idx:end_idx]:
                    chapter_title, section_title, full_path = self.structure_extractor.extract_section_info(
                        chunk.content,
                        chunk.title
                    )
                    
                    metadata = {
                        "file_path": str(chunk.file_path),
                        "file_name": str(chunk.file_name),
                        "chunk_index": int(chunk.chunk_index),
                        "doc_category": str(chunk.doc_category),
                        "title": str(chunk.title),
                        "start_char": int(chunk.start_char),
                        "end_char": int(chunk.end_char),
                        "is_heading": bool(chunk.is_heading),
                        "heading_level": int(chunk.heading_level) if hasattr(chunk, 'heading_level') and chunk.heading_level else 0,
                        "chapter_title": chapter_title,
                        "section_title": section_title,
                        "full_path": full_path
                    }
                    batch_metadatas.append(metadata)
                
                self._content_collection.add(
                    embeddings=content_embeddings[start_idx:end_idx],
                    documents=[chunk.content for chunk in chunks[start_idx:end_idx]],
                    metadatas=batch_metadatas,
                    ids=ids[start_idx:end_idx]
                )
                
                processed = end_idx
                progress = (processed / total_chunks) * 100
                bar_length = 30
                filled = int(bar_length * processed / total_chunks)
                bar = "█" * filled + "?" * (bar_length - filled)
                logger.info(f"  [{bar}] {progress:5.1f}% | {processed}/{total_chunks}")
            
            logger.info(f"=" * 60)
            logger.info(f"开始添加到结构向量库（节级别）")
            logger.info(f"=" * 60)
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, total_chunks)
                
                batch_metadatas = []
                for sc in structure_chunks[start_idx:end_idx]:
                    metadata = {
                        "file_path": str(sc.file_path),
                        "file_name": str(sc.file_name),
                        "chunk_index": int(sc.chunk_index),
                        "doc_category": str(sc.doc_category),
                        "title": str(sc.title),
                        "section_title": str(sc.section_title),
                        "section_level": int(sc.section_level),
                        "article_numbers": "|".join(sc.article_numbers),
                        "keywords": "|".join(sc.keywords)
                    }
                    batch_metadatas.append(metadata)
                
                self._structure_collection.add(
                    embeddings=structure_embeddings[start_idx:end_idx],
                    documents=[sc.content for sc in structure_chunks[start_idx:end_idx]],
                    metadatas=batch_metadatas,
                    ids=ids[start_idx:end_idx]
                )
                
                processed = end_idx
                progress = (processed / total_chunks) * 100
                bar_length = 30
                filled = int(bar_length * processed / total_chunks)
                bar = "█" * filled + "?" * (bar_length - filled)
                logger.info(f"  [{bar}] {progress:5.1f}% | {processed}/{total_chunks}")
            
            if hasattr(self._client, 'persist'):
                self._client.persist()
            
            logger.info(f"内容向量库文档数: {self._content_collection.count()}")
            logger.info(f"结构向量库文档数: {self._structure_collection.count()}")
            logger.info(f"成功添加 {len(chunks)} 个文本块到双重向量库")
            logger.info(f"结构向量粒度: 节级别（共 {len(section_groups)} 个节）")
            return True
            
        except Exception as e:
            logger.error(f"添加文本块到双重向量库失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def search_dual(
        self,
        query: str,
        n_results: int = 5,
        content_weight: float = 0.6,
        structure_weight: float = 0.4,
        enable_context: bool = True,
        context_window: int = 1
    ) -> List[DualSearchResult]:
        """
        双重向量检索。
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            content_weight: 内容向量权重
            structure_weight: 结构向量权重
            enable_context: 是否启用上下文增强
            context_window: 上下文窗口大小
            
        Returns:
            List[DualSearchResult]: 检索结果列表
        """
        try:
            logger.info(f"开始双重检索: {query}")
            
            query_embedding = self.embeddings.embed_query(query) if self.embeddings else None
            
            if query_embedding is None:
                logger.error("嵌入模型不可用")
                return []
            
            logger.info("查询向量化完成，开始内容向量检索...")
            
            content_results = self._content_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results * 2,
                include=["documents", "metadatas", "distances"]
            )
            
            logger.info(f"内容向量检索完成，结果数: {len(content_results['documents'][0]) if content_results and content_results.get('documents') else 0}")
            
            logger.info("开始结构向量检索...")
            
            structure_results = self._structure_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results * 2,
                include=["documents", "metadatas", "distances"]
            )
            
            logger.info(f"结构向量检索完成，结果数: {len(structure_results['documents'][0]) if structure_results and structure_results.get('documents') else 0}")
            
            logger.info("开始合并结果...")
            
            merged_results = self._merge_results(
                content_results,
                structure_results,
                content_weight,
                structure_weight,
                n_results
            )
            
            logger.info(f"结果合并完成，数量: {len(merged_results)}")
            
            if enable_context:
                logger.info("添加上下文信息...")
                merged_results = self._add_context(merged_results, context_window)
                logger.info("上下文添加完成")
            
            logger.info(f"双重检索完成，返回 {len(merged_results)} 个结果")
            return merged_results
            
        except Exception as e:
            logger.error(f"双重检索失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return []
    
    def _merge_results(
        self,
        content_results: Dict,
        structure_results: Dict,
        content_weight: float,
        structure_weight: float,
        n_results: int
    ) -> List[DualSearchResult]:
        """合并双重检索结果。"""
        chunk_scores = {}
        
        if content_results and content_results.get("documents"):
            for i, doc in enumerate(content_results["documents"][0]):
                chunk_id = content_results["ids"][0][i]
                distance = content_results["distances"][0][i]
                score = 1.0 / (1.0 + distance)
                
                if chunk_id not in chunk_scores:
                    chunk_scores[chunk_id] = {
                        "content": doc,
                        "metadata": content_results["metadatas"][0][i],
                        "content_score": score,
                        "structure_score": 0.0
                    }
                else:
                    chunk_scores[chunk_id]["content_score"] = score
        
        if structure_results and structure_results.get("documents"):
            for i, doc in enumerate(structure_results["documents"][0]):
                chunk_id = structure_results["ids"][0][i]
                distance = structure_results["distances"][0][i]
                score = 1.0 / (1.0 + distance)
                
                if chunk_id not in chunk_scores:
                    chunk_scores[chunk_id] = {
                        "content": doc,
                        "metadata": structure_results["metadatas"][0][i],
                        "content_score": 0.0,
                        "structure_score": score
                    }
                else:
                    chunk_scores[chunk_id]["structure_score"] = score
        
        results = []
        for chunk_id, data in chunk_scores.items():
            combined_score = (
                content_weight * data["content_score"] +
                structure_weight * data["structure_score"]
            )
            
            results.append(DualSearchResult(
                content=data["content"],
                metadata=data["metadata"],
                content_score=data["content_score"],
                structure_score=data["structure_score"],
                combined_score=combined_score
            ))
        
        results.sort(key=lambda x: x.combined_score, reverse=True)
        
        return results[:n_results]
    
    def _add_context(
        self,
        results: List[DualSearchResult],
        context_window: int
    ) -> List[DualSearchResult]:
        """添加上下文信息。"""
        enhanced_results = []
        
        for result in results:
            file_name = result.metadata.get("file_name")
            chunk_index = result.metadata.get("chunk_index")
            
            if file_name is None or chunk_index is None:
                enhanced_results.append(result)
                continue
            
            context_before = None
            context_after = None
            
            if chunk_index > 0:
                prev_chunks = self._content_collection.get(
                    where={
                        "$and": [
                            {"file_name": file_name},
                            {"chunk_index": chunk_index - 1}
                        ]
                    },
                    include=["documents"]
                )
                if prev_chunks and prev_chunks.get("documents"):
                    context_before = prev_chunks["documents"][0]
            
            next_chunks = self._content_collection.get(
                where={
                    "$and": [
                        {"file_name": file_name},
                        {"chunk_index": chunk_index + 1}
                    ]
                },
                include=["documents"]
            )
            if next_chunks and next_chunks.get("documents"):
                context_after = next_chunks["documents"][0]
            
            result.context_before = context_before
            result.context_after = context_after
            
            enhanced_results.append(result)
        
        return enhanced_results
    
    def search_content_only(
        self,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """仅使用内容向量检索。"""
        try:
            query_embedding = self.embeddings.embed_query(query) if self.embeddings else None
            
            if query_embedding is None:
                logger.error("嵌入模型不可用")
                return []
            
            results = self._content_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
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
            logger.error(f"内容检索失败: {e}")
            return []
    
    def count(self) -> Tuple[int, int]:
        """
        获取向量库文档数。
        
        Returns:
            Tuple[int, int]: (内容向量数, 结构向量数)
        """
        content_count = self._content_collection.count() if self._content_collection else 0
        structure_count = self._structure_collection.count() if self._structure_collection else 0
        return content_count, structure_count
    
    def clear(self) -> bool:
        """清空双重向量库。"""
        try:
            if self._client:
                content_collection_name = f"{self.collection_name}_content"
                structure_collection_name = f"{self.collection_name}_structure"
                
                try:
                    self._client.delete_collection(name=content_collection_name)
                except Exception:
                    pass
                
                try:
                    self._client.delete_collection(name=structure_collection_name)
                except Exception:
                    pass
                
                self._content_collection = self._client.create_collection(
                    name=content_collection_name,
                    metadata={"description": "Content vectors for school documents"}
                )
                
                self._structure_collection = self._client.create_collection(
                    name=structure_collection_name,
                    metadata={"description": "Structure vectors for school documents"}
                )
            
            logger.info("双重向量库已清空")
            return True
            
        except Exception as e:
            logger.error(f"清空双重向量库失败: {e}")
            return False
    
    def exists(self) -> bool:
        """检查向量库是否已存在。"""
        try:
            if not os.path.exists(self.persist_directory):
                return False
            
            content_count = self._content_collection.count() if self._content_collection else 0
            structure_count = self._structure_collection.count() if self._structure_collection else 0
            
            return content_count > 0 and structure_count > 0
            
        except Exception:
            return False
