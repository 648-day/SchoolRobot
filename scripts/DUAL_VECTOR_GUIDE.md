# 双重向量检索机制使用说明

## 概述

双重向量检索机制是对原有单一向量检索的改进，通过从不同维度对文档进行向量化，提高检索结果的信息完整性和准确性。

## 核心原理

### 1. 双重向量架构

#### 第一维度：内容向量（Content Vector）
- **目标**：检索具体的内容细节
- **策略**：对文本块内容进行向量化
- **优势**：能够精确匹配具体条款和细节内容

#### 第二维度：结构向量（Structure Vector）
- **目标**：检索文档结构和章节信息
- **策略**：
  - 提取章节标题和条目编号
  - 构建章节摘要（包含标题、条目、关键词）
  - 对摘要进行向量化
- **优势**：能够快速定位相关章节，提供上下文信息

### 2. 混合检索机制

检索流程：
1. **结构向量检索**：定位相关章节和文档结构
2. **内容向量检索**：获取具体内容细节
3. **结果融合**：合并两个维度的检索结果
4. **上下文增强**：自动获取前后相邻文本块

### 3. 上下文增强

- **策略**：检索到文本块后，自动获取前后相邻的文本块
- **优势**：提供完整的信息上下文，避免信息断裂

## 配置说明

### config.yaml 配置项

```yaml
# 双重向量检索配置
use_dual_vector: true          # 是否启用双重向量检索
content_weight: 0.6            # 内容向量权重（0-1）
structure_weight: 0.4          # 结构向量权重（0-1）
enable_context: true           # 是否启用上下文增强
context_window: 1              # 上下文窗口大小
```

### 参数说明

- **use_dual_vector**：
  - `true`：使用双重向量检索
  - `false`：使用单一向量检索（向后兼容）

- **content_weight** 和 **structure_weight**：
  - 两者之和应为 1.0
  - 内容权重较高时，更注重具体内容匹配
  - 结构权重较高时，更注重文档结构定位

- **enable_context**：
  - `true`：检索结果包含上下文信息
  - `false`：仅返回匹配的文本块

- **context_window**：
  - 获取前后各N个文本块作为上下文
  - 建议值：1-2

## 使用方法

### 1. 构建双重向量库

```bash
# 使用默认配置（双重向量检索）
python build_vectordb.py

# 重建向量库
python build_vectordb.py --rebuild
```

### 2. 运行对比测试

```bash
# 测试双重向量检索效果
python test_dual_vector.py
```

### 3. 代码调用示例

```python
from build_vectordb import VectorDBConfig
from dual_vectorstore import DualVectorStore
from vectorstore import BGEEmbeddings

# 初始化
config = VectorDBConfig.from_yaml("config.yaml")
embeddings = BGEEmbeddings(
    model_name=config.embedding_model_name,
    model_kwargs=config.model_kwargs,
    encode_kwargs=config.encode_kwargs
)

dual_store = DualVectorStore(
    persist_directory=config.persist_directory,
    collection_name=config.collection_name,
    embeddings=embeddings
)

# 执行检索
results = dual_store.search_dual(
    query="学生违纪处分有哪些种类？",
    n_results=5,
    content_weight=0.6,
    structure_weight=0.4,
    enable_context=True,
    context_window=1
)

# 处理结果
for result in results:
    print(f"内容: {result.content}")
    print(f"综合得分: {result.combined_score}")
    print(f"内容得分: {result.content_score}")
    print(f"结构得分: {result.structure_score}")
    
    if result.context_before:
        print(f"前文: {result.context_before}")
    if result.context_after:
        print(f"后文: {result.context_after}")
```

## 性能对比

### 预期改进

1. **信息完整性提升**：
   - 上下文增强避免信息断裂
   - 结构向量提供文档定位信息

2. **检索准确性提升**：
   - 双重维度匹配提高准确率
   - 混合评分机制优化排序

3. **用户体验改善**：
   - 提供更完整的答案
   - 减少多次查询需求

### 测试指标

- **关键词覆盖率**：检索结果中包含期望关键词的比例
- **上下文完整性**：是否提供前后文信息
- **检索耗时**：单一向量 vs 双重向量
- **综合得分**：结合多个指标的评估

## 适用场景

### 推荐使用双重向量检索的场景

1. **法规文档检索**：需要完整条款信息
2. **规章制度查询**：需要上下文关联
3. **流程性内容**：需要前后步骤信息
4. **跨文档主题**：需要结构化定位

### 可以使用单一向量检索的场景

1. **简单关键词查询**：不需要上下文
2. **性能优先场景**：检索速度要求高
3. **资源受限环境**：存储空间有限

## 技术细节

### 结构信息提取

系统自动提取以下结构信息：
- 章节标题（一级、二级、三级标题）
- 条目编号（第一条、第二条等）
- 关键词（学生、管理、规定等）

### 向量化策略

1. **内容向量**：
   - 直接对文本块内容进行向量化
   - 使用BGE中文向量模型

2. **结构向量**：
   - 构建结构化摘要
   - 对摘要进行向量化
   - 包含标题、条目、关键词信息

### 结果融合算法

```
综合得分 = 内容权重 × 内容得分 + 结构权重 × 结构得分
```

## 故障排查

### 常见问题

1. **向量库已存在错误**
   - 解决：使用 `--rebuild` 参数重建

2. **内存不足**
   - 解决：减小 `chunk_size` 或降低 `context_window`

3. **检索速度慢**
   - 解决：调整批处理大小或使用GPU

### 日志查看

系统提供详细的日志输出：
- 组件初始化状态
- 文档处理进度
- 向量化进度
- 检索性能指标

## 未来优化方向

1. **多维度扩展**：增加更多检索维度
2. **动态权重**：根据查询类型自动调整权重
3. **缓存机制**：优化重复查询性能
4. **增量更新**：支持文档增量添加

## 联系支持

如有问题或建议，请查看项目文档或联系开发团队。
