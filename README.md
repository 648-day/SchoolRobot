# campus-ai-assistant

一个适合“大创校园智能助手”项目的 GitHub 仓库初始化模板。

## 项目结构
- `frontend/`：前端网页项目
- `backend/`：FastAPI 后端项目
- `knowledge_base/`：知识库原始文档与清洗文档
- `scripts/`：向量库构建与测试脚本
- `storage/`：本地生成的数据文件（不提交到 GitHub）
- `docs/`：开发文档与协作文档

## 快速开始

### 1. 前端
```bash
cd frontend
npm install
npm run dev
```

### 2. 后端
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 协作建议
- `main`：稳定版本
- `feature/*`：功能开发分支
- `bugfix/*`：修复分支

详细说明见 `REPO_GUIDE.md`。
