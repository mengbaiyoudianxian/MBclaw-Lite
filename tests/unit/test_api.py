"""T6.1 — Unit tests for app.api (T5.1)."""

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
    """FastAPI TestClient with isolated DB and mocked LLM."""
    with tempfile.TemporaryDirectory() as tmp:
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
            summary="User decided to use SQLite FTS5.",
            keywords=["sqlite", "fts5"],
            experiences=[{"kind": "success", "title": "Chose FTS5", "content": "Fast enough"}],
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


# ── POST /sessions ──────────────────────────────────────────

def test_create_session(client):
    r = client.post("/sessions", json={"title": "test"})
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == 1
    assert data["status"] == "active"


def test_create_session_no_injection_on_first(client):
    r = client.post("/sessions", json={"title": "first"})
    assert r.json()["injected_system_message"] is None


# ── POST /sessions/{sid}/messages ───────────────────────────

def test_add_message(client):
    client.post("/sessions", json={"title": "s1"})
    r = client.post("/sessions/1/messages", json={"role": "user", "content": "hello"})
    assert r.status_code == 200
    assert r.json()["role"] == "user"


def test_add_message_to_closed_session_fails(client):
    client.post("/sessions", json={"title": "s1"})
    client.post("/sessions/1/messages", json={"role": "user", "content": "msg1"})
    client.post("/sessions/1/close")
    r = client.post("/sessions/1/messages", json={"role": "user", "content": "late"})
    assert r.status_code == 400


# ── POST /sessions/{sid}/close ──────────────────────────────

def test_close_session(client):
    client.post("/sessions", json={"title": "s1"})
    client.post("/sessions/1/messages", json={"role": "user", "content": "Let us use FTS5."})
    r = client.post("/sessions/1/close")
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
    assert len(r.json()["summary"]) > 0


def test_close_nonexistent_session(client):
    r = client.post("/sessions/999/close")
    assert r.status_code == 400


# ── GET /sessions/{sid}/messages ────────────────────────────

def test_list_messages(client):
    client.post("/sessions", json={"title": "s1"})
    client.post("/sessions/1/messages", json={"role": "user", "content": "m1"})
    client.post("/sessions/1/messages", json={"role": "assistant", "content": "m2"})
    r = client.get("/sessions/1/messages")
    assert r.status_code == 200
    assert len(r.json()) >= 2


# ── GET /search ─────────────────────────────────────────────

def test_search_requires_query(client):
    r = client.get("/search")
    assert r.status_code == 422


def test_search_returns_hits(client):
    client.post("/sessions", json={"title": "s1"})
    client.post("/sessions/1/messages", json={"role": "user", "content": "fts5"})
    client.post("/sessions/1/close")
    r = client.get("/search?q=fts5")
    assert r.status_code == 200


# ── health ──────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["db_ok"] is True
