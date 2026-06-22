"""T1.1 — Database connection and session management.

SQLite + WAL mode via SQLAlchemy 2.0.
All PRAGMAs applied on every new connection.
"""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ── connection ──────────────────────────────────────────────

DB_PATH = os.getenv("MBCLAW_DB_PATH", "data/mbclaw.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-20000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


# ── session factory ─────────────────────────────────────────

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session, closes it on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── init ────────────────────────────────────────────────────

def init_db():
    """Create all tables from models and apply FTS5 virtual-table schema."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    fts_path = os.path.join(os.path.dirname(__file__), "schema", "fts.sql")
    with open(fts_path) as f:
        sql = f.read()

    raw_conn = engine.raw_connection()
    raw_conn.executescript(sql)
    raw_conn.close()
