"""Phase1 migration + search"""
from app.db import engine
from sqlalchemy import text as _tx

def run_migration():
    raw = engine.raw_connection()
    try:
        raw.execute("""CREATE TABLE IF NOT EXISTS raw_memories (
            id TEXT PRIMARY KEY, workspace_id INTEGER NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, content_type TEXT NOT NULL DEFAULT 'text',
            reasoning_content TEXT, parent_id TEXT,
            created_at TEXT NOT NULL, is_archived INTEGER NOT NULL DEFAULT 0)""")
        raw.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS raw_memories_fts USING fts5(
            content, tokenize='unicode61')""")
        raw.executescript("""
            CREATE TRIGGER IF NOT EXISTS raw_fts_insert AFTER INSERT ON raw_memories BEGIN
                INSERT INTO raw_memories_fts(rowid, content) VALUES (NEW.rowid, NEW.content); END;
            CREATE TRIGGER IF NOT EXISTS raw_fts_delete AFTER DELETE ON raw_memories BEGIN
                INSERT INTO raw_memories_fts(raw_memories_fts, rowid, content) VALUES('delete', OLD.rowid, OLD.content); END;
            CREATE TRIGGER IF NOT EXISTS raw_fts_update AFTER UPDATE ON raw_memories BEGIN
                INSERT INTO raw_memories_fts(raw_memories_fts, rowid, content) VALUES('delete', OLD.rowid, OLD.content);
                INSERT INTO raw_memories_fts(rowid, content) VALUES (NEW.rowid, NEW.content); END;
        """)
        raw.execute("""CREATE TABLE IF NOT EXISTS memory_nodes (
            id TEXT PRIMARY KEY, workspace_id INTEGER NOT NULL,
            layer TEXT NOT NULL, content_json TEXT NOT NULL,
            summary TEXT, embedding BLOB,
            importance REAL NOT NULL DEFAULT 0.5,
            confidence REAL NOT NULL DEFAULT 0.5,
            quality_score REAL NOT NULL DEFAULT 0.0,
            decay_factor REAL NOT NULL DEFAULT 1.0,
            last_decay_at TEXT, usage_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        raw.execute("CREATE INDEX IF NOT EXISTS idx_nodes_layer ON memory_nodes(layer)")
        raw.execute("CREATE INDEX IF NOT EXISTS idx_nodes_ws ON memory_nodes(workspace_id, layer)")
        raw.execute("CREATE INDEX IF NOT EXISTS idx_raw_ws_time ON raw_memories(workspace_id, created_at)")
        raw.execute("""CREATE TABLE IF NOT EXISTS memory_edges (
            source_id TEXT NOT NULL, target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL, weight REAL NOT NULL DEFAULT 0.5,
            PRIMARY KEY (source_id, target_id, relation_type))""")
        raw.commit()
    finally:
        raw.close()

def write_raw(db_session, workspace_id, role, content, content_type='text', parent_id=None):
    from app.phase1_models import RawMemory
    m = RawMemory(workspace_id=workspace_id, role=role, content=content,
                  content_type=content_type, parent_id=parent_id)
    db_session.add(m)
    db_session.commit()
    # 手动写入jieba分词到FTS5(触发器不够,中文需分词)
    import jieba
    from app.db import engine as _eng
    tokenized = ' '.join(jieba.cut(content))
    _eng.raw_connection().execute(
        'INSERT OR REPLACE INTO raw_memories_fts(rowid, content) VALUES ((SELECT MAX(rowid) FROM raw_memories), ?)',
        [tokenized])
    return m.id

def search_fts(query, workspace_id=None, limit=10):
    """FTS5搜索 — 写入时jieba分词, 查询时jieba分词+OR连接"""
    import jieba
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        tokens = list(jieba.cut(query))
        fts_q = ' OR '.join(t for t in tokens if len(t.strip()) > 1) or query
        sql = """SELECT r.id, r.content, r.role, r.created_at
                 FROM raw_memories_fts f JOIN raw_memories r ON f.rowid = r.rowid
                 WHERE raw_memories_fts MATCH :q"""
        params = {'q': fts_q, 'limit': limit}
        if workspace_id:
            sql += ' AND r.workspace_id = :ws'
            params['ws'] = workspace_id
        sql += ' ORDER BY rank LIMIT :limit'
        result = db.execute(_tx(sql), params).fetchall()
        return [{'id': r[0], 'content': r[1], 'role': r[2], 'created_at': r[3]} for r in result]
    finally:
        db.close()
