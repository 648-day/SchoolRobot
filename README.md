# campus-ai-assistant

校园智能助手项目仓库。

当前前端已经按移动端模板拆成 3 个核心页面：
- **首页**：校园资讯 / 推文流（新生须知、选课提醒、图书馆规则等）
- **对话页**：单独问答页，对接 `/chat_with_memory` 或 `/chat`
- **我的**：历史记录、清空历史、设置占位

后端按 **FastAPI + RAG** 思路组织，知识库、脚本、运行产物分开存放，方便 3 人协作和大创答辩演示。

---

## 目录结构

```text
campus-ai-assistant/
├── frontend/                # MobVue 前端
├── backend/                 # FastAPI 后端
├── knowledge_base/          # 校园资料知识库
├── scripts/                 # 构建/评测脚本
├── storage/                 # 向量库、历史记录、日志（不提交）
├── docs/                    # 项目文档
├── tests/                   # 测试
├── REPO_GUIDE.md            # 文件夹用途说明
└── .gitignore
```

---

## 前端说明

当前约定的页面是：

- `/`：首页，展示校园通知流
- `/chat`：对话页
- `/me`：我的页

前端推荐开发流程：

```bash
cd frontend
pnpm install
pnpm dev
```

如未安装 pnpm，也可以先用 npm 安装依赖，但团队内最好统一一种包管理器。

前端需要配置后端地址，例如：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 后端说明

后端推荐开发流程：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

建议优先提供这些接口：

- `POST /chat_with_memory`：带记忆问答
- `POST /chat`：基础问答备用接口
- `GET /get_history`：读取历史记录
- `POST /clear_history`：清空历史记录

---

## 知识库与向量库

知识库目录分 3 层：

- `knowledge_base/raw/`：原始资料
- `knowledge_base/cleaned/`：整理后的 Markdown / txt
- `knowledge_base/metadata/`：来源、分类、更新时间等说明

向量库和历史记录不要放进代码目录，统一放到：

- `storage/vector_db/`
- `storage/history/`
- `storage/logs/`

---

## 协作建议

分支建议：

- `main`：稳定版本
- `feature/*`：功能开发
- `bugfix/*`：问题修复

建议按模块分工：

- **A**：前端聊天页、历史记录、提示词联调
- **B**：知识库整理、向量库构建、检索评测
- **C**：RAG 主流程、模型调用、聊天接口

---

## 当前最重要的开发原则

1. 不要把知识库资料放进 `docs/`
2. 不要把向量库提交到 GitHub
3. 不要把构建脚本写进业务接口文件
4. 前端页面、后端接口、RAG 核心逻辑分开维护

详细说明见 [REPO_GUIDE.md](./REPO_GUIDE.md)
