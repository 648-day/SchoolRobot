# -*- coding: utf-8 -*-
"""
双重向量检索对比测试脚本。

该脚本用于：
1. 构建双重向量库
2. 执行测试查询
3. 对比双重向量检索的效果
4. 输出详细的对比报告

作者: AI Assistant
日期: 2026-04-06
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from build_vectordb import VectorDBConfig, get_config, setup_logging
from dual_vectorstore import DualVectorStore
from vectorstore import BGEEmbeddings

logger = logging.getLogger("DualVectorTest")


TEST_QUERIES = [
    {
        "query": "学生违纪处分有哪些种类？",
        "expected_keywords": ["警告", "严重警告", "记过", "留校察看", "开除学籍"],
        "description": "测试具体规定的检索"
    },
    {
        "query": "学生可以申请哪些奖学金？",
        "expected_keywords": ["奖学金", "申请", "资助"],
        "description": "测试跨文档主题检索"
    },
    {
        "query": "学籍注册需要什么条件？",
        "expected_keywords": ["注册", "学籍", "学费", "手续"],
        "description": "测试流程性内容检索"
    },
    {
        "query": "创新创业学分如何认定？",
        "expected_keywords": ["创新创业", "学分", "认定"],
        "description": "测试专业术语检索"
    },
    {
        "query": "学生宿舍管理规定",
        "expected_keywords": ["宿舍", "管理", "规定"],
        "description": "测试主题性检索"
    }
]


class DualVectorTester:
    """双重向量检索测试器。"""
    
    def __init__(self, config: VectorDBConfig):
        """
        初始化测试器。
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.embeddings: BGEEmbeddings = None
        self.dual_vectorstore: DualVectorStore = None
        
    def initialize(self) -> bool:
        """初始化测试环境。"""
        try:
            logger.info("=" * 60)
            logger.info("初始化测试环境...")
            logger.info("=" * 60)
            
            logger.info("加载BGE向量模型...")
            self.embeddings = BGEEmbeddings(
                model_name=self.config.embedding_model_name,
                model_kwargs=self.config.model_kwargs,
                encode_kwargs=self.config.encode_kwargs
            )
            logger.info(f"✓ 模型加载成功，维度: {self.embeddings.embedding_dim}")
            
            logger.info("加载双重向量库...")
            self.dual_vectorstore = DualVectorStore(
                persist_directory=self.config.persist_directory,
                collection_name=self.config.collection_name,
                embeddings=self.embeddings
            )
            content_count, structure_count = self.dual_vectorstore.count()
            logger.info(f"✓ 双重向量库加载成功")
            logger.info(f"  内容向量数: {content_count}")
            logger.info(f"  结构向量数: {structure_count}")
            
            if content_count == 0 or structure_count == 0:
                logger.error("向量库为空，请先运行 build_vectordb.py 构建向量库")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def run_comparison_test(self) -> Dict[str, Any]:
        """
        运行双重向量检索测试。
        
        Returns:
            Dict[str, Any]: 测试结果
        """
        logger.info("\n" + "=" * 60)
        logger.info("开始双重向量检索测试...")
        logger.info("=" * 60)
        
        test_results = []
        
        for i, test_case in enumerate(TEST_QUERIES, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"测试用例 {i}/{len(TEST_QUERIES)}: {test_case['description']}")
            logger.info(f"查询: {test_case['query']}")
            logger.info(f"{'='*60}")
            
            try:
                dual_start = time.time()
                dual_results = self.dual_vectorstore.search_dual(
                    query=test_case['query'],
                    n_results=10,  # 增加到10个结果
                    content_weight=self.config.content_weight,
                    structure_weight=self.config.structure_weight,
                    enable_context=self.config.enable_context,
                    context_window=2  # 增加上下文窗口到2
                )
                dual_time = time.time() - dual_start
                
                logger.info(f"\n检索完成！")
                logger.info(f"  双重向量检索:")
                logger.info(f"    耗时: {dual_time:.3f}秒")
                logger.info(f"    结果数: {len(dual_results)}")
                
                if not dual_results:
                    logger.warning("  警告: 未找到任何结果")
                    continue
                
                dual_score = self._evaluate_dual_results(dual_results, test_case['expected_keywords'])
                logger.info(f"    得分: {dual_score:.2f}")
                
                test_result = {
                    "query": test_case['query'],
                    "description": test_case['description'],
                    "expected_keywords": test_case['expected_keywords'],
                    "dual_vector": {
                        "results": dual_results,
                        "time": dual_time,
                        "score": dual_score
                    }
                }
                
                test_results.append(test_result)
                
                logger.info(f"\n  最佳结果预览:")
                best_result = dual_results[0]
                logger.info(f"    综合得分: {best_result.combined_score:.3f}")
                logger.info(f"    内容得分: {best_result.content_score:.3f}")
                logger.info(f"    结构得分: {best_result.structure_score:.3f}")
                
                logger.info(f"\n    【检索内容】:")
                logger.info(f"    {best_result.content}")
                
                if best_result.context_before:
                    logger.info(f"\n    【前文上下文】:")
                    logger.info(f"    {best_result.context_before}")
                
                if best_result.context_after:
                    logger.info(f"\n    【后文上下文】:")
                    logger.info(f"    {best_result.context_after}")
                
                if len(dual_results) > 1:
                    logger.info(f"\n  其他结果（共{len(dual_results)}个）:")
                    for idx, result in enumerate(dual_results[1:], 2):
                        logger.info(f"    [{idx}] 综合得分: {result.combined_score:.3f}")
                        logger.info(f"        内容: {result.content[:200]}...")

                    
            except Exception as e:
                logger.error(f"测试用例执行失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        return self._generate_report(test_results)
    
    def _evaluate_dual_results(self, results: List, expected_keywords: List[str]) -> float:
        """
        评估双重检索结果质量。
        
        Args:
            results: 双重检索结果
            expected_keywords: 期望关键词
            
        Returns:
            float: 评估得分
        """
        if not results:
            return 0.0
        
        total_score = 0.0
        
        for result in results:
            content = result.content.lower()
            keyword_score = 0.0
            
            for keyword in expected_keywords:
                if keyword.lower() in content:
                    keyword_score += 1.0
            
            keyword_score = keyword_score / len(expected_keywords) if expected_keywords else 0
            
            context_score = 0.0
            if result.context_before:
                context_score += 0.5
            if result.context_after:
                context_score += 0.5
            
            combined_score = result.combined_score
            
            total_score += (keyword_score * 0.5 + context_score * 0.2 + combined_score * 0.3)
        
        return total_score / len(results) if results else 0.0
    
    def _generate_report(self, test_results: List[Dict]) -> Dict[str, Any]:
        """
        生成测试报告。
        
        Args:
            test_results: 测试结果列表
            
        Returns:
            Dict[str, Any]: 测试报告
        """
        logger.info("\n" + "=" * 60)
        logger.info("生成测试报告...")
        logger.info("=" * 60)
        
        dual_total_score = sum(r['dual_vector']['score'] for r in test_results)
        dual_avg_time = sum(r['dual_vector']['time'] for r in test_results) / len(test_results)
        
        report = {
            "summary": {
                "total_tests": len(test_results),
                "dual_vector_avg_score": dual_total_score / len(test_results),
                "dual_vector_avg_time": dual_avg_time
            },
            "details": test_results
        }
        
        logger.info(f"\n测试总结:")
        logger.info(f"  总测试数: {len(test_results)}")
        logger.info(f"  双重向量平均得分: {report['summary']['dual_vector_avg_score']:.2f}")
        logger.info(f"  双重向量平均耗时: {report['summary']['dual_vector_avg_time']:.3f}秒")
        
        return report


def main():
    """主函数。"""
    config = get_config()
    
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 同时配置 VectorDBBuilder 的日志
    setup_logging(log_level=log_level)
    
    logger.info("=" * 60)
    logger.info("双重向量检索测试")
    logger.info("=" * 60)
    
    tester = DualVectorTester(config)
    
    if not tester.initialize():
        logger.error("测试环境初始化失败")
        return False
    
    report = tester.run_comparison_test()
    
    logger.info("\n" + "=" * 60)
    logger.info("测试完成！")
    logger.info("=" * 60)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
