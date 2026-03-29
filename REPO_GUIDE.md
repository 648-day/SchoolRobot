# 仓库说明书

这个文件专门告诉你：**每个文件夹是干什么的，平时应该往哪里放东西。**

## 根目录

### `frontend/`
放前端网页代码。

适合放：
- 聊天页面
- 历史记录页面
- 知识库浏览页面
- 个人中心页面
- 前端接口请求代码
- 页面样式

### `backend/`
放后端服务代码。

适合放：
- FastAPI 接口
- RAG 检索逻辑
- 大模型调用逻辑
- 历史记录读写
- 提示词模板
- 配置文件

### `knowledge_base/`
放给 AI 检索用的知识库资料。

#### `knowledge_base/raw/`
放原始资料。
例如：
- PDF
- Word
- 扫描件
- OCR 前的原始文件

#### `knowledge_base/cleaned/`
放清洗后的资料。
例如：
- Markdown 文档
- txt 文档
- 分好类的学生手册内容

这里的内容会被后端拿去做向量库。

#### `knowledge_base/metadata/`
放文档说明信息。
例如：
- 文档属于哪个分类
- 文档来源
- 更新时间
- 文件编号

### `scripts/`
放脚本工具，不放业务接口代码。

适合放：
- 构建向量库脚本
- 重建向量库脚本
- 检索测试脚本
- 批量清洗文档脚本

### `storage/`
放程序运行过程中生成的本地数据。

#### `storage/vector_db/`
放向量库文件。

注意：
- 这里通常不上传 GitHub
- 因为文件可能很大，而且是可重复生成的

#### `storage/history/`
放聊天历史记录。
例如：
- `history.json`

#### `storage/logs/`
放日志文件。
例如：
- 后端运行日志
- 调试日志

### `tests/`
放测试代码。

#### `tests/backend/`
测试后端服务函数。

#### `tests/api/`
测试接口是否正常。

#### `tests/retrieval/`
测试知识检索是否准确。

### `docs/`
放项目文档，不放知识库原始资料。

适合放：
- 架构说明
- API 文档
- 部署说明
- 协作规范
- 答辩准备文档

### `.github/workflows/`
放 GitHub Actions 自动化配置。

适合放：
- 自动测试
- 自动检查格式
- 自动部署

---

## frontend 里面怎么分

### `frontend/src/views/`
放页面。

- `chat/`：聊天页面
- `history/`：历史记录页面
- `knowledge/`：知识库浏览页面
- `profile/`：个人中心页面

### `frontend/src/components/`
放可复用组件。
例如：
- 聊天气泡
- 顶部导航栏
- 卡片组件

### `frontend/src/api/`
放前端调用后端接口的代码。
例如：
- 发起 `/chat_with_memory`
- 获取 `/get_history`
- 清空 `/clear_history`

### `frontend/src/router/`
放前端页面路由配置。

### `frontend/src/stores/`
放状态管理代码。
例如：
- 当前会话状态
- 用户设置

### `frontend/src/styles/`
放全局样式。

### `frontend/src/utils/`
放工具函数。
例如：
- 时间格式化
- 文本处理

### `frontend/src/assets/`
放图片、图标等静态资源。

---

## backend 里面怎么分

### `backend/app/main.py`
后端启动入口。

### `backend/app/api/`
放接口路由。

- `chat.py`：聊天接口
- `history.py`：历史记录接口
- `knowledge.py`：知识库相关接口

### `backend/app/services/`
放核心业务逻辑。

- `rag_service.py`：RAG 主流程
- `retriever.py`：检索逻辑
- `llm_service.py`：大模型调用
- `history_service.py`：历史记录读写

### `backend/app/prompts/`
放提示词模板。

### `backend/app/schemas/`
放请求体、响应体的数据结构定义。

### `backend/app/core/`
放配置、常量、基础初始化逻辑。

---

## 最重要的使用原则

1. **知识库资料不要放进 `docs/`**
   - `docs/` 是项目文档
   - `knowledge_base/` 才是给 AI 检索的资料

2. **向量库不要放进代码目录**
   - 放在 `storage/vector_db/`
   - 并加入 `.gitignore`

3. **脚本不要和业务代码混写**
   - 构建向量库的脚本放 `scripts/`
   - 接口代码放 `backend/app/api/`

4. **页面、接口、核心逻辑分开**
   - 前端页面在 `frontend/`
   - 后端接口在 `backend/app/api/`
   - 核心逻辑在 `backend/app/services/`

---

## 你们 3 个人可以这样分

### A 同学
主做：
- `frontend/src/views/chat/`
- `backend/app/api/history.py`
- `backend/app/services/history_service.py`
- `backend/app/prompts/`

### B 同学
主做：
- `knowledge_base/cleaned/`
- `scripts/build_vectordb.py`
- `tests/retrieval/`

### C 同学
主做：
- `backend/app/api/chat.py`
- `backend/app/services/rag_service.py`
- `backend/app/services/retriever.py`
- `backend/app/services/llm_service.py`

---

## 一句话记忆

- `frontend`：用户看到的页面
- `backend`：系统处理逻辑
- `knowledge_base`：学校资料
- `scripts`：工具脚本
- `storage`：运行生成的数据
- `docs`：项目说明文档
- `tests`：测试代码
