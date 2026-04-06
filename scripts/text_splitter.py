"""
文本分块模块。

该模块负责：
- 基于中文语法特点的智能文本分块
- 支持自定义分块大小和重叠长度
- 智能断句，避免语义断裂
- 保留段落和章节结构信息

作者: AI Assistant
日期: 2026-04-02
"""

import re
import time
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("VectorDBBuilder.TextSplitter")


@dataclass
class TextChunk:
    """文本块类。"""
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    file_path: str
    file_name: str
    doc_category: str
    title: str
    is_heading: bool = False
    heading_level: int = 0


class ChineseTextSplitter:
    """中文文本分块器。"""

    # 中文句子结束标点
    SENTENCE_END_PUNCTUATIONS = "。！？；"

    # 段落分隔符
    PARAGRAPH_SEPARATOR = "\n\n"

    # 标题正则
    HEADING_PATTERNS = [
        (r"^#\s+(.+)$", 1),   # 一级标题
        (r"^##\s+(.+)$", 2),  # 二级标题
        (r"^###\s+(.+)$", 3), # 三级标题
        (r"^####\s+(.+)$", 4), # 四级标题
    ]

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 50,
        split_by_word: bool = True,
        split_by_sentence: bool = True
    ):
        """
        初始化文本分块器。

        Args:
            chunk_size: 分块大小（字符数）
            chunk_overlap: 分块重叠大小（字符数）
            min_chunk_size: 最小分块大小
            split_by_word: 是否按单词分割（中文按字符）
            split_by_sentence: 是否按句子分割
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.split_by_word = split_by_word
        self.split_by_sentence = split_by_sentence

        if self.chunk_overlap >= self.chunk_size:
            logger.warning(f"重叠长度({chunk_overlap})应小于分块大小({chunk_size})，已自动调整")
            self.chunk_overlap = chunk_size // 4

        logger.info(f"文本分块器初始化: chunk_size={chunk_size}, overlap={chunk_overlap}")

    def split_sentences(self, text: str) -> List[str]:
        """
        将文本分割为句子。

        Args:
            text: 文本内容

        Returns:
            List[str]: 句子列表
        """
        if not text:
            return []

        sentences = []
        current_sentence = []

        for char in text:
            current_sentence.append(char)

            if char in self.SENTENCE_END_PUNCTUATIONS:
                sentence = "".join(current_sentence).strip()
                if sentence:
                    sentences.append(sentence)
                current_sentence = []

        # 处理最后一个句子
        if current_sentence:
            remaining = "".join(current_sentence).strip()
            if remaining:
                sentences.append(remaining)

        return sentences

    def split_paragraphs(self, text: str) -> List[str]:
        """
        将文本分割为段落。

        Args:
            text: 文本内容

        Returns:
            List[str]: 段落列表
        """
        if not text:
            return []

        paragraphs = text.split(self.PARAGRAPH_SEPARATOR)
        result = []

        for para in paragraphs:
            para = para.strip()
            if para:
                result.append(para)

        return result

    def is_heading(self, line: str) -> Tuple[bool, int, str]:
        """
        检查行是否为标题。

        Args:
            line: 文本行

        Returns:
            Tuple[bool, int, str]: (是否为标题, 标题级别, 标题内容)
        """
        for pattern, level in self.HEADING_PATTERNS:
            match = re.match(pattern, line.strip())
            if match:
                return True, level, match.group(1)

        return False, 0, ""

    def split_by_headings(self, text: str) -> List[Tuple[str, int, str]]:
        """
        按标题分割文本。

        Args:
            text: 文本内容

        Returns:
            List[Tuple[str, int, str]]: [(段落内容, 标题级别, 标题文本)]
        """
        lines = text.split("\n")
        sections = []
        current_section_content = []
        current_heading = ""
        current_level = 0

        for line in lines:
            is_heading, level, heading_text = self.is_heading(line)

            if is_heading:
                # 保存之前的section
                if current_section_content:
                    sections.append((
                        "\n".join(current_section_content).strip(),
                        current_level,
                        current_heading
                    ))
                    current_section_content = []

                current_heading = heading_text
                current_level = level
                current_section_content.append(line)
            else:
                current_section_content.append(line)

        # 保存最后一个section
        if current_section_content:
            sections.append((
                "\n".join(current_section_content).strip(),
                current_level,
                current_heading
            ))

        return sections

    def create_chunks(
        self,
        text: str,
        file_path: str,
        file_name: str,
        doc_category: str = "",
        title: str = ""
    ) -> List[TextChunk]:
        """
        创建文本块（带进度显示）。
        """
        if not text or not text.strip():
            logger.warning(f"文档 {file_name} 内容为空，无法分块")
            return []

        logger.info(f"[{file_name}] 开始分块，文本长度: {len(text)}")

        chunks = []
        chunk_index = 0
        start_pos = 0

        sections = self.split_by_headings(text)
        total_sections = len(sections)
        logger.info(f"[{file_name}] 按标题分割得到 {total_sections} 个段落")

        for idx, (section_content, section_level, section_heading) in enumerate(sections):
            if not section_content.strip():
                continue

            section_len = len(section_content)
            heading_info = f"[级别{section_level}] {section_heading[:30]}..." if section_heading else "[无标题]"

            if section_len <= self.chunk_size:
                chunk = TextChunk(
                    content=section_content,
                    chunk_index=chunk_index,
                    start_char=start_pos,
                    end_char=start_pos + section_len,
                    file_path=file_path,
                    file_name=file_name,
                    doc_category=doc_category,
                    title=title or section_heading,
                    is_heading=(section_level > 0),
                    heading_level=section_level
                )
                chunks.append(chunk)
                chunk_index += 1
                start_pos += section_len + 2
                logger.info(f"[{file_name}] 段落 {idx+1}/{total_sections} {heading_info} -> 直接创建chunk (长度{section_len})")
            else:
                logger.info(f"[{file_name}] 段落 {idx+1}/{total_sections} {heading_info} -> 大段落需分割 (长度{section_len})")
                section_chunks = self._split_large_section(
                    section_content,
                    chunk_index,
                    start_pos,
                    file_path,
                    file_name,
                    doc_category,
                    title or section_heading,
                    section_level > 0
                )
                chunks.extend(section_chunks)
                chunk_index = chunks[-1].chunk_index + 1 if chunks else chunk_index + 1
                start_pos += section_len + 2
                logger.info(f"[{file_name}] 段落 {idx+1}/{total_sections} -> 分割生成 {len(section_chunks)} 个chunks")

        chunks = self._merge_small_chunks(chunks)

        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        logger.info(f"[{file_name}] 分块完成: 共 {len(chunks)} 个chunks")
        return chunks

    def _split_large_section(
        self,
        text: str,
        start_chunk_index: int,
        start_char_pos: int,
        file_path: str,
        file_name: str,
        doc_category: str,
        title: str,
        is_heading: bool
    ) -> List[TextChunk]:
        """
        分割大段落（带进度显示和异常保护）。
        """
        chunks = []
        current_pos = 0
        chunk_index = start_chunk_index
        text_len = len(text)
        max_iterations = text_len // self.min_chunk_size + 100  # 防止无限循环
        iteration_count = 0

        logger.debug(f"    开始分割大段落，长度: {text_len}")

        while current_pos < text_len:
            iteration_count += 1
            if iteration_count > max_iterations:
                logger.error(f"    分割段落超时，可能存在无限循环！position={current_pos}/{text_len}")
                break

            end_pos = min(current_pos + self.chunk_size, text_len)

            if end_pos < text_len:
                break_pos = self._find_best_break_point(text, current_pos, end_pos)

                if break_pos == current_pos:
                    overlap_start = max(current_pos - self.chunk_overlap, 0)
                    break_pos = self._find_best_break_point(text, overlap_start, end_pos)
                    if break_pos == overlap_start:
                        break_pos = end_pos
            else:
                break_pos = end_pos

            chunk_content = text[current_pos:break_pos].strip()

            if chunk_content and len(chunk_content) >= self.min_chunk_size:
                chunk = TextChunk(
                    content=chunk_content,
                    chunk_index=chunk_index,
                    start_char=start_char_pos + current_pos,
                    end_char=start_char_pos + break_pos,
                    file_path=file_path,
                    file_name=file_name,
                    doc_category=doc_category,
                    title=title,
                    is_heading=is_heading
                )
                chunks.append(chunk)
                chunk_index += 1

            if break_pos <= current_pos:
                current_pos += self.min_chunk_size
            else:
                current_pos = break_pos - self.chunk_overlap

            if current_pos < 0 or current_pos >= text_len:
                break

        logger.debug(f"    段落分割完成: 生成 {len(chunks)} 个chunks")
        return chunks

    def _find_best_break_point(self, text: str, start: int, end: int) -> int:
        """
        找到最佳的断点位置。

        Args:
            text: 文本内容
            start: 起始位置
            end: 结束位置

        Returns:
            int: 断点位置
        """
        # 优先在句子结束标点处断开
        for i in range(end - 1, start, -1):
            if text[i] in self.SENTENCE_END_PUNCTUATIONS:
                return i + 1

        # 其次在换行符处断开
        for i in range(end - 1, start, -1):
            if text[i] == "\n":
                return i + 1

        # 在空格处断开（适用于英文混合文本）
        for i in range(end - 1, start, -1):
            if text[i] == " ":
                return i + 1

        return start

    def _merge_small_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """
        合并太小的文本块。

        Args:
            chunks: 文本块列表

        Returns:
            List[TextChunk]: 合并后的文本块列表
        """
        if not chunks:
            return []

        merged = []
        current = chunks[0]

        for next_chunk in chunks[1:]:
            # 如果当前chunk太小，尝试与下一个合并
            if len(current.content) < self.min_chunk_size:
                current.content += "\n\n" + next_chunk.content
                current.end_char = next_chunk.end_char
            else:
                merged.append(current)
                current = next_chunk

        # 处理最后一个
        if current not in merged:
            merged.append(current)

        return merged


class ChunkProcessor:
    """文本块处理器，负责批量处理文本分块。"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 50
    ):
        """
        初始化文本块处理器。

        Args:
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
            min_chunk_size: 最小分块大小
        """
        self.splitter = ChineseTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size
        )
        logger.info(f"ChunkProcessor初始化: chunk_size={chunk_size}, overlap={chunk_overlap}")

    def process_document(
        self,
        content: str,
        file_path: str,
        file_name: str,
        doc_category: str = "",
        title: str = ""
    ) -> List[TextChunk]:
        """
        处理单个文档。

        Args:
            content: 文档内容
            file_path: 文件路径
            file_name: 文件名
            doc_category: 文档分类
            title: 文档标题

        Returns:
            List[TextChunk]: 文本块列表
        """
        chunks = self.splitter.create_chunks(
            text=content,
            file_path=file_path,
            file_name=file_name,
            doc_category=doc_category,
            title=title
        )

        logger.debug(f"文档 {file_name} 生成了 {len(chunks)} 个chunks")
        return chunks

    def process_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> Tuple[List[TextChunk], Dict[str, Any]]:
        """
        批量处理文档（带进度显示和异常保护）。
        """
        all_chunks = []
        doc_chunks_count = {}
        failed_docs = []

        total_docs = len(documents)
        logger.info("=" * 60)
        logger.info(f"开始批量处理 {total_docs} 个文档...")
        logger.info("=" * 60)

        start_time = time.time()

        for idx, doc in enumerate(documents, 1):
            file_name = doc.get("file_name", "unknown")
            content = doc.get("content", "")

            try:
                logger.info(f"[{idx}/{total_docs}] 处理文档: {file_name}")

                if not content or not content.strip():
                    logger.warning(f"[{file_name}] 内容为空，跳过")
                    doc_chunks_count[file_name] = 0
                    failed_docs.append((file_name, "内容为空"))
                    continue

                chunks = self.process_document(
                    content=content,
                    file_path=doc.get("file_path", ""),
                    file_name=file_name,
                    doc_category=doc.get("doc_category", ""),
                    title=doc.get("title", "")
                )

                all_chunks.extend(chunks)
                doc_chunks_count[file_name] = len(chunks)

                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                eta = avg_time * (total_docs - idx)
                logger.info(f"[{idx}/{total_docs}] {file_name} -> {len(chunks)} chunks | 进度: {idx}/{total_docs} | 剩余时间: {eta:.1f}s")

            except Exception as e:
                import traceback
                logger.error(f"[{file_name}] 处理失败: {e}")
                logger.debug(f"详细错误: {traceback.format_exc()}")
                doc_chunks_count[file_name] = 0
                failed_docs.append((file_name, str(e)))

        total_time = time.time() - start_time
        stats = {
            "total_chunks": len(all_chunks),
            "total_documents": total_docs,
            "chunks_per_document": doc_chunks_count,
            "avg_chunks_per_doc": len(all_chunks) / total_docs if total_docs > 0 else 0,
            "failed_docs": failed_docs,
            "processing_time": total_time
        }

        logger.info("=" * 60)
        logger.info(f"批量处理完成!")
        logger.info(f"  处理文档: {total_docs} 个")
        logger.info(f"  生成chunks: {len(all_chunks)} 个")
        logger.info(f"  处理失败: {len(failed_docs)} 个")
        logger.info(f"  总耗时: {total_time:.2f}秒")
        logger.info("=" * 60)

        if failed_docs:
            logger.warning(f"处理失败的文档:")
            for fn, reason in failed_docs:
                logger.warning(f"  - {fn}: {reason}")

        return all_chunks, stats
