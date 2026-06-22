"""T6.2 — E2E test fixtures: isolated DB + mocked LLM TestClient."""

import importlib
import os
import tempfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.db as _db
import app.models as _models
from app.llm import LLMOutput


@pytest.fixture
def client():
    """TestClient wired to a real FastAPI app with mocked LLM."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ.setdefault("MBCLAW_LLM_MOCK", "1")
        db_path = os.path.join(tmp, "test.db")
        old_db = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path

        importlib.reload(_db)
        importlib.reload(_models)
        for mn in ("app.llm", "app.memory", "app.pipeline", "app.api", "app.main"):
            importlib.reload(importlib.import_module(mn))

        app_main = importlib.import_module("app.main")
        app_llm = importlib.import_module("app.llm")

        mock_llm = MagicMock(spec=app_llm.LLMClient)
        mock_llm.summarize_session.return_value = LLMOutput(
            summary="用户决定使用 SQLite FTS5 配合 jieba 分词作为全文检索方案，确认不上向量库。",
            keywords=["sqlite", "fts5", "jieba", "全文检索"],
            experiences=[
                {"kind": "success", "title": "FTS5+jieba选型决策",
                 "content": "经过讨论确定使用SQLite FTS5配合jieba分词，够MVP使用，不上向量库"},
            ],
        )

        _db2 = importlib.import_module("app.db")
        app_main.app.dependency_overrides[_db2.get_db] = lambda: _db2.SessionLocal()
        app_main.app.dependency_overrides[app_llm.get_llm] = lambda: mock_llm

        with TestClient(app_main.app) as tc:
            yield tc

        app_main.app.dependency_overrides.clear()
        if old_db is not None:
            os.environ["MBCLAW_DB_PATH"] = old_db
        else:
            os.environ.pop("MBCLAW_DB_PATH", None)
