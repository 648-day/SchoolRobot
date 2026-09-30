"""tests/retrieval 公共配置：把 scripts 与 backend 加入 sys.path，并保护进程环境变量。

本目录是学生 C 的检索评测开发回归测试；全部离线运行，不加载模型、不写向量库。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"
for directory in (SCRIPTS_DIR, BACKEND_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "retrieval_cases.json"


@pytest.fixture(autouse=True)
def restore_environ():
    """Settings.from_env / load_dotenv 可能改 os.environ，用快照保证测试互不污染。"""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
