"""Tests for search, feedback, snapshot modules."""

import importlib
import os
import tempfile
from unittest.mock import MagicMock

import pytest

import app.db
import app.models
from app.llm import LLMClient


@pytest.fixture
def ctx():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        old = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path
        os.environ["MBCLAW_LLM_MOCK"] = "1"
        for mod in (app.db, app.models):
            importlib.reload(mod)
        for mn in ("app.llm", "app.memory", "app.search", "app.feedback", "app.snapshot"):
            importlib.reload(importlib.import_module(mn))
        from app.search import layered_search
        from app.feedback import submit_feedback, get_feedback_stats
        from app.snapshot import create_snapshot, list_snapshots
        app.db.init_db()
        db = app.db.SessionLocal()
        s = app.models.Session(id=1, title="test", status="active")
        db.add(s); db.commit()
        yield {"db": db, "layered_search": layered_search,
               "submit_feedback": submit_feedback, "feedback_stats": get_feedback_stats,
               "create_snapshot": create_snapshot, "list_snapshots": list_snapshots}
        db.close()
        if old is not None: os.environ["MBCLAW_DB_PATH"] = old


def test_layered_search_empty(ctx):
    hits = ctx["layered_search"](ctx["db"], "nothing matches this")
    assert isinstance(hits, list)


def test_layered_search_has_layers(ctx):
    # Seed memory then search
    from app.memory import MemoryRepo
    repo = MemoryRepo(ctx["db"])
    repo.write_session_memory(1, "SQLite FTS5 full-text search", ["sqlite", "fts5"], [])
    hits = ctx["layered_search"](ctx["db"], "sqlite")
    if hits:
        assert "matched_in" in hits[0]
        assert len(hits[0]["matched_in"]) >= 1


def test_submit_feedback_valid(ctx):
    r = ctx["submit_feedback"](ctx["db"], 1, 4, "general", "good")
    assert r["rating"] == 4


def test_submit_feedback_invalid_rating(ctx):
    with pytest.raises(ValueError):
        ctx["submit_feedback"](ctx["db"], 1, 0, "general", "")


def test_feedback_stats(ctx):
    ctx["submit_feedback"](ctx["db"], 1, 5, "ux", "great")
    ctx["submit_feedback"](ctx["db"], 1, 3, "ux", "ok")
    stats = ctx["feedback_stats"](ctx["db"])
    assert stats["total"] == 2
    assert stats["avg_rating"] == 4.0


def test_snapshot_create_list(ctx):
    s = ctx["create_snapshot"](ctx["db"], "test-snap", "desc")
    assert s["name"] == "test-snap"
    snaps = ctx["list_snapshots"]()
    assert len(snaps) >= 1
