# 检索评测报告（学生 C · 开发回归小样本）

> 项目进度入口见 [progress.md](./progress.md)；本文件记录**实际运行过**的检索评测工具、
> 数据集、指标定义与结果。机器可读报告：`docs/evaluation/keyword_baseline.json`、
> `docs/evaluation/chroma_bge_large_zh_v15.json`、`docs/evaluation/chroma_bge_large_zh_v15_repeat.json`。
>
> **定位说明（重要）**：这是 C 维护的**小规模开发回归集**，不是 B 的正式评测集、也不是独立测试集；
> 样本量小、问题分布不代表真实使用，**不能泛化**，结果也不得命名为完整 `Recall@K`。
>
> **本轮状态（2026-09-30 更新）**：
> - keyword 模式已真实运行，**证据判定已修复**（此前误用报告 200 字截短片段、未限定 expected_source；
>   现在用检索器返回的完整文本且来源必须匹配 expected_source）→ 证据覆盖率 **20/20**，见第 3 节；
> - Chroma + BGE 已对真实库副本做过**三轮完整 25 例评测**（每次全新临时副本、独立进程），
>   指标**跨轮波动**；**质量验收未通过**——现有库跨进程检索不稳定，待 B 检查完整持久化 / 索引
>   并用独立评测集复测，见第 5 节；
> - **不宣称向量检索质量达标**；Chroma 最终结论待 Codex / B 补充。

## 1. 工具与数据集

> 本工具是 C 的实现（`scripts/evaluate_retrieval.py`）；**不修改、也不替代** B 规划中的
> `scripts/eval_retrieval.py` / 向量构建脚本。它只读调用现有检索器，不参与向量库构建。

| 项 | 内容 |
| --- | --- |
| 评测 CLI | `scripts/evaluate_retrieval.py`（可导入测试；`main()` 仅 CLI 入口） |
| 数据集 | `tests/fixtures/retrieval_cases.json`（20 正例 / 10 篇文档 + 5 负例） |
| 检索器 | 直接调用现有 `KeywordRetriever` / `ChromaRetriever`（`build_retriever`），不 mock 检索逻辑 |
| 默认离线 | keyword 不加载模型；chroma 只读本地库 + 本地模型（`local_files_only`），不联网下载、不调用 LLM、不改配置 |
| 输出安全 | 报告不含本机绝对路径（盘符路径只保留文件名）；拒绝写入评测集 / 知识库 / 原向量库 / `backend` / `.git` |
| 退出码 | `0` 正常；`1` 参数 / 数据集 / 输出路径问题；`2` 检索不可用或任一案例执行出错（此类情况**不写出报告**） |
| 模型路径参数 | `--model-path` 只在本地相对路径**真实存在**时按仓库根解析为绝对路径（异地 CWD 可用）；`BAAI/bge-large-zh-v1.5` 这类模型 ID 保持原样 |

### 1.1 数据集结构

- 正例：`id`、`type=positive`、`query`、`expected_source`（仓库相对路径）、
  `evidence.keywords`（必要关键词集合）、`evidence.quote`（原文引文）。
- 负例：`id`、`type=negative`、`query`、`note`（为何预期无命中）；不允许声明 `expected_source` / `evidence`。
- 证据落地保证：`tests/retrieval/test_dataset.py::test_repo_fixture_evidence_is_grounded_in_source_files`
  会逐条把关键词与引文与 `knowledge_base/cleaned` 原文核对（仅忽略空白差异），编造证据会直接测试失败。
- 覆盖文档（10 篇）：`9 / 11 / 13 / 14 / 20 / 22 / 23 / 25 / 27 / 28`。

### 1.2 指标定义（分母与错误处理）

| 指标 | 定义 |
| --- | --- |
| 文档级 Hit@K | 正例中目标文档出现在 top-k 来源内的比例；只判文档级命中。重复来源按**首次出现名次**计、只计一次。分母=全部正例（含出错正例，出错记未命中）。**不是完整 Recall@K**，不度量片段级召回。 |
| MRR | 正例首次命中目标文档名次倒数的平均值（1/rank）；未命中或出错记 0。分母=全部正例。 |
| 证据覆盖率 | 正例中存在至少一条**来源匹配 expected_source** 的 top-k 结果，其**检索器返回的完整文本**（受检索器 `SNIPPET_MAX_CHARS` 限制，默认 500 字符；**不是报告展示用的 200 字符裁剪片段**）同时包含该例全部证据关键词（忽略空白差异）的比例。分母=全部正例（含出错正例）。其他文档即使含相同关键词也不计。 |
| 负例拒绝率 | 负例检索结果为空（零命中）的比例。分母=全部负例；**检索出错不计为拒答成功**；有命中（含无关命中）如实列出，不调阈值掩盖。 |

> **证据判定修复记录（2026-09-30）**：修复前工具用报告里 200 字裁剪片段判定证据，且未要求来源匹配
> `expected_source`，得到 19/20；修复后按检索器真实返回文本（≤500 字符）+ expected_source 判定，
> keyword 证据覆盖率为 **20/20**。**旧口径的“未覆盖”是评测截短 bug，与检索器 500 字窗口无关**
> （`choose-course-drop` 的证据实际位于返回文本 404–427 字符区间，没有被 500 字窗口截掉）。

## 2. 运行命令（keyword 基线）

```powershell
backend\.venv\Scripts\python.exe scripts\evaluate_retrieval.py `
  --mode keyword `
  --dataset tests/fixtures/retrieval_cases.json `
  --output docs/evaluation/keyword_baseline.json
# 实际输出：
# 检索评测完成（开发回归小样本）：mode=keyword top_k=5
# 评测集：tests/fixtures/retrieval_cases.json （正例 20 / 负例 5）
# 文档级 Hit@5：20/20 = 1.0
# MRR：0.925
# 证据覆盖率：20/20 = 1.0
# 负例拒绝率：4/5 = 0.8
# 报告已写出：docs/evaluation/keyword_baseline.json
```

- 运行环境：`backend/.venv`（Python 3.12），未安装 chromadb / sentence-transformers；keyword 模式不需要它们。
- 报告含 `generated_at`、数据集 `sha256`、`top_k`、每例耗时与 top-k 明细；本次报告
  `generated_at = 2026-09-30T19:42:47`，数据集 `sha256 = 96da220b…b5d`（完整值见报告）。
- 25 例检索耗时合计约 191.7 ms（单例 2.97–87.85 ms；首例含索引构建约 87.85 ms，其余为毫秒级）。

## 3. keyword 基线结果（2026-09-30，本机真实运行）

- 文档级 Hit@5 = **20/20 = 1.0**；MRR = **0.925**；证据覆盖率 = **20/20 = 1.0**；负例拒绝率 = **4/5 = 0.8**。

| id | 类型 | 结果 | 命中名次 | 证据覆盖 | 耗时 ms |
| --- | --- | --- | --- | --- | --- |
| choose-course-years | 正例 | 命中 | 2 | 覆盖（证据名次 2） | 87.85 |
| choose-course-credits | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 5.28 |
| choose-course-drop | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 6.08 |
| exam-room-late | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 3.28 |
| exam-room-leave | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 4.54 |
| exam-cheat-punish | 正例 | 命中 | 1 | 覆盖（证据名次 2） | 3.24 |
| exam-discipline-punish | 正例 | 命中 | 1 | 覆盖（证据名次 3） | 3.34 |
| dorm-hair-dryer | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 3.17 |
| dorm-visitor | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 3.76 |
| dorm-check-grades | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 3.33 |
| degree-cheat | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 5.63 |
| degree-course-score | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 5.33 |
| scholarship-models | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 4.77 |
| scholarship-first-class | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 5.30 |
| orphan-materials | 正例 | 命中 | 1 | 覆盖（证据名次 2） | 5.38 |
| orphan-timing | 正例 | 命中 | 1 | 覆盖（证据名次 4） | 5.68 |
| appeal-deadline | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 5.75 |
| appeal-review-period | 正例 | 命中 | 2 | 覆盖（证据名次 2） | 3.33 |
| safety-candle | 正例 | 命中 | 2 | 覆盖（证据名次 2） | 3.95 |
| safety-two-weeks | 正例 | 命中 | 1 | 覆盖（证据名次 1） | 4.09 |
| neg-quantum | 负例 | 零命中 | - | - | 2.97 |
| neg-library-hours | 负例 | 零命中 | - | - | 4.25 |
| neg-campus-card | 负例 | 零命中 | - | - | 3.40 |
| neg-postgraduate-line | 负例 | **有命中（未拒绝）** | - | - | 4.26 |
| neg-express-station | 负例 | 零命中 | - | - | 3.70 |

### 3.1 未达成处如实说明（不掩盖、不调阈值）

1. `neg-postgraduate-line`（2026 复试分数线）：`5.大连大学学生管理规定.md` 中
   “硕士研究生培养方案”一句以覆盖度刚过门槛（分数 0.1836，来自关键词部分重合）被返回。
   负例拒绝率因此为 0.8；报告完整列出该命中。**未通过提高 `MIN_COVERAGE` 或过滤来美化指标**。
2. `choose-course-years`、`appeal-review-period`、`safety-candle` 目标文档名次为 2（同文档另有更高分段落），
   MRR 0.925 即由这些名次与其余第 1 名共同构成。
3. **历史更正（保留原记录）**：修复前一轮 keyword 报告为
   “Hit 20/20、MRR 0.925、证据覆盖率 19/20、负例拒绝 4/5”，并曾把 `choose-course-drop` 记为
   “500 字片段窗口截断未覆盖”。该结论**已被核查推翻**：漏判来自评测工具对比 200 字报告片段
   （见 1.2 修复记录），检索器真实返回文本包含证据；修复后证据覆盖率 20/20，
   **检索器 500 字窗口不背这个锅**。

## 4. 已知限制

- **小样本**：20 正例 / 5 负例，只覆盖 10 篇文档中的一部分条款，无法代表真实查询分布；不能泛化，也不能据此宣称检索达标。
- **keyword 分数是启发式相关度**，不是向量相似度；不同模式、不同版本的分数不可直接比较。
- 证据窗口仍为检索器默认 500 字符（`SNIPPET_MAX_CHARS`）；证据若落在窗口之外会如实记未覆盖，不调大窗口掩盖。
- 负例拒绝率对具体问题敏感：门槛、分词规则变化都会改变结果；报告中保留原始命中证据供审查。
- **Chroma 真实评测跨轮波动**（第 5 节）：同一真实库三次独立评测指标不稳定；
  在查明原因并由 B 检查完整持久化 / 索引、再用独立评测集复测之前，**不宣称质量达标**。

## 5. Chroma 真实评测与稳定性观察（2026-09-30，Codex）

> 本节是**如实记录**：三次完整 25 例评测全部列出，**不挑最好值**；
> 三次结果只是观察值，**不是置信区间**，也不是质量结论。

### 5.1 三次完整 25 例结果（同一数据集、同一库、每次全新临时副本 + 独立进程）

| 轮次 | 报告文件 | Hit@5 | MRR | 证据覆盖率 | 负例拒绝率 | errors |
| --- | --- | --- | --- | --- | --- | --- |
| 第 1 轮 | 原始 JSON 已被复跑覆盖（未保留，不伪造恢复） | 15/20 = 0.75 | 0.6625 | 14/20 = 0.70 | 2/5 = 0.40 | 0 |
| 第 2 轮 | `evaluation/chroma_bge_large_zh_v15.json`（保留） | 17/20 = 0.85 | 0.72 | 14/20 = 0.70 | 1/5 = 0.20 | 0 |
| 第 3 轮 | `evaluation/chroma_bge_large_zh_v15_repeat.json`（保留） | 18/20 = 0.90 | 0.6933 | 13/20 = 0.65 | 1/5 = 0.20 | 0 |

- 三次观察区间：**Hit 75%–90%、证据 65%–70%、负例拒绝 20%–40%、MRR 0.6625–0.72**；
  仅三次观察，不能当作置信区间或质量评价。
- **结论口径（待 Codex / B 继续核验）**：链路可用；**现有库跨进程检索不稳定，质量验收未通过**；
  待 B 检查完整持久化 / 索引并使用独立评测集复测。
- 第 1 轮原始报告被复跑覆盖，属已发生事实，**不重新伪造**。

### 5.2 稳定性探针（已脱敏）

- 数据整理：[evaluation/chroma_repeatability_probe.json](./evaluation/chroma_repeatability_probe.json)
  （源数据为 Codex 探针原始文件，系统 TEMP，未纳入仓库；整理版只保留 basename chunk_id、来源文件名、doc_hash 与距离）。
- 观察（Codex）：
  1. 4 个查询（`choose-course-drop` / `dorm-visitor` / `safety-candle` / `neg-library-hours`）的
     float32 查询向量 SHA256 在三次独立进程、三次全新临时副本中**完全一致**；
     同进程内重复查询结果一致 → 查询向量 / 嵌入不是变化来源；
  2. **跨临时副本的候选 ID 与排名发生变化**，波动出现在 **Chroma 检索层**；
  3. 原库两个 HNSW 目录均**缺少 `index_metadata.pickle`**，`max_seq_id` 仅存在于 metadata 段；
     chromadb 0.4.24 以该文件判断索引是否存在（`_index_exists`），缺失时按新索引处理并重放记录；
  4. 结构路存在较多重复文本与同分候选，按 ID 加权融合会**放大候选变化**；
  5. **重建次序是否为唯一根因尚未隔离**——已证明的是“跨副本检索结果不稳定”这一现象，
     **不宣称波动原因已完全解决**。
- 原库与 B 的构建脚本**未改动**（本工具只读复制，评测在临时副本中进行，finally 清理）。

### 5.3 真实 API 冒烟（样例级，不代表评测）

- 结构化摘要：[evaluation/chroma_api_smoke.json](./evaluation/chroma_api_smoke.json)
  （源证据为系统 TEMP 的 `schoolrobot-bge-api-smoke.json`，未纳入仓库）。
- 环境：独立验证环境 `storage/vector_db/validation-env`（gitignored，Python 3.12、
  `chromadb 0.4.24 / sentence-transformers 3.4.1 / transformers 4.48.3 / torch 2.5.1+cpu / numpy 1.26.4 / posthog 3.25.0`），
  未改 `backend/.venv`；模型 `storage/vector_db/models/bge-large-zh-v1.5`
  （revision `79e7739b…0116`，`pytorch_model.bin` sha256 `bf84a56f…7a207f2`）；
  库为 `vectorstore/chroma` **只读副本**（229×2 集合、1024 维），原库 10 个文件 hash 前后一致，临时副本已删除；
  LLM 为 Ollama `qwen3.5:4b`。
- 结果：违纪处分种类问题 HTTP 200、8.29s，正确列出五种处分并引用 [4]（对应
  `knowledge_base/cleaned/10.大连大学学生违纪管理规定.md` 第六条）；
  域外量子问题 HTTP 200、0.15s、`sources=[]` 拒答；首次检索加载 12.20s。
- 注意：冒烟测试**显式设置 60 秒超时**，不代表默认 15 秒冷启动保证。

### 5.4 待 Codex / B 补充（占位，不写死）

1. 三次波动指标的**最终口径**与根因边界（重建次序是否唯一根因尚待隔离）；
2. B 对**持久化完整性 / 索引文件**的检查结论；
3. B 的**独立评测集**就绪后的正式复测（正式 Recall@K / MRR）；
4. 在以上完成前：**质量验收未通过、不宣称达标**。

### 5.5 复现命令（Codex 实际使用；本工具不联网、不安装）

```powershell
# 在仓库根执行；真实评测在独立验证环境，backend/.venv 未安装重依赖
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:OMP_NUM_THREADS = "4"
$env:MKL_NUM_THREADS = "4"
storage\vector_db\validation-env\Scripts\python.exe -X utf8 scripts\evaluate_retrieval.py `
  --mode chroma `
  --dataset tests/fixtures/retrieval_cases.json `
  --vector-db vectorstore/chroma `
  --model-path storage/vector_db/models/bge-large-zh-v1.5 `
  --output docs/evaluation/chroma_bge_large_zh_v15_rerun.json
# 输出请使用新的报告名（如 *_rerun.json / 带批次后缀），不要覆盖第 2/3 轮存档证据。
```

- 运行环境（Codex 实际使用）：`storage/vector_db/validation-env`（Python 3.12、
  `chromadb 0.4.24 / sentence-transformers 3.4.1 / transformers 4.48.3 / torch 2.5.1+cpu /
  numpy 1.26.4 / posthog 3.25.0`），并显式设置上述 4 个环境变量。
- 报告 `library` 段记录 `vector_db`、`content_collection`、`structure_collection`、`embedding_model`、
  `device`、`min_score`、`snippet_max_chars`、`content_weight`、`structure_weight`，便于复现。
- **版本提示**：`snippet_max_chars / content_weight / structure_weight` 是限定小修**新增**的字段；
  小修前归档的第 2/3 轮 JSON（`chroma_bge_large_zh_v15.json`、`chroma_bge_large_zh_v15_repeat.json`）
  **没有这些字段**（先于小修产出），不要误读为旧报告已含——只有小修后新跑的报告才会带上。
- 工具行为：先复制原库到临时目录再打开，finally 清理，绝不直开原库；失败不写报告。

## 6. 本工具测试与回归

```powershell
backend\.venv\Scripts\python.exe -m pytest tests\retrieval -q   # 54 passed
backend\.venv\Scripts\python.exe -m pytest tests\backend tests\api -q  # 117 passed, 1 warning（原有回归）
backend\.venv\Scripts\python.exe -m pytest tests -q             # 171 passed, 1 warning（合计）
```

| 文件 | 数量 | 关注点 |
| --- | --- | --- |
| `tests/retrieval/test_metrics.py` | 14 | 首位/后位命中、重复来源名次、无命中、负例、错误不计拒答、证据覆盖（含限定 expected_source、同一片段关键词）、top_k 有界、报告片段截断但保留完整文本 |
| `tests/retrieval/test_dataset.py` | 20 | fixture 规模与证据落地（关键词+引文）、重复 id、缺字段、未知字段、空正例证据、负例字段、坏 JSON |
| `tests/retrieval/test_cli.py` | 20 | 危险输出路径、报告脱敏、keyword 端到端、缺库/缺依赖/缺 sqlite、复制原库而非直开、临时副本清理、出错不写报告、模型路径本地相对路径按仓库根解析（异地 CWD 回归） |

全部新测试离线：不加载模型、不访问网络、不写向量库；chroma 相关用 stub / 假依赖探测。
