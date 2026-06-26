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


# ── Memory System v1 迁移 ────────────────────────────────────

def _run_migration_v1():
    """执行 Memory System v1 的表结构迁移。幂等, 不破坏旧数据。"""
    raw = engine.raw_connection()
    try:
        # 创建 workspaces 表 (IF NOT EXISTS)
        raw.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                topic TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_archived INTEGER NOT NULL DEFAULT 0
            )
        """)
        # 创建 memory 表 (IF NOT EXISTS)
        raw.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                session_id INTEGER REFERENCES sessions(id),
                type TEXT NOT NULL CHECK(type IN ('episode','semantic','procedure','failure')),
                content_json TEXT NOT NULL,
                embedding BLOB,
                importance_score REAL NOT NULL DEFAULT 0.5,
                tags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_used_at TEXT,
                usage_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        # 给 sessions 加 workspace_id (如果不存在)
        try:
            raw.execute("ALTER TABLE sessions ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id)")
        except Exception:
            pass  # 列已存在, 忽略

        # 索引
        raw.execute("CREATE INDEX IF NOT EXISTS idx_memory_ws_type ON memory(workspace_id, type)")
        raw.execute("CREATE INDEX IF NOT EXISTS idx_memory_ws_importance ON memory(workspace_id, importance_score DESC)")
        raw.execute("CREATE INDEX IF NOT EXISTS idx_memory_ws_lastused ON memory(workspace_id, last_used_at DESC)")

        # 插入默认工作区
        raw.execute("INSERT OR IGNORE INTO workspaces (id, name, topic) VALUES (1, 'Default', '默认工作区')")

        raw.commit()
    finally:
        raw.close()


# ── init ────────────────────────────────────────────────────

def init_db():
    """Create all tables from models and apply FTS5 virtual-table schema."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # FTS5 virtual tables (旧系统)
    fts_path = os.path.join(os.path.dirname(__file__), "schema", "fts.sql")
    if os.path.exists(fts_path):
        with open(fts_path) as f:
            sql = f.read()
        raw_conn = engine.raw_connection()
        raw_conn.executescript(sql)
        raw_conn.close()

    # Memory System v1 迁移
    _run_migration_v1()
