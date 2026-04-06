"""
向量库验证脚本。

用于验证向量库是否正确构建和持久化。

作者: AI Assistant
日期: 2026-04-02
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def check_vectorstore():
    """检查向量库状态。"""
    print("=" * 60)
    print("向量库验证脚本")
    print("=" * 60)

    # 检查向量库目录
    vectorstore_dir = Path(__file__).parent.parent / "vectorstore" / "chroma"
    print(f"\n向量库目录: {vectorstore_dir}")
    print(f"目录是否存在: {vectorstore_dir.exists()}")

    if not vectorstore_dir.exists():
        print("? 向量库目录不存在，需要先运行 build_vectordb.py")
        return False

    # 列出目录内容
    print(f"\n目录内容:")
    for item in vectorstore_dir.iterdir():
        if item.is_dir():
            print(f"  ? {item.name}/")
            for subitem in list(item.iterdir())[:5]:
                print(f"      - {subitem.name}")
        else:
            print(f"  ? {item.name}")

    # 尝试连接向量库
    print("\n" + "-" * 60)
    print("尝试连接向量库...")
    print("-" * 60)

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        client = chromadb.PersistentClient(
            path=str(vectorstore_dir),
            settings=chromadb.config.Settings(anonymized_telemetry=False)
        )

        # 获取集合
        collection = client.get_collection(name="school_documents")
        count = collection.count()

        print(f"? 成功连接到向量库")
        print(f"? 集合名称: {collection.name}")
        print(f"? 文档数量: {count}")

        if count == 0:
            print("\n? 向量库为空！")
            print("请运行: python build_vectordb.py --rebuild")
            return False

        # 测试查询
        print("\n" + "-" * 60)
        print("测试向量检索...")
        print("-" * 60)

        embeddings = SentenceTransformer("BAAI/bge-large-zh-v1.5")
        
        # 使用多个测试查询
        test_queries = [
            "奖学金金额是多少",
            "奖学金评选条件",
            "违纪处分规定"
        ]
        
        for query in test_queries:
            print(f"\n查询: {query}")
            query_embedding = embeddings.encode(query)

            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=3
            )

            if results and results.get("documents") and results["documents"][0]:
                print(f"找到 {len(results['documents'][0])} 条结果:")
                for i, doc in enumerate(results["documents"][0], 1):
                    metadata = results["metadatas"][0][i-1]
                    title = metadata.get("title", "N/A")
                    file_name = metadata.get("file_name", "N/A")
                    print(f"  [{i}] {title} - {file_name}")
                    print(f"      {doc[:100]}...")
            else:
                print("  无结果")

        print("\n" + "=" * 60)
        print("? 向量库验证完成")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"? 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    check_vectorstore()
