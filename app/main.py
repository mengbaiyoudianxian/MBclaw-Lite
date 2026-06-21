# T5.2 — 由 OpenHands 实现。
# 约束: ≤80 行
# 必含:
#   app = FastAPI(title="MBclaw", version="0.1.0", lifespan=lifespan)
#   lifespan: init_db()
#   app.include_router(api.router, prefix="/api")
#   DI: get_db, get_llm
#   GET /health → {db_ok, last_llm_status}
#   JSONL helper: append_transcript(sid, msg) 用 fcntl.LOCK_EX
# 不允许: 多 middleware（仅 CORS）
