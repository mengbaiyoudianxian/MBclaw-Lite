"""T6.1 — Unit tests for app.pipeline (T4.1)."""

import importlib
import os
import tempfile
from unittest.mock import MagicMock

import pytest

import app.db
import app.models
from app.llm import LLMOutput
from app.pipeline import close_session


@pytest.fixture
def ctx():
    """Isolated DB, session, and mocked LLM."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        old = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path
        importlib.reload(app.db)
        importlib.reload(app.models)
        for mod_name in ("app.llm", "app.memory", "app.pipeline"):
            importlib.reload(importlib.import_module(mod_name))
        from app.pipeline import close_session
        app.db.init_db()
        db = app.db.SessionLocal()
        # Setup mock LLM
        llm = MagicMock()
        llm.summarize_session.return_value = LLMOutput(
            summary="Test summary about SQLite FTS5.",
            keywords=["sqlite", "fts5", "jieba"],
            experiences=[],
        )
        yield {"db": db, "llm": llm, "close_session": close_session}
        db.close()
        if old is not None:
            os.environ["MBCLAW_DB_PATH"] = old
        else:
            os.environ.pop("MBCLAW_DB_PATH", None)


def _seed_messages(db, sid=1, count=3):
    s = app.models.Session(id=sid, title="test", status="active")
    db.add(s)
    for i in range(count):
        db.add(app.models.Message(session_id=sid, role="user" if i % 2 == 0 else "assistant",
                                   content=f"Message {i} about FTS5 and jieba"))
    db.commit()


# ── tests ───────────────────────────────────────────────────

def test_close_session_returns_summary(ctx):
    _seed_messages(ctx["db"])
    result = ctx["close_session"](ctx["db"], 1, ctx["llm"])
    assert result["status"] == "closed"
    assert len(result["summary"]) > 0


def test_close_session_includes_keywords(ctx):
    _seed_messages(ctx["db"])
    result = ctx["close_session"](ctx["db"], 1, ctx["llm"])
    assert len(result["keywords"]) >= 1
    assert any(k["keyword"] == "sqlite" for k in result["keywords"])


def test_close_session_idempotent(ctx):
    _seed_messages(ctx["db"])
    first = ctx["close_session"](ctx["db"], 1, ctx["llm"])
    assert first["stats"]["cached"] is False
    second = ctx["close_session"](ctx["db"], 1, ctx["llm"])
    assert second["stats"]["cached"] is True
    # LLM should only be called once
    assert ctx["llm"].summarize_session.call_count == 1


def test_close_session_raises_on_empty(ctx):
    s = app.models.Session(id=1, title="empty", status="active")
    ctx["db"].add(s); ctx["db"].commit()
    with pytest.raises(ValueError, match="No messages"):
        ctx["close_session"](ctx["db"], 1, ctx["llm"])
