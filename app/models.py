# T1.2 — 由 OpenHands 实现。
# 约束: ≤120 行
# 必含 5 个 model:
#   Session(id, title, status, started_at, ended_at)
#   Message(id, session_id FK, role, content, created_at)
#   Summary(id, session_id FK UNIQUE, summary, created_at)
#   Keyword(id, session_id FK, keyword, weight)
#   Experience(id, session_id FK, kind, title, content, keywords_json,
#              created_at, last_recalled_at NULL, recall_count default 0)
# 不允许: 给 model 挂业务方法; 加 dna/project/user/approval 表
