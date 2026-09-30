# RAG 测试报告（学生 C 第 1 阶段）

> 项目进度入口与时间顺序日志见 [progress.md](./progress.md)；本文件只记录**实际运行过**的测试，
> Codex 的真实 API 验收与外部冒烟证据在本文第 5 节如实引用。
> keyword 模式真实 API 样例验收：**通过**；**真实 Chroma + BGE 链路已冒烟跑通、完整评测三轮
> 指标波动，质量验收未通过**（待 B 检查持久化 / 索引与独立评测集，见第 4、5.4 节）。

## 1. 环境与命令

- Python：`backend/.venv/Scripts/python.exe`（Python 3.12）
- 已安装（`importlib.metadata.version` 实测）：fastapi 0.141.1、**starlette 1.7.0**、
  httpx 0.28.1、pydantic 2.13.5、pytest 9.1.1、python-dotenv 1.2.3、uvicorn 0.54.0；
  **未安装** chromadb、sentence-transformers（chroma 相关用假客户端 / 假嵌入覆盖）；
  真实重依赖在独立验证环境 `storage/vector_db/validation-env`（gitignored），不改变本环境
- 命令与结果：

```powershell
backend\.venv\Scripts\python.exe -m pytest tests/backend tests/api -q
# C 本地运行：      117 passed, 1 warning in 4.62s
# Codex 独立复验： 117 passed, 1 warning in 4.38s
backend\.venv\Scripts\python.exe -m pytest tests -q
# 含 tests/retrieval（C 的检索评测）：171 passed, 1 warning（117 + 54，2026-09-30 最新）
```

- warning 来自 `fastapi.testclient` 对 httpx 的 Starlette 弃用提示，与本项目代码无关。
- 分文件用例数（合计 117）：

| 文件 | 数量 | 关注点 |
| --- | --- | --- |
| `tests/backend/test_config.py` | 10 | `.env` 加载、环境变量优先、路径不依赖 CWD、边界收敛、CORS |
| `tests/backend/test_schemas.py` | 7 | trim、1..2000、空白/类型错误、响应结构 |
| `tests/backend/test_llm_service.py` | 16 | 请求体、think、message.content、连接/超时/状态/畸形 JSON/空内容、脱敏、关闭 |
| `tests/backend/test_keyword_retriever.py` | 22 | 命中/零命中、README 排除、排序、截断、来源安全、低相关门槛、真实语料回归 |
| `tests/backend/test_chroma_retriever.py` | 22 | 双路融合、structure-only、默认阈值、缺依赖/集合/故障 503、库故障 vs 缺失正文、并发初始化 |
| `tests/backend/test_rag_service.py` | 13 | 拒答不调用模型、snippet 与上下文一致、严格预算、恶意资料、错误传播 |
| `tests/api/test_chat_api.py` | 27 | `/chat` 全链路、422/503/504/502、CORS、`/health`、A 接口未实现、chroma 故障 |

全部常规测试离线：不访问真实 Ollama、不写现有向量库、不加载 torch / sentence-transformers。

## 2. 需求覆盖矩阵

| 要求 | 覆盖用例 |
| --- | --- |
| 有效问答 + 前端 `answer` 兼容 | `test_chat_happy_path_is_frontend_compatible`、`test_answer_returns_sources_and_mode` |
| 无命中明确话术且不调用模型 | `test_no_hit_refusal_without_llm_call`、`test_no_hits_refuses_without_calling_model`、`test_off_topic_query_refuses_without_model` |
| 空白 / 超长 / 错误类型 422 | `test_invalid_message_rejected_with_422`（参数化 8 组）、`test_length_boundaries` |
| 恶意资料当数据、不执行其中指令 | `test_malicious_material_is_passed_as_data_with_defensive_prompt` |
| 配置 CWD 无关、环境变量优先 | `test_relative_paths_resolve_from_repo_root`、`test_env_overrides_dotenv` |
| 来源排序 / 片段截断 / 不泄露盘符 | `test_ranking_prefers_more_matches`、`test_snippet_is_bounded`、`test_snippet_keeps_match_at_paragraph_end`、`test_source_is_sanitized` |
| 相邻条款列举保持关联 | `test_adjacent_list_stays_with_its_intro`、`test_discipline_kinds_are_in_top_results` |
| 高频通用词不淹没关键问题（IDF/覆盖度） | `test_generic_word_only_match_is_gated`、`test_discipline_kinds_are_in_top_results` |
| 低相关门槛（通用、非白名单） | `test_low_relevance_gate_rejects_off_topic_query`、`test_generic_word_only_match_is_gated` |
| 真实仓库语料回归（违纪处分种类 top5） | `test_real_corpus_discipline_kinds_in_top5`（只读） |
| 真实仓库语料：量子纠缠问题拒答 | `test_real_corpus_off_topic_query_is_refused`（只读） |
| 真实仓库语料：常见问题仍能命中 | `test_real_corpus_common_queries_still_hit`（只读） |
| 双路按 ID 加权融合 | `test_dual_path_weighted_merge_and_sort`、`test_multiple_chunks_ranking_is_stable` |
| structure-only 从内容集合取正文 | `test_structure_only_hit_uses_content_body`、`test_structure_only_passes_production_default_threshold`（默认阈值 0.35）、`test_structure_only_without_content_is_skipped` |
| 库故障 vs 缺失正文的区分 | `test_content_fetch_db_failure_raises_503`（get 异常 → 503）、`test_structure_only_missing_content_id_is_skipped_not_503`（缺失 ID → 跳过） |
| 阈值 / top_k 有界 | `test_min_score_filters_low_relevance`、`test_top_k_is_bounded`（两种检索） |
| 缺依赖 / 缺集合 / 缺目录明确 503 | `test_missing_chromadb_dependency_raises_503`、`test_missing_embedding_dependency_raises_503`、`test_missing_collection_raises_503`、`test_missing_vector_db_directory_raises_503` |
| 向量库故障不当作空库、不泄露内部异常 | `test_collection_count_failure_raises_503_instead_of_empty`、`test_client_factory_failure_raises_503`、`test_embedding_encode_failure_raises_503`、`test_chroma_collection_count_failure_returns_503_without_leaking`、`test_chroma_embedding_failure_returns_503_without_leaking` |
| 不静默回退 keyword | `test_query_failure_raises_without_keyword_fallback`、`test_invalid_retrieval_mode_returns_503_without_silent_fallback` |
| 嵌入模型并发首请求只初始化一次 | `test_concurrent_embedder_initialization_loads_once`、`test_concurrent_first_search_loads_index_once` |
| 上下文长度严格有界（含分隔符/超长标题） | `test_context_budget_counts_block_separators`、`test_context_strictly_bounded_with_extreme_header`、`test_blank_chunk_text_refuses_without_calling_model` |
| 模型各类错误 503/504/502 | `test_connection_error_maps_503_class`、`test_timeout_maps_504_class`、`test_model_404_maps_upstream_error`、`test_invalid_shapes_map_upstream_error`（参数化 6 组）及 API 侧对应用例 |
| `import`/startup 不加载重依赖 | `test_import_does_not_load_heavy_dependencies` |
| `GET /health` 不谎称依赖可用 | `test_health_reports_process_and_config_only` |
| `/chat_with_memory` 等 A 接口未实现边界 | `test_chat_with_memory_not_implemented_yet` |

## 3. 真实语料抽查（只读脚本，非 pytest）

在真实 `knowledge_base/cleaned`（28 份文档）上做只读验收，用于校准 `MIN_COVERAGE=0.2`：

| 查询 | 结果 |
| --- | --- |
| 学生违纪处分有哪些种类？ | 返回 5 条；top5 片段包含“警告、严重警告、记过、留校察看、开除学籍”；第六条列举段进入前五 |
| 量子纠缠如何实现超光速通信？ | 0 条（最高覆盖度 0.084 < 0.2），走拒答、不调用模型 |
| 选课时间是怎么规定的？ | 命中 `20.大连大学本科生选课管理办法.md` 等 4 条 |
| 考试作弊怎么处理 | 命中 `23.大连大学考试违规处理办法.md` 等 5 条 |
| 怎么申请奖学金 | 命中含“申请奖学金、助学金及助学贷款”等 5 条 |
| 图书馆开放时间（短查询） | 命中 1 条弱相关片段（覆盖度 0.215，略高于门槛），由提示词兜底 |

## 4. 未覆盖 / 留给复验

1. **真实 Chroma + BGE 全链路**：`backend/.venv` 仍未安装 `chromadb` / `sentence-transformers`；
   真实链路已由 Codex 在独立验证环境 `storage/vector_db/validation-env` 跑通（API 冒烟见 5.4 节，
   三轮完整评测见 5.5 节），**但现有库跨进程检索不稳定、质量验收未通过**，
   待 B 检查完整持久化 / 索引并用独立评测集复测。
2. **正式检索质量指标**：C 已有 20 正例 / 5 负例的小样本开发回归（keyword 完整、Chroma 三轮观察），
   但**正式 Recall@K / MRR 需要 B 的评测数据**，当前不能出；chroma 三轮观察值波动，不作为质量结论。
3. **keyword 分数语义**：启发式相关度，与 chroma 的 `1/(1+distance)` 不可直接比较。
4. **20 秒前端超时实测**：未做浏览器端到端计时；后端默认 15 秒预留余量。
5. **`docs` 早期草案接口**（`/api/chat` 前缀、知识库分类）未实现，不在本阶段范围。

## 5. Codex 验收证据（本轮引用）

### 5.1 keyword 模式真实 API 样例验收：通过

环境：FastAPI TestClient 调用完整 `/chat` 服务 + 真实本机 Ollama `qwen3.5:4b` + 真实 28 份语料，
`Settings` 默认 15 秒超时。

| 用例 | 结果 |
| --- | --- |
| 学生违纪处分有哪些种类？ | HTTP 200、7.70s；正确列出警告 / 严重警告 / 记过 / 留校察看 / 开除学籍；引用 [4]，对应 `sources[3]` 第六条原文 |
| 量子纠缠如何实现超光速通信？ | HTTP 200、约 0s、`sources=[]`、明确拒答 |
| 图书馆开放时间是什么时候？ | HTTP 200、`sources=[]`、拒答（与短查询“图书馆开放时间”的弱命中区别保留） |

限制：以上只代表 **keyword 模式真实 API 样例**；不宣称浏览器端或 Chroma+BGE 全链路通过。

### 5.2 chroma adapter 外部冒烟（不计入 117 项常规测试）

- 环境：外部独立 Python 运行时 + 真实 `chromadb==0.4.24` + 临时数据库 + 固定 3 维假 embedding；
  **未使用真实 BGE，未改动原向量库**。
- 配置与结果：两个集合各 3 条记录；`top_k=1`；权重 content 0.1 / structure 0.9；
  只有结构路候选 `c` 命中 → 成功从 content 集合取回真实正文、`score=0.9`、集合数量保持 3/3。
- 备注：出现 posthog 遥测 API 兼容警告，不影响查询断言。

### 5.3 仓库与前端核验

- 后端独立复验：`117 passed, 1 warning, 4.38s`（Codex，`backend/.venv/Scripts/python.exe`）。
- 最新全量回归（2026-09-30，含检索评测）：`tests` = `171 passed, 1 warning`
  （`backend/.venv/Scripts/python.exe -X utf8 -m pytest tests -q`）。
- 前端：`pnpm exec vitest run` = 11 passed；`pnpm exec vue-tsc --noEmit` 退出 0。
- 仓库：`git diff --check` 退出 0；`git diff --cached` 为空；
  `frontend/types/auto/components.d.ts` 为用户修改，未改动
  （sha1 `2b124f3924ca4659c8567b206d294f6f5c9a786e`）。

### 5.4 真实 BGE + 真实向量库 API 冒烟：通过（样例级）

- 环境：独立验证环境 `storage/vector_db/validation-env`（Python 3.12、`chromadb 0.4.24`、
  `sentence-transformers 3.4.1`、`transformers 4.48.3`、`torch 2.5.1+cpu`、`numpy 1.26.4`、`posthog 3.25.0`）；
  模型 `storage/vector_db/models/bge-large-zh-v1.5`（revision `79e7739b…0116`，
  `pytorch_model.bin` sha256 `bf84a56f…7a207f2`）；库为 `vectorstore/chroma` 只读副本
  （229×2 集合、1024 维）；LLM 为 Ollama `qwen3.5:4b`。
- 结果：违纪处分种类问题 HTTP 200、8.29s，正确列出五种处分并引用 [4]
  （`knowledge_base/cleaned/10.大连大学学生违纪管理规定.md` 第六条）；
  域外量子问题 HTTP 200、0.15s、`sources=[]` 拒答；首次检索加载 12.20s。
- 安全与限制：原库只复制不打开，10 个文件 hash 前后一致，临时副本已删除；
  冒烟测试**显式 60 秒超时**，不代表默认 15 秒冷启动保证；仅 2 个样例，不代表质量达标。
- 结构化摘要见 `docs/evaluation/chroma_api_smoke.json`。

### 5.5 真实 Chroma + BGE 完整评测：三轮观察，质量验收未通过

- 三轮完整 25 例（每次全新临时副本 + 独立进程，**不挑最好值**）：
  第 1 轮 Hit 15/20、MRR 0.6625、证据 14/20、负例拒绝 2/5（原始 JSON 已被复跑覆盖，不伪造恢复）；
  第 2 轮 Hit 17/20、MRR 0.72、证据 14/20、负例拒绝 1/5；
  第 3 轮 Hit 18/20、MRR 0.6933、证据 13/20、负例拒绝 1/5。
- 观察区间 Hit 75–90%、证据 65–70%、负例拒绝 20–40%；仅三次观察，**不是置信区间或质量结论**。
- 探针证明：4 个查询的 float32 查询向量三次独立进程完全一致、同进程重复查询稳定；
  跨副本候选 ID / 排名变化，**波动在 Chroma 层**；原库 HNSW 目录缺 `index_metadata.pickle`
  （chromadb 0.4.24 据此判断索引存在）；重建次序是否唯一根因**尚未隔离**，不宣称已解决。
- 结论口径：**链路可用；现有库跨进程检索不稳定，质量验收未通过；待 B 检查完整持久化 / 索引
  与独立评测集复测**。详细记录见 [retrieval_evaluation.md](./retrieval_evaluation.md) 第 5 节，
  探针整理见 `docs/evaluation/chroma_repeatability_probe.json`。

## 6. 历史备注（保留，不抹去）

- 第 1 轮实现时的测试结果是 `92 passed, 2 failed`；两个失败已修复并纳入本轮 117 项。
- 第一版真实 `/chat` 问答约 2.66s 但**因检索漏证据错误拒答**；修复分段与排序后，
  才有 5.1 节的 keyword/API 验收通过。
- 检索评测工具的证据判定曾误用报告 200 字截短片段（当时得证据覆盖 19/20）；
  2026-09-30 修复为对比检索器真实返回文本并限定 `expected_source`，keyword 重跑为 **20/20**。
  历史记录保留并更正，**不归咎检索器 500 字窗口**。
- 详细时间顺序见 [progress.md](./progress.md) 第 9 节。
