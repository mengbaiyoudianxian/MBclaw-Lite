"""T6.1 — Unit tests for app.models (T1.2)."""

import importlib
import os
import tempfile

import pytest
from sqlalchemy.exc import IntegrityError

import app.db
import app.models


@pytest.fixture
def db_session():
    """Initialise an isolated DB and return a SQLAlchemy Session."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        old = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path
        importlib.reload(app.db)
        importlib.reload(app.models)
        app.db.init_db()
        session = app.db.SessionLocal()
        yield session
        session.close()
        if old is not None:
            os.environ["MBCLAW_DB_PATH"] = old
        else:
            os.environ.pop("MBCLAW_DB_PATH", None)


def test_all_five_tables_exist(db_session):
    """sessions, messages, summaries, keywords, experiences all present."""
    tables = set(app.db.Base.metadata.tables.keys())
    assert tables == {"sessions", "messages", "summaries", "keywords", "experiences"}


def test_session_crud_and_defaults(db_session):
    """Session: create, read, status defaults to 'active'."""
    s = app.models.Session(title="test session")
    db_session.add(s)
    db_session.commit()

    row = db_session.get(app.models.Session, s.id)
    assert row.id == 1
    assert row.title == "test session"
    assert row.status == "active"
    assert row.started_at is not None
    assert row.ended_at is None


def test_message_fk_to_session(db_session):
    """Message.session_id references sessions.id."""
    s = app.models.Session(title="s1")
    db_session.add(s)
    db_session.flush()

    m = app.models.Message(session_id=s.id, role="user", content="hello")
    db_session.add(m)
    db_session.commit()

    row = db_session.get(app.models.Message, m.id)
    assert row.session_id == s.id
    assert row.role == "user"
    assert row.content == "hello"


def test_summary_unique_per_session(db_session):
    """Summary.session_id is UNIQUE."""
    s = app.models.Session(title="s1")
    db_session.add(s)
    db_session.flush()

    db_session.add(app.models.Summary(session_id=s.id, summary="first"))
    db_session.commit()

    db_session.add(app.models.Summary(session_id=s.id, summary="second"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_experience_defaults(db_session):
    """Experience: recall_count=0, last_recalled_at=None, keywords_json='[]'."""
    s = app.models.Session(title="s1")
    db_session.add(s)
    db_session.flush()

    e = app.models.Experience(
        session_id=s.id, kind="lesson", title="learned X", content="details"
    )
    db_session.add(e)
    db_session.commit()

    row = db_session.get(app.models.Experience, e.id)
    assert row.recall_count == 0
    assert row.last_recalled_at is None
    assert row.keywords_json == "[]"
