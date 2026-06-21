"""T6.1 — Unit tests for app.memory (T3.1–T3.4).

test_memory_write (6) + test_memory_query (6) + test_memory_render (6) + test_memory_evict (3) = 21
"""

import importlib
import os
import tempfile
from unittest.mock import patch, PropertyMock

import pytest

import app.db
import app.models
from app.memory import MemoryHit, MemoryRepo


@pytest.fixture
def repo():
    """Isolated DB + MemoryRepo wired to a fresh session."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        old = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path
        importlib.reload(app.db)
        importlib.reload(app.models)
        importlib.reload(importlib.import_module("app.memory"))
        from app.memory import MemoryRepo
        app.db.init_db()
        session = app.db.SessionLocal()
        yield MemoryRepo(session)
        session.close()
        if old is not None:
            os.environ["MBCLAW_DB_PATH"] = old
        else:
            os.environ.pop("MBCLAW_DB_PATH", None)


def _make_session(repo, sid=1):
    s = app.models.Session(id=sid, title=f"s{sid}", status="active")
    repo.db.add(s)
    repo.db.commit()


# ═══════════════════ T3.1 write (6) ══════════════════════════

def test_write_creates_summary(repo):
    _make_session(repo)
    repo.write_session_memory(1, "summary text", [], [])
    s = repo.db.query(app.models.Summary).filter_by(session_id=1).first()
    assert s is not None and s.summary == "summary text"


def test_write_creates_keywords(repo):
    _make_session(repo)
    repo.write_session_memory(1, "s", ["kw1", "kw2", "kw3"], [])
    kws = repo.db.query(app.models.Keyword).filter_by(session_id=1).all()
    assert len(kws) == 3


def test_write_creates_experiences(repo):
    _make_session(repo)
    repo.write_session_memory(1, "s", [], [
        {"kind": "success", "title": "t1", "content": "c1"},
        {"kind": "failure", "title": "t2", "content": "c2"},
    ])
    exps = repo.db.query(app.models.Experience).filter_by(session_id=1).all()
    assert len(exps) == 2


def test_write_caps_experiences_at_5(repo):
    _make_session(repo)
    exps = [{"kind": "lesson", "title": f"t{i}", "content": f"c{i}"} for i in range(10)]
    repo.write_session_memory(1, "s", [], exps)
    count = repo.db.query(app.models.Experience).filter_by(session_id=1).count()
    assert count == 5


def test_write_overwrites_old_keywords(repo):
    _make_session(repo)
    repo.write_session_memory(1, "s", ["a", "b"], [])
    repo.write_session_memory(1, "s2", ["c"], [])
    kws = repo.db.query(app.models.Keyword).filter_by(session_id=1).all()
    assert [k.keyword for k in kws] == ["c"]


def test_write_upserts_summary(repo):
    _make_session(repo)
    repo.write_session_memory(1, "first", [], [])
    repo.write_session_memory(1, "second", [], [])
    summaries = repo.db.query(app.models.Summary).filter_by(session_id=1).all()
    assert len(summaries) == 1 and summaries[0].summary == "second"


# ═══════════════════ T3.2 query (6) ═════════════════════════

def test_query_fts_recall(repo):
    _make_session(repo)
    app.models.Message.__table__.create(repo.db.bind, checkfirst=True)
    from app.models import Message
    m = Message(id=1, session_id=1, role="user", content="SQLite FTS5 full text search")
    repo.db.add(m); repo.db.commit()
    repo.write_session_memory(1, "about sqlite fts5", ["sqlite", "fts5"], [])
    hits = repo.query("fts5")
    assert len(hits) >= 1


def test_query_keyword_recall(repo):
    _make_session(repo)
    repo.write_session_memory(1, "python async patterns", ["python", "async", "await"], [])
    hits = repo.query("python")
    assert len(hits) >= 1 and hits[0].session_id == 1


def test_query_returns_max_top_n(repo):
    for i in range(5):
        _make_session(repo, sid=i + 1)
        repo.write_session_memory(i + 1, f"session {i}", [f"kw{i}"], [])
    hits = repo.query("session", top_n=3)
    assert len(hits) <= 3


def test_query_scores_are_between_0_and_1(repo):
    _make_session(repo)
    repo.write_session_memory(1, "test content", ["t1"], [])
    hits = repo.query("test")
    if hits:
        assert 0.0 <= hits[0].score <= 1.0


def test_query_empty_input_returns_empty(repo):
    assert repo.query("") == []


def test_query_source_field_set(repo):
    _make_session(repo)
    repo.write_session_memory(1, "unique phrase here", ["unique"], [])
    for h in repo.query("unique"):
        assert h.source in ("fts", "keywords", "both")


# ═══════════════════ T3.3 experiences + render (6) ═══════════

def test_query_experiences_fts(repo):
    _make_session(repo)
    app.models.Experience.__table__.create(repo.db.bind, checkfirst=True)
    repo.write_session_memory(1, "s", [], [
        {"kind": "lesson", "title": "Learned FTS5", "content": "FTS5 is fast for search"},
    ])
    exps = repo.query_experiences("fts5")
    assert len(exps) >= 1


def test_query_experiences_returns_at_most_top_n(repo):
    _make_session(repo)
    for i in range(5):
        repo.write_session_memory(1, "s", [], [
            {"kind": "lesson", "title": f"Lesson {i}", "content": "content about search"}
        ])
    exps = repo.query_experiences("search", top_n=2)
    assert len(exps) <= 2


def test_query_experiences_bumps_recall_count(repo):
    _make_session(repo)
    repo.write_session_memory(1, "s", [], [
        {"kind": "lesson", "title": "Test", "content": "recall test pattern"},
    ])
    repo.query_experiences("recall")
    e = repo.db.query(app.models.Experience).first()
    assert e.recall_count >= 1 and e.last_recalled_at is not None


def test_render_injection_returns_none_when_no_closed_session(repo):
    assert repo.render_injection_for_new_session() is None


def test_render_injection_includes_session_ref(repo):
    _make_session(repo)
    repo.write_session_memory(1, "decided to use sqlite fts5", ["sqlite", "fts5"], [
        {"kind": "failure", "title": "do not use vectors", "content": "too heavy"},
        {"kind": "success", "title": "fts5 works", "content": "good enough"},
    ])
    s = repo.db.query(app.models.Session).first()
    s.status = "closed"; repo.db.commit()
    result = repo.render_injection_for_new_session()
    assert result is not None and "#1" in result
    assert "sqlite" in result.lower() or "fts5" in result.lower()


def test_render_injection_max_800_chars(repo):
    _make_session(repo)
    repo.write_session_memory(1, "x" * 400, ["k1", "k2", "k3", "k4", "k5"], [
        {"kind": "failure", "title": "bad" * 30, "content": "c"},
    ])
    s = repo.db.query(app.models.Session).first()
    s.status = "closed"; repo.db.commit()
    result = repo.render_injection_for_new_session()
    assert result is not None and len(result) <= 800


# ═══════════════════ T3.4 evict (3) ═════════════════════════

def test_evict_does_nothing_under_threshold(repo):
    _make_session(repo)
    repo.write_session_memory(1, "s", [], [
        {"kind": "lesson", "title": "t1", "content": "c1"}
    ])
    assert repo._maybe_evict_experiences() == 0


def test_evict_archives_and_reduces(repo):
    """When count > 1000, oldest experiences are evicted."""
    _make_session(repo)
    # Insert 1001 experiences via bulk insert for speed
    from app.models import Experience as E
    repo.db.query(E).delete(); repo.db.commit()
    # Bulk insert 1001 minimal rows
    rows = [{"session_id": 1, "kind": "lesson", "title": f"e{i}",
             "content": f"c{i}", "keywords_json": "[]"} for i in range(1001)]
    repo.db.execute(E.__table__.insert(), rows)
    repo.db.commit()

    removed = repo._maybe_evict_experiences()
    assert removed >= 1
    remaining = repo.db.query(E).count()
    assert remaining <= 1000


def test_evict_handles_exact_threshold(repo):
    """Exactly 1000 experiences → no eviction."""
    _make_session(repo)
    from app.models import Experience as E
    repo.db.query(E).delete(); repo.db.commit()
    rows = [{"session_id": 1, "kind": "lesson", "title": f"e{i}",
             "content": f"c{i}", "keywords_json": "[]"} for i in range(1000)]
    repo.db.execute(E.__table__.insert(), rows)
    repo.db.commit()
    assert repo._maybe_evict_experiences() == 0
    assert repo.db.query(E).count() == 1000
