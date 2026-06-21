"""共享 pytest fixtures。OpenHands 在 T6.1 中扩展。"""

import os
import shutil
import pytest


@pytest.fixture(autouse=True)
def setup_clean_data(tmp_path, monkeypatch):
    """每个测试独立 data 目录。"""
    db = tmp_path / "mbclaw.db"
    monkeypatch.setenv("MBCLAW_DB_PATH", str(db))
    monkeypatch.setenv("MBCLAW_LLM_MOCK", "1")
    yield
    # tmp_path 自动清理


@pytest.fixture
def client():
    """T5.2 实现 app/main.py 后启用。"""
    pytest.skip("client fixture 待 T5.2 实现 main.py 后启用")
