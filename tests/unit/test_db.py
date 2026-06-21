"""T6.1 — Unit tests for app.db (T1.1)."""

import importlib
import os
import tempfile

import pytest

import app.db


@pytest.fixture
def isolated_db_path():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        old = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path
        yield db_path
        if old is not None:
            os.environ["MBCLAW_DB_PATH"] = old
        else:
            os.environ.pop("MBCLAW_DB_PATH", None)


def test_engine_uses_sqlite_and_env_path(isolated_db_path):
    importlib.reload(app.db)
    assert "sqlite" in str(app.db.engine.url)
    assert isolated_db_path in str(app.db.engine.url)


def test_pragmas_applied_on_connect(isolated_db_path):
    importlib.reload(app.db)
    raw = app.db.engine.raw_connection()
    cur = raw.cursor()
    cur.execute("PRAGMA journal_mode"); assert cur.fetchone()[0] == "wal"
    cur.execute("PRAGMA synchronous");  assert cur.fetchone()[0] == 1
    cur.execute("PRAGMA cache_size");   assert cur.fetchone()[0] == -20000
    cur.execute("PRAGMA temp_store");   assert cur.fetchone()[0] == 2
    raw.close()


def test_get_db_yields_working_session(isolated_db_path):
    importlib.reload(app.db)
    from sqlalchemy import text
    gen = app.db.get_db()
    db = next(gen)
    assert db is not None
    result = db.execute(text("SELECT 1"))
    assert result.scalar() == 1
    db.close()


def test_init_db_creates_db_file(isolated_db_path):
    importlib.reload(app.db)
    importlib.reload(importlib.import_module('app.models'))
    assert not os.path.exists(isolated_db_path)
    app.db.init_db()
    assert os.path.exists(isolated_db_path)
    assert os.path.getsize(isolated_db_path) > 0
