-- MBclaw Memory System v1 — 001: workspace + memory 表
-- 幂等, 不破坏旧数据

CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    topic TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_archived INTEGER NOT NULL DEFAULT 0
);

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
);

-- sessions 加 workspace_id (如果旧表没有这列)
-- ALTER TABLE sessions ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);

CREATE INDEX IF NOT EXISTS idx_memory_ws_type ON memory(workspace_id, type);
CREATE INDEX IF NOT EXISTS idx_memory_ws_importance ON memory(workspace_id, importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_memory_ws_lastused ON memory(workspace_id, last_used_at DESC);

INSERT OR IGNORE INTO workspaces (id, name, topic) VALUES (1, 'Default', '默认工作区');
