# 部署与本地运行（学生 C 第 1 阶段）

以下命令均在仓库根目录（PowerShell）执行。示例路径按本机仓库位置：
`D:\desktop\study\school robot\SchoolRobot`。

## 1. 后端依赖与启动

```powershell
# 已有 backend\.venv 可跳过创建；首次搭建时：
py -3.12 -m venv backend\.venv

# 安装依赖（fastapi / uvicorn / pydantic / httpx / python-dotenv）
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 可选：复制配置示例（环境变量优先于 .env，相对路径按仓库根解析；已存在则不覆盖）
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }

# 启动（默认 keyword 检索，不需要向量库）
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

冒烟测试：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat `
  -ContentType 'application/json' -Body '{"message":"学生违纪处分有哪些种类？"}'

Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

## 2. Ollama

```powershell
ollama list                    # 本机已安装 qwen3.5:4b
ollama pull qwen3.5:4b         # 缺少时拉取

# 后端默认配置
# OLLAMA_BASE_URL=http://127.0.0.1:11434
# MODEL_NAME=qwen3.5:4b
# OLLAMA_TIMEOUT_SECONDS=15    # 必须小于前端 20 秒超时
# OLLAMA_THINK=false           # 只读取 message.content
```

前端 axios 超时为 20 秒；后端默认 15 秒，独立压测 / 脚本联调时可以用
`OLLAMA_TIMEOUT_SECONDS` 调大（例如 60），但前端联调不建议。

## 3. 两种检索配置

### keyword（默认，无额外依赖）

```powershell
$env:RETRIEVAL_MODE = "keyword"          # 或写进 backend\.env
$env:KNOWLEDGE_BASE_DIR = "knowledge_base/cleaned"
$env:MIN_COVERAGE = "0.2"                # 低相关门槛，可按效果微调
```

读取 `knowledge_base/cleaned` 下的 md/txt（排除 README），中文词元匹配 + IDF 覆盖度
排序。分数是启发式相关度，不代表语义理解。

### chroma（可选，需 B 的向量库与重依赖）

```powershell
# 安装固定版本的可选依赖（不要直接升级 chromadb 0.5+）
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-chroma.txt

# 指向 B 构建好的向量库；默认 storage/vector_db/chroma
$env:RETRIEVAL_MODE = "chroma"
$env:VECTOR_DB_PATH = "vectorstore/chroma"   # 现有库可显式指定，不会自动搬迁
$env:EMBEDDING_MODEL_NAME = "BAAI/bge-large-zh-v1.5"
$env:EMBEDDING_DEVICE = "cpu"
```

`backend/requirements-chroma.txt` 固定 `chromadb==0.4.24`、`numpy>=1.24,<2`、
`sentence-transformers>=3.0.1,<4`（选用 3.0.1+ 的 3.x：已核查 v3.0.1 支持
`SentenceTransformer(..., local_files_only=True)`，更早版本未核查、不作为下限依据）。
该清单与 B 的构建环境对齐（`scripts/requirements.txt` 为 `chromadb>=0.4.22,<0.5.0`）。
注意：**不要安装 / 下载重依赖用于常规测试**，`backend/.venv` 仍未安装；
真实 BGE + 真实向量库已由 Codex 在独立验证环境 `storage/vector_db/validation-env` 跑通并评测
（三轮指标波动、质量验收未通过，见 [retrieval_evaluation.md](./retrieval_evaluation.md)）。

注意：

- 后端**不主动创建集合、不执行 add / delete / rebuild**；查询通过 chromadb 打开持久化
  目录，`PersistentClient` 可能维护底层元数据，因此**不承诺物理文件只读**。打开现有
  `vectorstore/chroma` 前请先备份。
- 本机未安装模型文件或缺依赖时，`/chat` 明确返回 503，不会静默改用 keyword。
- 现有向量库在 `vectorstore/chroma`（B 构建），代码默认值是
  `storage/vector_db/chroma`；两者不会自动互相迁移，需要时用 `VECTOR_DB_PATH` 显式指定。
- 首次请求会加载嵌入模型，可能超过前端 20 秒；建议先单独调用一次预热。
- chroma 适配器曾用真实 `chromadb==0.4.24` + 临时数据库 + 假 embedding 做过外部冒烟验证
  （详见测试报告）；真实 BGE 模型 + 真实向量库的端到端已由 Codex 在独立验证环境完成冒烟与
  三轮评测，**质量验收未通过**（跨进程检索不稳定，待 B 检查持久化 / 索引与正式评测集）。

## 4. 测试

```powershell
# 测试依赖（pytest 在 requirements-dev.txt 中，正常运行环境只需要 requirements.txt）
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python.exe -m pytest tests/backend tests/api -q
```

测试全部离线：不访问真实 Ollama、不写现有向量库；chroma 相关用假客户端 / 假嵌入。
只读的真实语料集成回归在知识库目录缺失时自动跳过。

## 5. 常见问题

| 现象 | 排查 |
| --- | --- |
| `/chat` 返回 503“无法连接本地 Ollama” | `ollama list`；确认 `OLLAMA_BASE_URL` 与端口 |
| `/chat` 返回 504 | 模型冷启动慢；首次可先预热，或临时调大 `OLLAMA_TIMEOUT_SECONDS` |
| `/chat` 返回 502“未找到模型” | `ollama pull qwen3.5:4b` |
| `/chat` 返回 503“向量库中缺少集合…” | 用 B 的构建脚本生成向量库，或用 `VECTOR_DB_PATH` 指向已有库 |
| 明明有资料却回答“参考资料未提及” | 调整 `MIN_COVERAGE` / `TOP_K`，或检查问题用词是否与资料差异过大 |
| 新增 / 修改资料后检索不到 | keyword 索引在首次检索时缓存，需**重启后端服务**刷新；向量库更新走 B 的构建流程后同样建议重启 |
| 前端跨域报错 | 默认放行 `http://localhost:3333` 与 `http://127.0.0.1:3333`；换端口时设置 `CORS_ORIGINS` |
