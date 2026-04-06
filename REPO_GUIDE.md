# REPO_GUIDE

这个文件说明当前仓库里每个主要目录是做什么的，以及你们应该把东西放到哪里。

---

## 1. 根目录说明

### `frontend/`
前端项目目录，当前使用移动端网页模板改造。

现在前端核心页面已经按下面 3 个模块来拆：

- **首页 `pages/home/`**
  - 展示校园资讯、通知流、须知类内容
  - 适合放“新生须知、选课提醒、图书馆规则、保研政策摘要”等卡片

- **对话页 `pages/chat/`**
  - 单独的智能问答页
  - 调用 `/chat_with_memory` 或 `/chat`
  - 后续可以继续加流式输出、来源标注、问题推荐

- **我的页 `pages/me/`**
  - 展示历史记录
  - 清空历史
  - 预留设置、关于我们、演示说明入口

除了页面本身，前端里还建议这样分：

- `src/api/`：前端请求后端接口
- `src/types/`：类型定义
- `src/mock/`：前期没有后端时的本地模拟数据
- `src/router/`：路由配置
- `src/components/`：可复用组件
- `src/styles/`：全局样式
- `src/utils/`：工具函数

---

### `backend/`
后端项目目录，当前按 FastAPI 组织。

建议职责如下：

- `app/main.py`
  - 后端启动入口

- `app/api/`
  - 放接口路由
  - `chat.py`：聊天接口
  - `history.py`：历史记录接口
  - `knowledge.py`：知识库接口

- `app/services/`
  - 放业务逻辑
  - `rag_service.py`：RAG 主流程
  - `retriever.py`：向量检索
  - `llm_service.py`：模型调用
  - `history_service.py`：历史记录读写

- `app/prompts/`
  - 放提示词模板
  - 建议把“校园官方口径、来源标注、禁止编造”等规则统一写在这里

- `app/schemas/`
  - 放请求体和响应体定义

- `app/core/`
  - 放配置、常量、初始化逻辑

---

### `knowledge_base/`
知识库目录，专门放给 AI 检索的资料。

#### `knowledge_base/raw/`
放原始文件：
- PDF
- Word
- 扫描件
- OCR 前文件

这类文件可能很大，不建议无脑全部提交到 GitHub。

#### `knowledge_base/cleaned/`
放整理后的资料：
- Markdown
- txt
- 分好类的学生手册内容

这部分会被 `scripts/build_vectordb.py` 用来构建向量库。

#### `knowledge_base/metadata/`
放补充说明：
- 文档分类
- 来源
- 更新时间
- 文件编号
- 是否已审核

---

### `scripts/`
放脚本工具，不放接口业务代码。

适合放：
- `build_vectordb.py`：构建向量库
- `rebuild_vectordb.py`：重建向量库
- `eval_retrieval.py`：检索效果测试
- 批量清洗文档脚本

原则：脚本是“维护工具”，不是“接口服务”。

---

### `storage/`
放运行时生成的数据，不提交到 GitHub。

#### `storage/vector_db/`
放本地向量库文件。

#### `storage/history/`
放历史记录文件，例如：
- `history.json`

#### `storage/logs/`
放日志文件。

---

### `docs/`
放项目文档，不放知识库原始资料。

适合放：
- 架构说明
- API 文档
- 部署说明
- 协作规范
- 答辩准备材料

---

### `tests/`
放测试代码。

建议继续细分：

- `tests/backend/`：测试服务函数
- `tests/api/`：测试接口
- `tests/retrieval/`：测试检索效果

---

## 2. 当前前端和后端怎么配合

当前前端默认会用到这些接口：

- `POST /chat_with_memory`
- `POST /chat`
- `GET /get_history`
- `POST /clear_history`

所以联调顺序建议是：

1. 先让 `/chat` 跑通
2. 再补 `/chat_with_memory`
3. 再接 `/get_history`
4. 最后补 `/clear_history` 和知识库接口

---

## 3. 当前仓库最容易乱的地方

### 不要把这几类东西混在一起
- 项目文档 ≠ 知识库资料
- 构建脚本 ≠ 后端接口
- 运行产物 ≠ 源代码
- 页面代码 ≠ 路由配置 ≠ 接口封装

### 记住这几条
1. `docs/` 只放项目文档
2. `knowledge_base/` 只放给 AI 检索的资料
3. `storage/` 只放运行产物
4. `scripts/` 只放脚本工具

---

## 4. 三人协作建议

### A 同学
主做：
- `frontend/src/pages/chat/`
- `frontend/src/pages/me/`
- `backend/app/api/history.py`
- `backend/app/prompts/`

### B 同学
主做：
- `knowledge_base/cleaned/`
- `scripts/build_vectordb.py`
- `scripts/eval_retrieval.py`

### C 同学
主做：
- `backend/app/api/chat.py`
- `backend/app/services/rag_service.py`
- `backend/app/services/retriever.py`
- `backend/app/services/llm_service.py`

---

## 5. 一句话记忆

- `frontend`：用户看到的页面
- `backend`：系统处理逻辑
- `knowledge_base`：学校资料
- `scripts`：工具脚本
- `storage`：运行生成的数据
- `docs`：项目说明
- `tests`：测试
