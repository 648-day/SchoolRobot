# -*- coding: utf-8 -*-
"""
文档加载与预处理模块。

该模块负责：
- 批量扫描和读取指定目录下的.md文档
- 自动处理文件编码问题
- 文本清洗和预处理
- Markdown格式解析和结构提取

作者: AI Assistant
日期: 2026-04-02
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("VectorDBBuilder.DocumentLoader")


@dataclass
class DocumentMetadata:
    """文档元数据类。"""
    file_path: str
    file_name: str
    file_size: int
    encoding: str
    load_time: str
    doc_category: str = ""
    title: str = ""
    total_chars: int = 0


@dataclass
class LoadResult:
    """文档加载结果类。"""
    success: bool
    content: str
    metadata: DocumentMetadata
    error_message: Optional[str] = None


class TextPreprocessor:
    """文本预处理器，负责清洗和规范化文本。"""

    def __init__(self):
        self.special_chars_pattern = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]")
        self.multiple_spaces_pattern = re.compile(r"[ \t]+")
        self.multiple_newlines_pattern = re.compile(r"\n{3,}")
        self.trailing_whitespace_pattern = re.compile(r"[ \t]+$", re.MULTILINE)

    def clean(self, text: str) -> str:
        """清洗文本内容。"""
        if not text:
            return ""

        text = self.special_chars_pattern.sub("", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = self.multiple_spaces_pattern.sub(" ", text)
        text = self.multiple_newlines_pattern.sub("\n\n", text)
        text = self.trailing_whitespace_pattern.sub("", text)
        text = text.strip()

        return text

    def process_markdown(self, text: str) -> str:
        """处理Markdown格式文本。"""
        if not text:
            return ""

        lines = text.split("\n")
        processed_lines = []
        in_code_block = False
        code_block_content = []

        for line in lines:
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_block_content = [line]
                else:
                    code_block_content.append(line)
                    processed_lines.append("\n".join(code_block_content))
                    processed_lines.append("")
                    in_code_block = False
                    code_block_content = []
                continue

            if in_code_block:
                code_block_content.append(line)
                continue

            if line.startswith("#"):
                processed_lines.append(line)
                processed_lines.append("")
            elif line.strip().startswith(("-", "*", "·")):
                processed_lines.append(line)
            elif re.match(r"^\d+\.", line.strip()):
                processed_lines.append(line)
            elif line.strip().startswith("|") or re.match(r"^\|?[\s\-:]+\|", line.strip()):
                processed_lines.append(line)
            else:
                processed_lines.append(line)

        result = "\n".join(processed_lines)
        result = self.clean(result)

        return result

    def extract_title(self, text: str) -> Tuple[str, str]:
        """从Markdown文本中提取标题。"""
        lines = text.split("\n")
        title = ""
        content_lines = []
        title_found = False

        for line in lines:
            if not title_found and line.strip().startswith("# ") and not line.strip().startswith("##"):
                title = line.strip().lstrip("#").strip()
                title_found = True
            else:
                content_lines.append(line)

        return title, "\n".join(content_lines)

    def extract_category(self, file_path: str) -> str:
        """从文件路径提取文档分类。"""
        path = Path(file_path)
        parent_name = path.parent.name
        file_name = path.stem
        category = parent_name if parent_name not in ["cleaned", "raw", "knowledge_base"] else "general"

        if "学生" in file_name:
            category = "学生管理"
        elif "教学" in file_name or "课程" in file_name:
            category = "教学管理"
        elif "学籍" in file_name:
            category = "学籍管理"
        elif "奖励" in file_name or "奖学金" in file_name:
            category = "奖励资助"
        elif "违纪" in file_name or "处分" in file_name:
            category = "纪律管理"
        elif "住宿" in file_name or "宿舍" in file_name:
            category = "宿舍管理"
        elif "创新创业" in file_name:
            category = "创新创业"
        elif "考试" in file_name:
            category = "考试管理"

        return category


class DocumentLoader:
    """文档加载器，负责批量读取和处理文档。"""

    def __init__(self, directory: str, encoding: str = "utf-8", recursive: bool = True):
        """
        初始化文档加载器。

        Args:
            directory: 文档目录路径
            encoding: 文件编码，默认utf-8
            recursive: 是否递归扫描子目录
        """
        self.directory = Path(directory)
        self.encoding = encoding
        self.recursive = recursive
        self.preprocessor = TextPreprocessor()

        if not self.directory.exists():
            raise FileNotFoundError(f"文档目录不存在: {directory}")

        logger.info(f"文档加载器初始化完成，目录: {directory}")

    def scan_files(self, extensions: List[str] = None) -> Tuple[List[Path], List[str]]:
        """扫描目录下的所有指定格式文件。"""
        if extensions is None:
            extensions = [".md"]
            
        success_files = []
        failed_files = []

        pattern = "**/*" if self.recursive else "*"

        for ext in extensions:
            for file_path in self.directory.glob(f"{pattern}{ext}"):
                if file_path.is_file():
                    try:
                        with open(file_path, "r", encoding=self.encoding) as f:
                            f.read(100)
                        success_files.append(file_path)
                    except UnicodeDecodeError:
                        for enc in ["gbk", "gb2312", "gb18030"]:
                            try:
                                with open(file_path, "r", encoding=enc) as f:
                                    f.read(100)
                                success_files.append(file_path)
                                logger.info(f"文件 {file_path.name} 使用编码 {enc} 读取成功")
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            failed_files.append(f"{file_path} (编码错误)")
                            logger.error(f"文件 {file_path} 编码不支持")
                    except Exception as e:
                        failed_files.append(f"{file_path} ({str(e)})")
                        logger.error(f"文件 {file_path} 读取失败: {e}")

        logger.info(f"文件扫描完成，成功: {len(success_files)} 个，失败: {len(failed_files)} 个")
        return success_files, failed_files

    def load_file(self, file_path: Path) -> LoadResult:
        """加载单个文件。"""
        metadata = DocumentMetadata(
            file_path=str(file_path),
            file_name=file_path.name,
            file_size=0,
            encoding=self.encoding,
            load_time=datetime.now().isoformat(),
        )

        try:
            metadata.file_size = file_path.stat().st_size
            content = file_path.read_text(encoding=self.encoding)

            if not content or len(content) < 10:
                for enc in ["gbk", "gb2312", "gb18030"]:
                    try:
                        temp_content = file_path.read_text(encoding=enc)
                        if temp_content and len(temp_content) > len(content):
                            content = temp_content
                            metadata.encoding = enc
                            break
                    except:
                        continue

            if not content or not content.strip():
                return LoadResult(
                    success=False,
                    content="",
                    metadata=metadata,
                    error_message="文件为空"
                )

            metadata.total_chars = len(content)
            metadata.doc_category = self.preprocessor.extract_category(str(file_path))

            title, content_without_title = self.preprocessor.extract_title(content)
            metadata.title = title

            processed_content = self.preprocessor.process_markdown(content_without_title)
            processed_content = self.preprocessor.clean(processed_content)

            if not metadata.title:
                metadata.title = file_path.stem

            return LoadResult(
                success=True,
                content=processed_content,
                metadata=metadata
            )

        except UnicodeDecodeError as e:
            error_msg = f"编码错误: {e}"
            logger.error(f"文件 {file_path} 编码错误: {e}")
            return LoadResult(
                success=False,
                content="",
                metadata=metadata,
                error_message=error_msg
            )
        except Exception as e:
            error_msg = f"读取错误: {str(e)}"
            logger.error(f"文件 {file_path} 读取失败: {e}")
            return LoadResult(
                success=False,
                content="",
                metadata=metadata,
                error_message=error_msg
            )

    def load_all(self, extensions: List[str] = None) -> Tuple[List[LoadResult], Dict[str, Any]]:
        """加载目录下所有文档。"""
        if extensions is None:
            extensions = [".md"]
            
        success_results = []
        failed_results = []

        success_files, failed_files = self.scan_files(extensions)

        logger.info(f"开始加载 {len(success_files)} 个文件...")

        for i, file_path in enumerate(success_files, 1):
            logger.info(f"加载文件 [{i}/{len(success_files)}]: {file_path.name}")
            result = self.load_file(file_path)

            if result.success:
                success_results.append(result)
                logger.info(f"  成功，字符数: {result.metadata.total_chars}")
            else:
                failed_results.append(result)
                logger.warning(f"  失败: {result.error_message}")

        stats = {
            "total_files": len(success_files) + len(failed_files),
            "success_count": len(success_results),
            "failed_count": len(failed_results),
            "failed_files": [str(r.metadata.file_path) for r in failed_results],
            "failed_reasons": [r.error_message for r in failed_results],
            "total_chars": sum(r.metadata.total_chars for r in success_results)
        }

        logger.info(f"加载完成，成功: {stats['success_count']}，失败: {stats['failed_count']}")

        return success_results, stats
