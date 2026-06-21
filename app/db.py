# T1.1 — 由 OpenHands 实现。
# 约束: ≤80 行
# 必含:
#   - DATABASE_URL 从 env MBCLAW_DB_PATH 读
#   - engine = create_engine(url, connect_args={"check_same_thread": False})
#   - 启动 PRAGMA: journal_mode=WAL / synchronous=NORMAL / cache_size=-20000 / temp_store=MEMORY
#   - SessionLocal / Base / get_db() / init_db()
#   - init_db() 末尾 executescript(open('app/schema/fts.sql').read())
# 不允许: alembic; 业务查询
