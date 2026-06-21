"""Tests for Agent Runtime + Classification + Skills."""

import importlib
import os
import tempfile
from unittest.mock import MagicMock

import pytest

import app.db
import app.models
from app.llm import LLMClient
from app.agent import agent_run, build_agent_context, parse_llm_response, execute_tool
from app.classification import classify_content
from app.skills import extract_skill


@pytest.fixture
def ctx():
    """Isolated DB + session."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        old = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path
        os.environ["MBCLAW_LLM_MOCK"] = "1"

        for mod in (app.db, app.models):
            importlib.reload(mod)
        for mn in ("app.llm", "app.memory", "app.pipeline", "app.agent", "app.classification", "app.skills"):
            importlib.reload(importlib.import_module(mn))

        from app.agent import agent_run, build_agent_context
        from app.classification import classify_content
        from app.skills import extract_skill

        app.db.init_db()
        db = app.db.SessionLocal()

        s = app.models.Session(id=1, title="test", status="active")
        db.add(s)
        db.commit()

        llm = MagicMock(spec=LLMClient)

        yield {"db": db, "llm": llm, "agent_run": agent_run,
               "build_context": build_agent_context,
               "classify": classify_content, "extract_skill": extract_skill}
        db.close()
        if old is not None:
            os.environ["MBCLAW_DB_PATH"] = old


# ── Agent ──

def test_agent_run_mock(ctx):
    """Agent returns response in mock mode."""
    result = ctx["agent_run"](ctx["db"], 1, "用SQLite还是PostgreSQL？", ctx["llm"], max_turns=3)
    assert "response" in result
    assert "MOCK" in result["response"]
    assert result["turns"] <= 3


def test_agent_run_records_messages(ctx):
    """Agent adds user + assistant messages to session."""
    ctx["agent_run"](ctx["db"], 1, "hello", ctx["llm"])
    msgs = ctx["db"].query(app.models.Message).filter_by(session_id=1).all()
    assert len(msgs) >= 2
    assert msgs[0].role == "user"
    assert msgs[-1].role == "assistant"


def test_agent_closed_session_raises(ctx):
    """Closed session rejects agent run."""
    s = ctx["db"].query(app.models.Session).first()
    s.status = "closed"
    ctx["db"].commit()
    with pytest.raises(ValueError, match="closed"):
        ctx["agent_run"](ctx["db"], 1, "test", ctx["llm"])


# ── Parse ──

def test_parse_tool_call():
    parsed = parse_llm_response("hello <tool>read_file</tool><content>/tmp/x</content> done")
    assert len(parsed["tools"]) == 1
    assert parsed["tools"][0]["name"] == "read_file"


def test_parse_thinking():
    parsed = parse_llm_response("<thinking>let me think</thinking> answer")
    assert len(parsed["thinking"]) == 1
    assert parsed["text"] == "answer"


# ── Classify ──

def test_classify_mock_tech(ctx):
    assert ctx["classify"](ctx["llm"], "应该用SQLite还是PostgreSQL来做这个项目") == "技术选型"


def test_classify_mock_chat(ctx):
    assert ctx["classify"](ctx["llm"], "你好，今天天气真不错") == "闲聊"


# ── Skills ──

def test_extract_skill_mock_sqlite(ctx):
    s = ctx["extract_skill"](ctx["llm"], "讨论了SQLite和FTS5的方案，决定使用FTS5+jieba")
    assert s is not None
    assert "FTS5" in s["skill_name"]


def test_extract_skill_mock_none(ctx):
    s = ctx["extract_skill"](ctx["llm"], "今天天气不错")
    assert s is None
