"""
向量数据库重建脚本。

该脚本用于重建（清空并重新构建）向量数据库。

作者: AI Assistant
日期: 2026-04-02
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config import VectorDBConfig, setup_logging, get_config
from vectorstore import ChromaVectorStore, BGEEmbeddings


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="向量数据库重建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径"
    )

    parser.add_argument(
        "--vectorstore-dir",
        type=str,
        default=None,
        help="向量库存储目录"
    )

    parser.add_argument(
        "--collection-name",
        type=str,
        default=None,
        help="向量库集合名称"
    )

    parser.add_argument(
        "--confirm",
        action="store_true",
        help="确认删除（不提示）"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别"
    )

    return parser.parse_args()


def main():
    """主函数入口。"""
    args = parse_args()

    logger = setup_logging(log_level=getattr(logging, args.log_level.upper(), logging.INFO))
    logger = logging.getLogger("VectorDBBuilder.Rebuild")

    if args.config:
        config = VectorDBConfig.from_yaml(args.config)
    else:
        config = get_config()

    if args.vectorstore_dir:
        config.persist_directory = args.vectorstore_dir
    if args.collection_name:
        config.collection_name = args.collection_name

    logger.info("=" * 60)
    logger.info("向量数据库重建工具")
    logger.info(f"向量库路径: {config.persist_directory}")
    logger.info(f"集合名称: {config.collection_name}")
    logger.info("=" * 60)

    if not os.path.exists(config.persist_directory):
        logger.error(f"向量库目录不存在: {config.persist_directory}")
        logger.info("请先运行 build_vectordb.py 构建向量库")
        sys.exit(1)

    if not args.confirm:
        confirm = input("\n??  确认要清空并重建向量库吗？此操作不可恢复 (yes/no): ")
        if confirm.lower() not in ["yes", "y"]:
            logger.info("操作已取消")
            sys.exit(0)

    try:
        logger.info("正在初始化向量库连接...")

        embeddings = BGEEmbeddings(
            model_name=config.embedding_model_name,
            model_kwargs=config.embedding_model_kwargs,
            encode_kwargs=config.encode_kwargs
        )

        vectorstore = ChromaVectorStore(
            persist_directory=config.persist_directory,
            collection_name=config.collection_name,
            embeddings=embeddings
        )

        if vectorstore.count() > 0:
            logger.info(f"当前向量库包含 {vectorstore.count()} 个文本块")
            vectorstore.clear()
            logger.info("? 向量库已清空")
        else:
            logger.info("向量库为空，无需清空")

        logger.info("\n向量库已准备好重建")
        logger.info("请运行: python build_vectordb.py --rebuild")

    except Exception as e:
        logger.error(f"重建准备失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
