# 后端说明（学生 C 第 1 阶段）

FastAPI + RAG，当前提供非流式 `POST /chat` 与 `GET /health`。

## 快速启动（PowerShell，仓库根目录）

```powershell
# 1. 安装运行时依赖（已有 backend\.venv 可跳过）
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 2. 可选：复制配置示例（已存在则不覆盖已有配置）
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }

# 3. 确认本机 Ollama 与模型
ollama list          # 应包含 qwen3.5:4b
ollama pull qwen3.5:4b

# 4. 启动（默认 keyword 检索，无需向量库）
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

冒烟测试：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat `
  -ContentType 'application/json' -Body '{"message":"选课时间是怎么规定的？"}'
```

## 检索模式

| 模式 | 依赖 | 数据来源 |
| --- | --- | --- |
| `keyword`（默认） | 无额外依赖 | `knowledge_base/cleaned` 的 md/txt，IDF 覆盖度排序 + `MIN_COVERAGE` 低相关门槛 |
| `chroma`（可选） | `chromadb` + `sentence-transformers` + 本地 BGE 模型 | 只读 B 构建的 `school_documents_content` / `school_documents_structure` 集合 |

chroma 模式使用 `local_files_only=True`，不会联网下载模型。chroma 可选依赖固定在
`backend/requirements-chroma.txt`（chromadb==0.4.24 等），需要时再安装，不要直接升级
chromadb 0.5+。完整说明见
[DEPLOY](../docs/deployment.md)、[API](../docs/api.md)、[第 1 阶段计划](../docs/student_c_plan.md)。

## 测试

```powershell
# 测试依赖（pytest 不在运行时 requirements.txt 中）
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python.exe -m pytest tests/backend tests/api -q
```

测试全部离线运行：不访问真实 Ollama、不写现有向量库。
