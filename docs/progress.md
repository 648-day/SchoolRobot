# 项目进度（学生 C · 进度入口）

> 最后更新：2026-09-30 · 分支：**xiangliang** · 阶段：**个人中心（C 前端）已完成 + 后端第 1 阶段已验收 + 检索评测（keyword 完整 + Chroma 三轮真实评测，质量验收未通过，待 B 检查）+ 新生指引草稿 / 来源登记**
>
> 本文件是 C 的进度入口；个人中心测试证据见 [personal_center_test_report.md](./personal_center_test_report.md)，
> 后端第 1 阶段证据见 [rag_test_report.md](./rag_test_report.md)，
> 检索评测（keyword + Chroma 三轮 + 稳定性探针 + API 冒烟）见
> [retrieval_evaluation.md](./retrieval_evaluation.md)、
> [evaluation/keyword_baseline.json](./evaluation/keyword_baseline.json)、
> [evaluation/chroma_bge_large_zh_v15.json](./evaluation/chroma_bge_large_zh_v15.json)、
> [evaluation/chroma_bge_large_zh_v15_repeat.json](./evaluation/chroma_bge_large_zh_v15_repeat.json)、
> [evaluation/chroma_repeatability_probe.json](./evaluation/chroma_repeatability_probe.json)、
> [evaluation/chroma_api_smoke.json](./evaluation/chroma_api_smoke.json)；
> 资料草稿见 [materials/new_student_guide_draft.md](./materials/new_student_guide_draft.md)、
> [materials/source_register.md](./materials/source_register.md)，
> 阶段计划与 A/B 边界见 [student_c_plan.md](./student_c_plan.md)，
> 接口与部署分别见 [api.md](./api.md)、[deployment.md](./deployment.md)。

## 1. 当前状态一句话

**后端 keyword / API 里程碑已验收**（Codex 真实 Ollama + 真实语料复验，后端 117 passed）；
**个人中心（/me）前端已完成**：81 项前端测试、`vue-tsc`、生产构建与目标文件 lint 全部通过，
Codex 独立浏览器验收通过（2026-09-30，真实 Vite :3333 + FastAPI :8000）。
**检索评测工具已完成并跑通真实 Chroma + BGE 链路**：`scripts/evaluate_retrieval.py` +
20 正例 / 5 负例小样本开发回归集（不是 B 的正式评测集）。
keyword 真实基线（**证据判定修复后**）Hit@5 20/20、MRR 0.925、证据覆盖率 **20/20**、负例拒绝率 4/5；
Chroma + BGE 对真实库副本完成**三轮完整 25 例**（每次全新临时副本、独立进程），
**指标跨轮波动（Hit 15–18/20、MRR 0.6625–0.72、证据 13–14/20、负例拒绝 1–2/5），
质量验收未通过**——探针已证明查询向量一致、候选跨副本变化发生在 Chroma 层，
但重建次序是否唯一根因尚未隔离，待 B 检查完整持久化 / 索引并用独立评测集复测。
**C 的资料草稿已开始**：新生指引“依据现有手册的待核验草稿”与来源登记已建立，
不写无来源的报到 / 费用 / 宿舍分配信息；课程知识点只有待收集字段模板。
**A 的历史后端 / 记忆 / SSE 升级联调，以及 C 后续的演示视频、资料补齐仍未完成**；
历史接口当前 404，页面按“未开放”展示，不宣称真实历史持久化已可用。

## 2. 分支与职责边界

| 项 | 内容 |
| --- | --- |
| 分支 | `xiangliang`（只在本分支实现；未切分支、未操作其他审查目录） |
| C 职责 | `advanced_search`、Ollama 调用、基础提示词、`POST /chat`、RAG 测试报告；**个人中心（历史记录页 / 清空历史 / 设置 / 关于我们）、演示视频、新生指引和课程知识点资料**（后三项属后续阶段） |
| 本轮范围 | 个人中心前端（页面 / 设置 / 关于 / 服务状态）与历史、健康 API 适配；历史后端 / 记忆 / SSE 属 A；知识库浏览与向量构建属 B |
| 版本控制 | 按用户 2026-09-30 授权，Codex 已提交并推送阶段代码 `75691f4` 至 `origin/xiangliang`，远程哈希核验一致。OpenCode 负责实现，Codex 负责审查与提交；未创建 PR、未合并 main、未删除文件 |

## 3. 第 1 阶段目标与验收（keyword / API 里程碑已验收）

| 目标 | 验收标准 | 状态 |
| --- | --- | --- |
| 配置 | `.env` 加载、环境变量优先、路径不依赖 CWD、默认 15s 超时、CORS 明确来源 | ✅ 代码完成 |
| `POST /chat` | trim 后 1..2000 字符、422 边界、响应含 `answer`（前端兼容）/`sources`/`retrieval_mode` | ✅ 代码完成 |
| 无命中行为 | “参考资料未提及，请咨询学校相关部门。”且不调用模型 | ✅ 代码完成 |
| 提示词 | 只依资料、资料当数据不当指令、不假称官方、不用内置知识答校园政策 | ✅ 代码完成 |
| Ollama | `/api/chat` + `stream:false` + `temperature:0.1` + `think` 默认 false；503/504/502 映射不泄密 | ✅ 真实 API 验收 |
| keyword 检索 | 条款/列表分段、IDF 覆盖度排序、低相关门槛、零命中拒答、来源仓库相对 | ✅ 真实 API 验收 |
| chroma 检索 | 只读查询 B 双集合、双路按 ID 加权、structure-only 取正文、缺依赖/集合 503 | ✅ 代码 + 假 embedding 冒烟；真实 BGE + 向量库已由 Codex 评测（第 7.4 节，质量验收未通过待 B） |
| 测试 | `tests/backend tests/api` 全绿、不访问真实 Ollama、不写向量库 | ✅ 117 passed |
| 文档 | `api / architecture / deployment / progress / student_c_plan / rag_test_report` 与实现一致 | ✅ 已更新 |

> 里程碑结论：**keyword 模式 / API 样例验收通过**（Codex，见第 7 节）；
> 真实 Chroma + BGE 链路已在独立环境冒烟跑通并完成三轮评测（指标波动、质量验收未通过，
> 见第 7.4 节），不影响本里程碑结论。

## 4. 个人中心阶段目标与验收（2026-09-30，C 前端）

| 目标 | 验收标准 | 状态 |
| --- | --- | --- |
| 历史区状态 | 加载 / 成功空 / 有记录 / 404·501 未开放 / 网络·服务错误 / 格式错误分开；失败不显示成空历史 | ✅ 代码 + 测试 |
| 历史适配 | `[] / {items} / {history}` 兼容；question / answer / id / time 类型校验；错误结构拒绝 | ✅ 代码 + 测试 |
| 展示 key | `JSON.stringify([id, index])`，重复 / 缺失 / `#` 后缀 id 均不冲突；契约写入 api.md | ✅ 代码 + 测试 |
| 清空 | 先确认、取消零请求、失败保留记录、成功才清空；确认锁、并发与卸载保护 | ✅ 代码 + 测试 |
| 刷新竞态 | 请求序号保护（旧响应不覆盖新结果）；刷新中 / stale 时清空禁用；清空 / 确认中刷新禁用 | ✅ 代码 + 测试 |
| 显示设置 | “显示记录时间”“默认展开回答”；专属 key `mobvue-me-settings-key`；损坏 / 写失败 / 禁用降级 | ✅ 代码 + 测试 |
| 关于我们 | 用途、现阶段能力（资料缺失时提示咨询学校相关部门）、仅供参考与以最新通知为准 | ✅ 代码 + 测试 |
| 服务状态 | 真实 `/health` 连接状态 + 检索模式（关键词 / 向量 / 未知）；失败不显示在线 | ✅ 代码 + 测试 + 浏览器 |
| 样式 | 显式导入 Vant 组件时同步显式导入样式，避免浏览器无样式 | ✅ 构建 CSS 核验 + 浏览器验收 |
| 测试 | `vitest` / `vue-tsc` / `build` / 目标文件 lint | ✅ 81 passed；详见个人中心测试报告 |
| 浏览器验收 | 320 / 375 无横向溢出、样式与交互正常 | ✅ Codex（2026-09-30，Edge headless） |
| 真实历史联调 | A 的 `/get_history`、`/clear_history` 就绪后联调 | ⏳ 待 A（当前 404 → 页面“未开放”） |

> 说明：个人中心**不依赖 Chroma / BGE**；历史区在 A 的接口就绪前按“未开放”展示，
> 浏览器验收中的隔离拦截用例是 mock 响应，不代表真实历史后端可用。

## 5. 检索评测工具阶段（C，2026-09-30）

目标：在不动 B 向量构建、不改关键词检索策略的前提下，把 C 的检索评测做成**可复现、可审查**的工具，
为真实 Chroma + BGE 验证做准备。详细命令、数据集与结果见 [retrieval_evaluation.md](./retrieval_evaluation.md)，
机器可读报告见 `docs/evaluation/keyword_baseline.json`。

| 目标 | 验收标准 | 状态 |
| --- | --- | --- |
| 评测 CLI | `scripts/evaluate_retrieval.py`：`--mode/--dataset/--output/--top-k/--model-path/--vector-db` 等必要参数，复用 `Settings` 默认；真实调用现有 `KeywordRetriever/ChromaRetriever`；可导入测试，`main()` 仅 CLI | ✅ 代码 + 测试 |
| 离线与安全 | 默认离线、不下载模型、不调用 LLM、不改配置；chroma 先复制指定库到临时目录再打开、finally 清理、禁止直开原库与 create/add/rebuild | ✅ 代码 + 测试；真实库已跑（复制副本、不直开，见 7.4） |
| 输出安全 | 拒绝覆盖评测集 / 知识库 / 原向量库 / `backend` / `.git`；用户指定目录可创建；报告不含本机绝对路径；失败退出非 0 且不写报告 | ✅ 代码 + 测试 |
| 数据集 | ≥12 正例、跨 ≥6 文档、各含 query/id/expected_source/evidence；≥4 负例；证据逐条与原文核对 | ✅ 20 正例（10 篇）+ 5 负例；测试核对 |
| 每例结果 | top-k 来源、名次、分数、可审查 snippet、命中目标文档/证据、耗时 | ✅ 报告字段 |
| 汇总指标 | 文档级 Hit@K、MRR、证据覆盖率、负例拒绝率；分母与定义明确；重复 source 按首次名次；错误不计拒答成功；不冒充完整 Recall@K | ✅ 定义写进报告 |
| keyword 完整开发集 | 真实运行并产出报告 | ✅ Hit@5 20/20、MRR 0.925、证据覆盖 20/20、负例拒绝 4/5（证据判定修复后重跑） |
| 回归 | 现有 117 项 + `tests/retrieval` | ✅ 117 + 54 = 171 passed |
| Chroma 真实库 + BGE | 对真实库副本运行并如实记录；不宣称质量达标 | 🟡 三轮完整 25 例已跑（指标波动：Hit 15–18/20），**质量验收未通过**，待 Codex/B 补充 |
| 稳定性探针 | 查询向量 / 候选跨副本变化可审查 | ✅ `evaluation/chroma_repeatability_probe.json`（已脱敏） |
| 边界遵守 | 未改 frontend、`knowledge_base`、`vectorstore`、B 的 scripts、检索器 / 阈值 / 库 | ✅（见第 7 节证据；限定脚本小修除外） |

已知限制（本轮如实声明，不夸大）：

- 小样本开发回归集：20 正例 / 5 负例、10 篇文档，**不是 B 的正式评测集，不能泛化**，也不命名为完整
  `Recall@K`；keyword 分数是启发式相关度。
- 负例 `neg-postgraduate-line`（复试分数线）被弱相关片段命中（0.1836），负例拒绝率为 4/5，如实入报告，未调阈值掩盖。
- **历史更正**：旧报告“证据覆盖 19/20、`choose-course-drop` 被 500 字窗口截断未覆盖”系评测工具
  对比报告 200 字截短片段的 bug；修复后证据覆盖率 20/20，**检索器窗口不是原因**（详见
  [retrieval_evaluation.md](./retrieval_evaluation.md) 第 3.1 节）。
- 真实 Chroma + BGE 已跑三轮完整评测（每次全新临时副本、独立进程），指标波动且**质量验收未通过**；
  探针证明查询向量一致、候选变化发生在 Chroma 层，但根因边界与最终指标待 Codex/B 补充，不写死结论。
- keyword 索引在首次检索时构建并缓存在进程内；评测每次新建进程，不受后端服务缓存影响。

## 6. 已完成 / 进行中 / 待办

### 已完成（代码 + 测试）

- 后端第 1 阶段：`backend/app/core/config.py`、`backend/app/schemas/chat.py`、
  `backend/app/prompts/rag_base.txt`、`backend/app/services/{retriever, rag_service, llm_service}.py`、
  `backend/app/api/chat.py`、`backend/app/main.py`，测试 `tests/backend/*`、`tests/api/*`（117 项）
- 后端依赖与文档：`backend/requirements-chroma.txt`、`.env.example`、`backend/README.md`、
  `docs/api.md`、`architecture.md`、`deployment.md`、`student_c_plan.md`、`rag_test_report.md`
- 真实 API 样例验收（keyword 模式，Codex）与 chroma adapter 外部假 embedding 冒烟
- **个人中心（C 前端）**：
  - `frontend/src/pages/me/index.vue`（历史区状态机 / 清空 / 服务状态 / 汇总卡片）
  - `frontend/src/pages/me/components/{HistoryItemCard, SettingsPanel, AboutPanel, ServiceStatusPanel}.vue`
  - `frontend/src/pages/me/composables/useProfileSettings.ts`、`frontend/src/pages/me/utils/display.ts`、
    `frontend/src/pages/me/types.ts`
  - `frontend/src/api/chat.ts`（历史规范化 / 错误分类 / 清空成功契约 / `getHealth`；`chatWithMemory` 回落行为不变）、
    `frontend/src/types/chat.ts`（兼容性补类型）
  - 测试 `frontend/tests/api/chat.test.ts`、`frontend/tests/pages/me/*`（新增 70 项，合计 81 passed）
  - Codex 浏览器验收（真实 Vite :3333 + FastAPI :8000，Edge headless）
- **检索评测工具（C，本阶段）**：
  - `scripts/evaluate_retrieval.py`（真实调用检索器；默认离线；chroma 复制临时副本；报告脱敏；失败非 0 不写报告）
  - `tests/fixtures/retrieval_cases.json`（20 正例 / 10 篇文档 + 5 负例，证据与原文逐条核对）
  - `tests/retrieval/{conftest.py,test_metrics.py,test_dataset.py,test_cli.py}`（54 项，全部离线）
  - `docs/retrieval_evaluation.md`、`docs/evaluation/keyword_baseline.json`（keyword 真实基线，
    证据判定修复后 20/20）、`docs/evaluation/chroma_bge_large_zh_v15.json`
    与 `chroma_bge_large_zh_v15_repeat.json`（Chroma 真实评测第 2/3 轮）、
    `docs/evaluation/chroma_repeatability_probe.json`（稳定性探针，已脱敏）、
    `docs/evaluation/chroma_api_smoke.json`（真实 API 冒烟结构化摘要）
  - 限定小修（经授权）：报告限制语改为通用质量/小样本口径；`--model-path` 本地相对路径按仓库根解析
    （异地 CWD 回归测试）；Chroma 报告 `library` 记录 `snippet_max_chars / content_weight / structure_weight`
- **资料草稿（C，本阶段起步）**：
  - `docs/materials/new_student_guide_draft.md`（依据现有手册的待核验草稿，8 条问答，逐条标注手册、条款与版本）
  - `docs/materials/source_register.md`（来源、已核验条款、年份、待核验项与下一步；课程知识点仅字段模板）

### 进行中 / 等待外部条件

- 与 A 的历史后端联调（当前 `/get_history`、`/clear_history` 返回 404；页面已完成并按未开放展示）
- 真实 Chroma + BGE：三轮评测已跑（质量验收未通过），等 Codex/B 给出最终指标口径、
  持久化 / 索引检查结论与 B 的正式评测集复测（C 侧不重跑重模型评测）

### 待办（C 的后续职责，未做不宣称）

- **演示视频**：拍摄与剪辑
- **资料**：新生指引草稿等待 2026 入学通知等官方来源核验；课程知识点按字段模板收集；
  补齐后按 B 的流程入库（未核验内容不入 `knowledge_base/cleaned`）
- B 的正式评测集就绪后用本工具复测（正式 Recall@K / MRR；当前只有 C 的小样本开发回归）

## 7. 真实测试证据（截至最后更新）

### 7.1 后端第 1 阶段（保留）

```powershell
backend\.venv\Scripts\python.exe -m pytest tests/backend tests/api -q
# 本地运行：      117 passed, 1 warning in 4.62s
# Codex 独立复验：117 passed, 1 warning in 4.38s；本轮再次复验：117 passed in 9.30s
# 仓库核验：      git diff --check 退出 0；git diff --cached 为空
# 用户修改的 frontend/types/auto/components.d.ts 未被改动
#   sha1 = 2b124f3924ca4659c8567b206d294f6f5c9a786e
```

- 分文件（合计 117）：config 10、schemas 7、llm_service 16、keyword_retriever 22、
  chroma_retriever 22、rag_service 13、chat_api 27。
- 常规测试全部离线：Ollama 用 `httpx.MockTransport`；chroma 用假客户端 / 假嵌入
  （本环境未装 `chromadb`、`sentence-transformers`）；不写向量库。
- **keyword 模式真实 API 样例验收（Codex）：通过**
  - 处分种类问题：HTTP 200、7.70s，正确列出警告 / 严重警告 / 记过 / 留校察看 / 开除学籍，
    引用 [4]，对应 `sources[3]` 第六条原文。
  - “量子纠缠如何实现超光速通信？”：HTTP 200、约 0s、`sources=[]`、明确拒答。
  - “图书馆开放时间是什么时候？”：HTTP 200、`sources=[]`、拒答（与短查询“图书馆开放时间”
    的弱命中区别保留）。
- **chroma adapter 外部冒烟（不计入 117）**：外部独立运行时 + 真实 `chromadb==0.4.24` +
  临时数据库 + 固定 3 维假 embedding；每集合 3 条、`top_k=1`、权重 content 0.1 / structure 0.9，
  仅结构路候选 c 命中 → 从 content 取回真实正文、score 0.9、集合数量保持 3/3；
  未用真实 BGE、未动原库；posthog 遥测兼容警告不影响查询断言。
- 历史保留：第一版真实 `/chat` 约 2.66s 但**因检索漏证据错误拒答**；修复后才有本次验收通过。
- 真实语料只读抽查（覆盖度 / top5）见 [rag_test_report.md](./rag_test_report.md) 第 3 节。
- **未运行**：真实 BGE + 真实向量库端到端、浏览器端 20s 超时计时。
- **索引刷新**：keyword 索引在首次检索时构建并缓存在进程内，新增 / 修改资料后需**重启后端服务**刷新。

### 7.2 个人中心前端（2026-09-30）

```powershell
cd frontend
pnpm exec vitest run        # 6 files, 81 passed（本地 81；Codex 独立复验 81 passed, 9.08s）
pnpm exec vue-tsc --noEmit  # 退出 0（Codex 复验退出 0）
pnpm build                  # 成功，PWA precache 81 entries（Codex 独立构建 19.25s，precache 81）
pnpm exec eslint <本轮文件> # 退出 0（只针对本轮新增 / 修改文件）
```

- 测试分文件：`tests/api/chat.test.ts` 21、`tests/pages/me/page.test.ts` 36、
  `tests/pages/me/settings.test.ts` 8、`tests/pages/me/display.test.ts` 5，
  加原有 demo 2 + validate 9 = 81。
- 构建 CSS 核验：`dist` 中包含 `.van-button / .van-switch / .van-dialog / .van-toast /
  .van-space / .van-empty / .van-loading` 等样式（显式组件导入 + 显式样式导入）。
- **Codex 浏览器验收（Edge headless，真实 Vite :3333 + FastAPI :8000）：通过**
  - 真实 `/get_history` 404 → “历史记录暂未开放，当前问答暂不保存历史。”且清空禁用；
  - 真实 `/health` → 关键词 / 在线 + “仅表示后端服务连接正常，不代表问答与检索的依赖均可用”；
  - 设置关闭显示时间后重载仍保留；关于我们展开出现“以学校最新通知和老师答复为准”；
  - 320 / 375 宽 `document.scrollWidth === viewport`，无横向溢出；switch 样式正常；
    刷新 / 清空横排恢复；真实 Vant dialog `position: fixed`；页面 `pageerror` 为空。
  - 浏览器内隔离拦截（**mock 响应，不代表真实历史后端**）：health 503 → 无法连接 / 离线；
    历史有记录可展开长回答；取消清空零 POST；`{success:false}` 保留记录并 toast 失败；
    `{success:true}` 显示空历史。截图在系统 TEMP，不纳入仓库。
- 生成声明：`components.d.ts` 最终恢复为用户基线（含 VanCellGroup / VanForm 等），
  `git hash-object` = `2b124f3924ca4659c8567b206d294f6f5c9a786e`；
  `auto-imports.d.ts` 保持基线 `6abdace96058f5fdf7a836649e18727102a4f052`。
- 详细证据与 mock / 真实边界见 [personal_center_test_report.md](./personal_center_test_report.md)。

### 7.3 检索评测工具与 keyword 基线（2026-09-30，C）

```powershell
backend\.venv\Scripts\python.exe -m pytest tests\retrieval -q
# 54 passed in 1.62s（离线：不加载模型、不访问网络、不写向量库）
backend\.venv\Scripts\python.exe -m pytest tests\backend tests\api -q
# 117 passed, 1 warning in 5.14s（原有回归未受影响）
backend\.venv\Scripts\python.exe -m pytest tests -q
# 171 passed, 1 warning in 6.26s（117 + 54）

backend\.venv\Scripts\python.exe scripts\evaluate_retrieval.py --mode keyword `
  --dataset tests\fixtures\retrieval_cases.json --output docs\evaluation\keyword_baseline.json
# 正例 20 / 负例 5；文档级 Hit@5 = 20/20 = 1.0；MRR = 0.925；
# 证据覆盖率 = 20/20 = 1.0；负例拒绝率 = 4/5 = 0.8；退出码 0
# 报告 generated_at = 2026-09-30T19:42:47；数据集 sha256 = 96da220b…b5d（与 fixture 现文件一致）
```

- 小样本开发回归集：20 正例覆盖 10 篇文档，证据（关键词 + 引文）由
  `tests/retrieval/test_dataset.py` 逐条与 `knowledge_base/cleaned` 原文核对；
  **不是 B 的正式评测集 / 独立测试集，不能泛化**。
- **证据判定修复**：旧口径误用报告 200 字截短片段、未限定 expected_source（曾得证据覆盖 19/20）；
  修复后按检索器真实返回文本 + expected_source 判定，证据覆盖率 20/20。
  **旧“`choose-course-drop` 被 500 字窗口截断”结论不成立**，检索器窗口不是原因（历史记录保留并更正）。
- 未达成处如实记录：`neg-postgraduate-line` 有一例弱相关命中（负例拒绝率 0.8）；**未调阈值掩盖**。
- chroma 路径行为已有测试：复制原库到临时目录再打开、finally 清理、缺依赖/缺 sqlite 失败、
  案例出错不写报告；真实 `vectorstore/chroma` + BGE 由 Codex 在独立验证环境运行，见 7.4。
- 命令、指标定义（分母 / 重复 source / 错误处理）与逐例结果见
  [retrieval_evaluation.md](./retrieval_evaluation.md)；报告为 `docs/evaluation/keyword_baseline.json`、
  Chroma 报告见 `docs/evaluation/` 下同名 JSON。

### 7.4 真实 Chroma + BGE 评测与稳定性观察（2026-09-30，Codex）

```text
环境：storage/vector_db/validation-env（gitignored 独立验证环境；backend/.venv 未装重依赖）
      chromadb 0.4.24 / sentence-transformers 3.4.1 / transformers 4.48.3 /
      torch 2.5.1+cpu / numpy 1.26.4 / posthog 3.25.0（Python 3.12）
模型：storage/vector_db/models/bge-large-zh-v1.5
      revision 79e7739b6ab944e86d6171e44d24c997fc1e0116
      pytorch_model.bin sha256 bf84a56fb045c24e090495195584a3922c3e4204107f0bba8b79c11f67a207f2
库：  vectorstore/chroma 只读复制（229×2 集合、1024 维）；原库只复制不打开、hash 前后一致、临时副本已删除
API 冒烟：Ollama qwen3.5:4b；违纪处分五种类型回答正确并引用 [4]（HTTP 200、8.29s）；
      域外量子问题 HTTP 200、0.15s 拒答 sources=[]；首次检索加载 12.20s；
      测试显式 60 秒超时（不代表默认 15 秒冷启动保证）

三次完整 25 例（每次全新临时副本、独立进程；不挑最好值）：
  第 1 轮：Hit 15/20、MRR 0.6625、证据 14/20、负例拒绝 2/5（原始 JSON 已被复跑覆盖，不伪造恢复）
  第 2 轮：Hit 17/20、MRR 0.72  、证据 14/20、负例拒绝 1/5（chroma_bge_large_zh_v15.json）
  第 3 轮：Hit 18/20、MRR 0.6933、证据 13/20、负例拒绝 1/5（chroma_bge_large_zh_v15_repeat.json）
  观察区间：Hit 75–90%、证据 65–70%、负例拒绝 20–40%；仅三次观察，不是置信区间
```

- 探针（`docs/evaluation/chroma_repeatability_probe.json`，已脱敏）：4 个查询的 float32 查询向量 SHA256
  三次独立进程完全一致、同进程重复查询结果一致；**跨副本候选 ID / 排名变化 → 波动在 Chroma 层**。
  原库两个 HNSW 目录缺少 `index_metadata.pickle`（chromadb 0.4.24 以该文件判断索引存在，
  缺失时按新索引处理并重放记录）；结构路重复文本/同分多，加权融合放大候选变化。
  **重建次序是否唯一根因尚未隔离，不宣称已解决**；原库与 B 构建脚本未改。
- 结论口径：**链路可用；现有库跨进程检索不稳定，质量验收未通过；待 B 检查完整持久化 / 索引
  与独立评测集复测**。最终指标待 Codex/B 补充，本阶段不写死、不宣称达标。
- 冒烟结构化摘要：`docs/evaluation/chroma_api_smoke.json`（源证据为系统 TEMP，未纳入仓库）。

## 8. 审查问题解决状态

### 第一轮 7 项审查（后端）

| # | 问题 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | 违纪处分种类漏证据；分段/排序需改进 | ✅ | 修复标题粘连 bug + IDF 覆盖度排序；fixture 与真实语料双回归；真实 top5 含五种处分 |
| 2 | 量子纠缠低覆盖片段不应送模型；加通用门槛 | ✅ | `MIN_COVERAGE=0.2`；真实语料覆盖度 0.084 拒答，测试 4 项 |
| 3 | structure-only 分数与默认阈值 | ✅ | 复核确认分支保留 `hit["score"]`（`retriever.py`）；新增默认阈值 0.35 回归，验证取回 content 正文 |
| 4 | 向量库故障被当空库；构造/嵌入异常未映射 503 | ✅ | `_collection_count` 抛 503；PersistentClient/factory/encode 异常统一 503；API 测试不泄密 |
| 5 | 上下文预算漏算分隔符；末尾命中被截掉 | ✅ | 预算含分隔符 + header 收缩 + 空 context 拒答；片段按命中窗口截取；4 项新测试 |
| 6 | chroma 惰性初始化并发重复加载 | ✅ | 双检锁；8 线程并发只初始化一次（测试） |
| 7 | 文档/注释误写“仅 404 回退” | ✅ | 改为“任何失败都回落”；未改 frontend |

### 第二轮 / 收尾核验的小修（后端）

- 文档职责修正：C 负责个人中心（历史记录页 / 清空历史 / 设置 / 关于我们）、演示视频、
  新生指引与课程知识点资料；A 负责聊天页（已在仓库）与历史后端、记忆 / SSE；B 负责知识库浏览与向量构建。
- 索引刷新说明：keyword 索引首次检索后缓存，资料变更需重启服务。
- 依赖版本核查：`fastapi 0.141.1 / starlette 1.7.0 / httpx 0.28.1 / pydantic 2.13.5 /
  pytest 9.1.1 / python-dotenv 1.2.3 / uvicorn 0.54.0`。
- `_fetch_content` 区分“库故障 → 503”与“缺失 ID → 跳过”，补 2 项测试。
- 新增 `backend/requirements-chroma.txt`（chromadb==0.4.24 等，不安装重依赖）；
  部署与 README 的测试步骤改用 `requirements-dev.txt`，复制 `.env` 前检查是否存在。
- 另修正两个失败用例：`make_retriever` 的 `min_score` 重复传参、`advanced_search` 阈值断言。

### 第三轮：Codex 个人中心阶段审查（2026-09-30）

| # | 问题 | 状态 | 修复与证据 |
| --- | --- | --- | --- |
| 1 | 历史展示 key 按 `#n` 去重仍可能碰撞（如 `["a","a","a#2"]`） | ✅ | key 改为 `JSON.stringify([id, index])`；补重复 / 后缀 / 缺失 / 撞名用例；api.md 说明顺序变化时 key 变化 |
| 2 | 清空把任何 2xx 当成功，服务拒绝删除却清空 UI | ✅ | `isClearHistorySuccess`：拒绝 `{success:false}`、`{ok:false}`、`{status:error/failed/fail}`；契约写入 api.md |
| 3 | 确认等待可重复弹窗；确认 / 清空请求在卸载后仍可能发请求或提示 | ✅ | 独立 `confirming` 锁；确认后与响应返回前检查 `disposed`；补 deferred 确认连点、卸载后确认、卸载后响应测试 |
| 4 | 有旧记录时刷新不设 loading，刷新中 / stale 仍可清空；未开放 stale 可清空 | ✅ | 独立 `refreshing`；`canClear` 要求非刷新 / 非 stale / 非确认 / 非清空；清空与确认期间刷新禁用；刷新中显示“正在刷新历史记录…” |
| 5 | 健康检查无最新响应保护 | ✅ | `healthSeq` 序号保护 + 连点测试 |
| 6 | 设置开关无可访问名称 | ✅ | 两个 VanSwitch 增加 `aria-label`，测试断言 |
| 7 | 显式导入 Vant 组件后浏览器样式缺失（首轮浏览器验收发现） | ✅ | 各组件显式导入 `vant/es/*/style/index`；构建 CSS 核验 + 浏览器复验通过 |
| 8 | 关于我们“不会编造”属过度保证 | ✅ | 改为“缺少相关依据时提示咨询学校相关部门”；不硬编码“历史未开放”，以历史区实际状态为准 |
| 9 | 生成声明被反复改写（删除原条目） | ✅ | 最终恢复用户基线：`components.d.ts` hash = `2b124f3924ca4659c8567b206d294f6f5c9a786e`；`auto-imports.d.ts` 保持基线 |

## 9. 时间顺序日志（保留历史，不抹去）

| 轮次 | 事件 | 当时结果 |
| --- | --- | --- |
| 第 1 轮 | 完成后端第 1 阶段初版（配置 / `/chat` / Ollama / keyword 检索 / 提示词 / 测试 / 文档） | `92 passed, 2 failed`（`make_retriever` 重复 kwarg；`advanced_search` 阈值断言错误） |
| 第 2 轮 | Codex 真实模型复验 | 冷启动曾 60s 超时；预热后约 1.6s；直接传 1800 字真实手册“处分种类”约 2.3s；**第一版真实 `/chat` 约 2.66s 但因检索漏证据错误拒答**（不算 E2E 成功） |
| 第 3 轮 | 处理 7 项审查：分段 bug、IDF 覆盖度门槛、structure-only 默认阈值回归、故障 503、预算 / 片段、并发锁、措辞；修正 2 个失败用例 | `115 passed, 1 warning`；真实语料离线回归确认 top5 含五种处分、量子问题拒答 |
| 第 4 轮 | 新增本进度文档；与测试报告对齐；不新增代码功能 | `115 passed, 1 warning in 4.50s` |
| 第 5 轮 | Codex 二次核验；修正文档职责、索引缓存说明、依赖版本号 | `115 passed`（Codex 4.42s，git diff --check 通过） |
| 第 6 轮 | Codex 验收证据同步 + 小修：`_fetch_content` 故障映射 503、`requirements-chroma.txt` 固定版本、部署 / README 测试步骤 | `117 passed`；keyword/API 里程碑通过；chroma 假 embedding 外部冒烟通过 |
| 第 7 轮（收尾） | Codex 独立复验 | 后端 `117 passed, 1 warning, 4.38s`；前端 `vitest` 11 passed、`vue-tsc` 退出 0；`git diff --check` 0、`git diff --cached` 空；`components.d.ts` 哈希未变 → **keyword / API 里程碑已验收** |
| 第 8 轮 | 个人中心前端第 1 版（页面 / 组件 / composable / API 适配 / 测试 / 文档） | 前端 `vitest` 75 passed（含新增 64 项）；`vue-tsc`、`build` 通过 |
| 第 9 轮 | Codex 阶段审查：key 碰撞、清空成功契约、确认锁 / 竞态、刷新 pending、健康序号、aria-label、About 措辞、生成声明 | 逐项修复；新增确认锁 / 卸载 / 禁用矩阵 / 健康连点等测试 |
| 第 10 轮 | 浏览器首轮验收发现显式导入后 Vant 样式缺失 | 各组件显式导入 Vant 样式；构建 CSS 核验；前端 81 passed |
| 第 11 轮 | Codex 独立复验 + 浏览器验收 + About 措辞再修 + 生成声明还原 | `vitest` 81 passed、`vue-tsc` 退出 0、`vite build` 19.25s（precache 81）、目标文件 eslint 0；浏览器验收通过；`components.d.ts` 恢复用户基线哈希 |
| 第 12 轮 | 检索评测工具：`scripts/evaluate_retrieval.py`、`tests/fixtures/retrieval_cases.json`（20 正例 / 10 篇 + 5 负例）、`tests/retrieval/*`、`docs/retrieval_evaluation.md`、keyword 基线报告 | `tests/retrieval` 41 passed；`tests/backend tests/api` 117 passed；合计 158 passed；keyword 真实跑完：Hit@5 20/20、MRR 0.925、证据覆盖 19/20、负例拒绝 4/5（当时报告 1 例证据窗口未覆盖）——**后经核查该证据未覆盖系评测工具 200 字截短 bug，见第 13 轮更正**；Chroma 当时待 Codex 验证 |
| 第 13 轮 | 证据判定修复（真实返回文本 + expected_source）与 keyword 重跑；真实 Chroma API 冒烟（Ollama `qwen3.5:4b`） | keyword 证据覆盖 **20/20**（旧“500 字窗口截断”结论更正）；处分种类问题引用 [4]、量子问题拒答；首次检索加载 12.20s；原库 10 文件 hash 前后一致、临时副本已删 |
| 第 14 轮 | Chroma + BGE 真实评测三轮（每次全新临时副本 + 独立进程）、稳定性探针、限定脚本小修（报告限制语、`--model-path` 仓库根解析、library 复现字段） | 三轮不择优：Hit 15→17→18 / 20、MRR 0.6625→0.72→0.6933、证据 14→14→13 / 20、负例 2→1→1 / 5；探针证明查询向量一致、候选变化在 Chroma 层，根因未完全隔离；**质量验收未通过**，待 B 检查持久化/索引与正式评测集；测试 54 + 117 = **171 passed** |
| 第 15 轮 | 新生指引待核验草稿与来源登记（8 条问答，逐条手册/条款/版本）；文档同步（progress / retrieval_evaluation / rag_test_report / tests README / student_c_plan） | 草稿不写报到/费用/宿舍分配等无来源信息；课程知识点仅字段模板；本地文档链接与条款核验通过 |

## 10. 阻塞

1. **现有 Chroma 库跨进程检索不稳定**：真实 Chroma + BGE 链路已在独立验证环境跑通（三轮完整 25 例），
   但指标跨轮波动、**质量验收未通过**；探针已把变化定位在 Chroma 层，重建次序是否唯一根因尚未隔离；
   待 B 检查完整持久化 / 索引，并用正式评测集复测。未完成前不宣称检索质量达标。
   （`backend/.venv` 仍未安装 chromadb / sentence-transformers，常规测试仍用假依赖。）
2. **A 的历史接口未就绪**：`/get_history`、`/clear_history` 当前 404，真实历史展示与真实清空尚不可联调；个人中心页面已完成并按“未开放”展示，不阻塞本阶段验收。
3. **评测数据与正式指标**：C 已有 20 正例 / 5 负例的小样本开发回归（`tests/fixtures/retrieval_cases.json`，
   已跑 keyword 基线与 Chroma 三轮观察）；**B 的正式评测集仍缺失**，正式 Recall@K / MRR 尚不能出，不得用开发集冒充。
4. **资料缺口**：新生指引草稿与来源登记已建立，但**2026 入学通知尚无可靠来源**（报到 / 费用 / 宿舍分配等不能写）；
   课程知识点缺专业与课程名（仅有待收集字段模板）；图书馆 / 后勤资料归属与来源待确认，只列待补、不编造。

## 11. 下一步

1. **阶段代码已交付**：[75691f4](https://github.com/648-day/SchoolRobot/commit/75691f45ca694874d7cda66f89b2999ea9a53bd3)
   已于 2026-09-30 推送至 `xiangliang`，`git ls-remote` 核验通过。用户原有的
   `frontend/types/auto/components.d.ts` 改动原样保留在工作区，未纳入提交。
2. **A 接口联调（历史 / 记忆 / SSE）**：A 交付后联调历史数据展示与真实清空；个人中心**不依赖 BGE**。
3. **Chroma / 向量检索（结论待补）**：真实链路已在独立验证环境跑通（三轮评测 + 探针 + API 冒烟），
   但质量验收未通过；等 Codex/B 给出最终指标口径、持久化 / 索引检查结论，并在 B 的正式评测集就绪后复测。
   C 侧不重跑重模型评测；复现命令与报告字段见 [retrieval_evaluation.md](./retrieval_evaluation.md) 第 5 节。
4. **资料补齐**：新生指引草稿（[materials/new_student_guide_draft.md](./materials/new_student_guide_draft.md)）
   等 2026 入学通知等官方来源后核验回填；课程知识点按
   [materials/source_register.md](./materials/source_register.md) 模板向学院 / 教务处收集，不编造；
   补齐后按 B 的流程入库。
5. **演示视频**：按后续阶段推进。
6. 每轮更新本文件第 7、9 节，保持与 [personal_center_test_report.md](./personal_center_test_report.md)、
   [rag_test_report.md](./rag_test_report.md)、[retrieval_evaluation.md](./retrieval_evaluation.md) 一致。

## 12. Codex 阶段验收（2026-09-30）

- **独立复验通过**：`pytest tests -q` = **171 passed, 1 warning in 7.01s**；
  原向量库 10 个文件 SHA256 与阶段前完全相同；`docs/evaluation/` 5 个 JSON 可解析且无 Windows 盘符路径；
  临时评测副本无残留；`frontend/types/auto/components.d.ts` 用户基线未变。
- **验收结论**：检索评测工具与资料草稿（新生指引待核验草稿 + 来源登记）**通过**；
  **向量检索质量未通过**（现有库跨进程检索不稳定）。
- **列 B 待办**：检查完整持久化 / 索引，并用 B 的正式评测集复测；在完成前不宣称检索质量达标。
- **提交状态**：Codex 已提交并推送本阶段交付 [eb8f162](https://github.com/648-day/SchoolRobot/commit/eb8f1623e5a381bbb87680f2cbd1d40c0d109ee6) 至 `origin/xiangliang`，远程哈希核验一致；OpenCode 未执行提交。用户原有 `frontend/types/auto/components.d.ts` 改动保留且未提交，未创建 PR、未合并 main。
