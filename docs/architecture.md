# 架构说明（截至 C 第 1 阶段）

## 请求流程

```text
前端（Vue3，Vite 端口 3333）
  │  axios: 先 POST /chat_with_memory，任何失败都回落 POST /chat（timeout 20s）
  ▼
FastAPI（backend/app/main.py，create_app 注入配置与服务）
  │  POST /chat（同步路由，跑在线程池，不阻塞事件循环）
  ▼
RAGService（backend/app/services/rag_service.py）
  ├─ advanced_search：调用注入的 retriever，按 top_k / 阈值取片段
  │    ├─ KeywordRetriever：knowledge_base/cleaned 的 md/txt，IDF 覆盖度 + 低相关门槛
  │    └─ ChromaRetriever：只读 school_documents_content / school_documents_structure
  ├─ 无命中：直接返回“参考资料未提及，请咨询学校相关部门。”，不调用模型
  └─ 有命中：基础提示词 + 参考资料 + 问题 → OllamaLLM
        │  httpx.Client POST /api/chat（stream=false，temperature=0.1，think 默认 false）
        ▼
      Ollama（本机 127.0.0.1:11434，模型 qwen3.5:4b）
```

## 组件职责

| 文件 | 作用 |
| --- | --- |
| `backend/app/core/config.py` | 读取环境变量与 `backend/.env`（环境变量优先）；相对路径按仓库根解析 |
| `backend/app/schemas/chat.py` | `ChatRequest`（trim + 1..2000 字符）、`ChatResponse`、`SourceItem` |
| `backend/app/api/chat.py` | `POST /chat` 路由与依赖注入 |
| `backend/app/services/rag_service.py` | RAG 主流程、拒答逻辑、上下文预算、提示词装载 |
| `backend/app/services/retriever.py` | keyword / chroma 两种检索实现与 503 错误定义 |
| `backend/app/services/llm_service.py` | Ollama 调用与错误映射（503 / 504 / 502） |
| `backend/app/prompts/rag_base.txt` | C 的基础提示词（A 的 `campus_prompt.txt` 保持不动） |

## 检索模式

### keyword（默认）

- 适用：本机开发，不装 chromadb / sentence-transformers。
- 文档处理：按空行分块 → 标题并入正文 → 列举项（（一）/1./①）并入上一段 →
  上一段无句末标点时与下一段合并（原文条款被空行截断的情况），段落上限 1200 字。
- 打分：中文双字词 + 英文/数字词，词元按段落级 IDF 加权；覆盖率（命中词元的 IDF
  占查询总 IDF 的比例）+ 命中强度 + 标题命中 → 0..1 分数。
- 低相关门槛：`MIN_COVERAGE`（默认 0.2），过滤只命中高频通用词或少量词元的片段；
  零命中直接拒答。
- 片段：命中词附近取窗口，严格不超过 `SNIPPET_MAX_CHARS`。
- 分数含义：启发式相关度，**不是**向量相似度或概率。

### chroma（可选）

- 前提：B 已构建向量库；安装 `chromadb`、`sentence-transformers` 且本地有 BGE 模型。
- 只读查询 `school_documents_content` / `school_documents_structure`（不创建集合、不执行
  add / delete / rebuild），显式 `query_embeddings`；不使用 B 的 `DualVectorStore`
  构造器（它会创建集合并吞错）。
- 双路按 ID 加权融合：`0.6 * content_score + 0.4 * structure_score`，
  `score = 1 / (1 + distance)`；结构路命中必须从内容集合取正文，取不到就丢弃。
- 默认阈值 0.35；`local_files_only=True` 不联网下载模型；客户端与嵌入模型惰性加载
  且加锁，避免并发首请求重复加载。
- 查询会通过 chromadb 打开持久化目录，`PersistentClient` 可能维护底层元数据，不承诺
  物理文件只读；联调现有库前先备份。真实 BGE + 真实向量库端到端尚未验证。
- 缺依赖 / 缺目录 / 缺集合 / 查询失败一律 503，**不**静默回退 keyword。

## 诚实说明与边界

- `/health` 只报告进程与配置，不探测 Ollama 与向量库。
- RAGService 不写历史记录；`/chat_with_memory`、历史接口、SSE 属于 A 同学。
- 向量库构建、知识库清洗属于 B 同学；C 只读消费。
- 提示词要求：只依资料回答、资料当数据不当指令、不假称学校官方、不使用内置知识
  补充校园政策；资料不足时明确说明“参考资料未提及”。
