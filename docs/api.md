# API 说明（对齐当前实现）

当前后端实现的是学生 C 第 1 阶段：**非流式** RAG 问答。历史记录、记忆问答、SSE 流式
由 A 同学后续实现，本文不把它们写成已完成。

## POST /chat（已实现）

基础检索增强问答，一次返回完整答案。

> 前端行为：`frontend/src/api/chat.ts` 先请求 `POST /chat_with_memory`，**任何请求失败**
> （当前该接口尚未实现，返回 404）都会回落到本接口；不是只针对 404 回退。

### 请求

```http
POST /chat
Content-Type: application/json

{"message": "学生违纪处分有哪些种类？"}
```

- `message`：字符串，必填；先去掉首尾空白，再要求 1..2000 字符。
- 空白、缺字段、类型错误、超长：`422`。

### 成功响应（200）

```json
{
  "answer": "根据参考资料，纪律处分的种类分为：警告、严重警告、记过、留校察看、开除学籍。[1]",
  "sources": [
    {
      "index": 1,
      "title": "大连大学学生违纪管理规定(修订)",
      "source": "knowledge_base/cleaned/10.大连大学学生违纪管理规定.md",
      "snippet": "# 第二章 处分的种类和运用 第六条……（一）警告；（二）严重警告；（三）记过；（四）留校察看；（五）开除学籍。",
      "score": 0.216
    }
  ],
  "retrieval_mode": "keyword"
}
```

- `answer`：前端兼容字段（`frontend/types` 里只要求 `answer`）。
- `sources`：**只包含本次真正放入提示词的资料**；`index` 与答案中的 `[编号]` 对应，
  `snippet` 与提示词正文逐字一致；`source` 为仓库相对路径，不含盘符。
- `retrieval_mode`：`keyword` 或 `chroma`，便于排查检索模式。

### 未命中（200）

检索无结果时（含 keyword 的低相关门槛过滤之后）：

```json
{"answer": "参考资料未提及，请咨询学校相关部门。", "sources": [], "retrieval_mode": "keyword"}
```

这种情况**不会调用大模型**，避免编造校园政策。

### 错误响应

| 状态码 | 含义 | 触发场景 |
| --- | --- | --- |
| 422 | 请求不合法 | `message` 缺失 / 空白 / 超长 / 类型错误 |
| 503 | 检索或模型连接不可用 | 知识库目录缺失、文件均不可读、chroma 缺依赖 / 缺集合 / 向量库读取失败、连接不上 Ollama、`RETRIEVAL_MODE` 不支持 |
| 504 | 模型响应超时 | 默认 15 秒（需小于前端 20 秒） |
| 502 | 模型返回异常 | Ollama 404（模型未安装）、其他错误状态、非法 JSON、空内容 |

错误体固定为 `{"detail": "..."}`，不包含内部路径、堆栈或 Ollama 原始响应。

## GET /health（已实现）

只报告进程与配置，**不检测依赖是否真的可用**：

```json
{
  "status": "ok",
  "checks": ["process", "config"],
  "external_dependencies_checked": false,
  "retrieval_mode": "keyword",
  "model": "qwen3.5:4b",
  "rag_service_ready": true,
  "note": "仅报告进程与配置，不检测 Ollama 与向量库是否可用"
}
```

## GET /（已实现）

```json
{"message": "Campus AI Assistant backend is running"}
```

## 未实现（A 同学负责，勿按已完成联调）

- `POST /chat_with_memory`：带记忆问答。当前不存在，前端请求失败后回落到 `/chat`。
- `POST /chat` 的 SSE 流式版本：未实现。
- `GET /get_history`、`POST /clear_history`：未实现。
- `backend/app/api/knowledge.py`：知识库分类接口未实现。

另外，`docs` 早期草案里的 `/api/chat` 前缀没有采用：实际路径就是 `/chat`
（前端 `baseURL + "/chat"`）。

## 个人中心（C 前端）消费的历史 / 健康契约（历史后端仍待 A 实现）

> 本节描述 `frontend/src/api/chat.ts` 实际解析与展示的契约；`GET /get_history`、
> `POST /clear_history` **尚未实现**（当前返回 404），页面按“历史记录暂未开放”展示。
> 本节不能当作已完成联调的依据。

### GET /get_history（A 待实现）

前端兼容三种响应结构：

- `[]`（裸数组）；
- `{"items": [...]}`；
- `{"history": [...]}`（两种键同时存在时 `history` 优先，与旧实现一致）。

条目字段：

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `question` | string | 必填；类型不符时整体按格式错误处理 |
| `answer` | string | 必填；前端按纯文本渲染（保留换行，不用 v-html） |
| `id` | string \| number | 契约要求必填且唯一；缺失 / 重复不会导致渲染 key 冲突 |
| `time` | string（ISO 8601）\| number（毫秒时间戳） | 可选；**类型错误（对象 / 数组 / 布尔等）、非有限或超范围数字会抛格式错误并拒绝整批**；类型合法但无法解析的日期字符串显示“时间未知” |

- 展示 key 为 `JSON.stringify([id, index])`：仅用于列表渲染，同一响应内一定唯一；
  **顺序变化时 key 会变化**，后端应提供唯一 `id`。缺失 `id` 时按序号生成展示 id
  （如 `history-1`），不作为业务 id。
- 结构或字段类型不符合上表时，前端显示“历史数据格式异常”并给重试，**不会静默当成空历史**。

错误与前端行为：

| 情况 | 页面表现 |
| --- | --- |
| 404 / 501 | “历史记录暂未开放，当前问答暂不保存历史。” + 重试；清空禁用 |
| 其它网络 / 服务错误 | “历史记录加载失败……” + 重试；若已有旧记录则保留并标注“可能不是最新” |
| 结构 / 字段不合法 | “历史数据格式异常……” + 重试 |

### POST /clear_history（A 待实现）

- 成功契约：HTTP 2xx **且响应体没有显式失败标记**。显式失败指 `success === false`、
  `ok === false`，或 `status` 为 `error` / `failed` / `fail`（大小写不敏感）；
  出现这些标记时前端按失败处理并**保留现有记录**。
- 建议实现返回 `{"success": true}`；204 或空响应体同样视为成功。
- 404 / 501 与其它失败都会给出失败提示，不会清空界面。

### GET /health（已实现，个人中心只读展示）

- 页面仅当 `status === "ok"` 显示“在线”，否则显示“服务异常（status）/ 无法连接”；
- `retrieval_mode`：`keyword` → 关键词、`chroma` → 向量、其它 → 未知；
- `model` 作为“配置模型”展示；`rag_service_ready` **不作为模型 / 向量库可用依据**，
  页面固定注明“仅表示后端服务连接正常，不代表问答与检索的依赖均可用”；
- 健康检查失败时显示“无法连接 / 离线”，绝不显示在线；历史接口失败不影响健康结论。

## 实现约定（C 第 1 阶段）

- Ollama：`POST /api/chat`，`stream=false`，`temperature=0.1`，`think` 默认 `false`；
  只读取 `message.content`，不返回思考内容。官方文档 <https://docs.ollama.com/api/chat>。
- keyword 检索：读取 `KNOWLEDGE_BASE_DIR` 下的 md/txt，中文双字词 + 英文/数字词匹配，
  IDF 加权覆盖度排序 + `MIN_COVERAGE` 低相关门槛；是启发式相关度，不是向量检索。
- chroma 检索：只读查询 B 构建的 `school_documents_content` / `school_documents_structure`
  集合（不创建集合、不执行 add / delete / rebuild），双路按 ID 加权融合（0.6 / 0.4），
  结构路命中时从内容集合取正文；`local_files_only=True` 不下载模型，不静默回退 keyword。
  查询会通过 chromadb 打开持久化目录，可能触发底层元数据维护，联调旧库前先备份。
- `/chat` 不写历史记录，也不实现 `/chat_with_memory`。
