"""tests/backend 公共配置：把 backend 加入 sys.path，并保护进程环境变量。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def restore_environ():
    """load_dotenv 会直接改 os.environ，用快照保证测试之间互不污染。"""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
