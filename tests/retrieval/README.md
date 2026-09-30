# 检索评测测试（学生 C）

本目录测试 `scripts/evaluate_retrieval.py` 与 `tests/fixtures/retrieval_cases.json`：
指标定义、评测集校验、报告安全、chroma 临时副本行为。全部离线，不加载模型、
不访问网络、不写向量库。

```powershell
backend\.venv\Scripts\python.exe -m pytest tests\retrieval -q   # 54 passed
backend\.venv\Scripts\python.exe -X utf8 -m pytest tests -q     # 171 passed（117 + 54）
```

- `test_metrics.py`（14）：命中位次 / 重复来源 / 无命中 / 负例 / 错误不计拒答；
  证据判定限定 `expected_source`、要求关键词落在同一片段、按真实返回文本而非
  报告 200 字裁剪片段；top_k 有界。
- `test_dataset.py`（20）：结构校验，以及 fixture 证据逐条与 `knowledge_base/cleaned` 原文核对。
- `test_cli.py`（20）：危险输出路径、报告脱敏、端到端 keyword、缺依赖 / 缺库、
  复制原库而非直开、临时副本清理、失败不写报告；
  模型路径本地相对路径按仓库根解析（异地 CWD 回归）；Chroma 报告 `library`
  记录 `snippet_max_chars / content_weight / structure_weight`。

评测命令、指标定义、keyword 基线与 Chroma 三轮真实评测（含稳定性探针，质量验收未通过、
待 B 检查）见 [docs/retrieval_evaluation.md](../../docs/retrieval_evaluation.md) 与
`docs/evaluation/` 下的 JSON 报告。这是 C 的小样本开发回归集，不是 B 的正式评测集 /
独立测试集，结果不能泛化，也不能据此宣称检索质量达标。