"""T6.2 — 唯一不可妥协的端到端测试。

执行 AI 必须实现使其通过；不准修改任何 assert 阈值。
完整脚本参见 MBclaw/design/mvp/MVP-r0-1week.md §5。

CI 用 MBCLAW_LLM_MOCK=1 跑；本地真 LLM 跑加 @pytest.mark.live_llm。
"""

import pytest


def test_mbclaw_remembers_across_sessions(client):
    # ROUND 1: 首次开会话
    r1 = client.post("/sessions", json={"title": "选型"}).json()
    assert r1["injected_system_message"] is None
    sid1 = r1["session_id"]

    for role, content in [
        ("user", "我打算用 SQLite FTS5 做全文检索"),
        ("assistant", "FTS5 配合 jieba 分词足够 MVP"),
        ("user", "决定了，就 FTS5+jieba，不上向量库"),
    ]:
        client.post(f"/sessions/{sid1}/messages",
                    json={"role": role, "content": content})

    close1 = client.post(f"/sessions/{sid1}/close").json()
    assert close1["summary"]
    assert len(close1["keywords"]) >= 3
    assert any(k["keyword"] in ("sqlite", "fts5", "jieba")
               for k in close1["keywords"])

    # ROUND 2: 新会话（关键验证点）
    r2 = client.post("/sessions", json={"title": "继续"}).json()
    sid2 = r2["session_id"]

    inj = r2["injected_system_message"]
    assert inj is not None, "★ 新会话必须自动注入上一次的关键事实"
    assert f"#{sid1}" in inj["content"], "★ 必须引用上次 session id"
    assert any(kw in inj["content"].lower()
               for kw in ["sqlite", "fts5", "jieba"]), "★ 必须含上次关键词"
    assert len(inj["content"]) <= 800, "★ 注入硬上限 800 字符"

    # ROUND 3: 注入消息在历史中可见
    msgs = client.get(f"/sessions/{sid2}/messages").json()
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == inj["content"]
