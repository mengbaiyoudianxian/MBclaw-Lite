"""Agent Runtime — LLM-driven conversation loop with tool execution.

Derived from agent_runtime.py. Uses MemoryRepo + tools module.
"""

import json, os, re
from app.llm import LLMClient
from app.memory import MemoryRepo
from app.tools import execute as exec_tool, bump_usage, list_tools
from app.models import Message, Session as SessionModel
from sqlalchemy.orm import Session as DBSession

AGENT_PROMPT = """你是 MBclaw，一个智能编程助手。

回复格式:
- 用工具: <tool>工具名</tool><content>参数</content>
- 思考: <thinking>内容</thinking>
- 回答: 直接回复

可用工具:
{tools_list}

规则: 先理解问题，优先查记忆库，出错自动修复最多3次，完成后总结。"""

TOOL_RE = re.compile(r'<tool>(.*?)</tool>\s*<content>(.*?)</content>', re.DOTALL)
THINK_RE = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)


def _build_context(db: DBSession, session_id: int, user_msg: str) -> str:
    """Assemble context: memory hits + recent messages + tools."""
    parts = []

    # Memory
    hits = MemoryRepo(db).query(user_msg, top_n=3)
    if hits:
        parts.append("## 相关记忆")
        for h in hits:
            parts.append(f"- [#{h.session_id}] {h.summary[:200]}")
            if h.keywords:
                parts.append(f"  关键词: {', '.join(h.keywords[:5])}")
        parts.append("")

    # Recent messages
    recent = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.desc()).limit(10).all()
    if recent:
        parts.append("## 对话历史")
        for m in reversed(recent):
            role = "用户" if m.role == "user" else "助手" if m.role == "assistant" else m.role
            parts.append(f"[{role}]: {m.content[:300]}")
        parts.append("")

    return "\n".join(parts)


def agent_run(db: DBSession, session_id: int, user_message: str, llm: LLMClient, max_turns: int = 5) -> dict:
    """Execute one agent turn loop."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise ValueError(f"Session {session_id} not found")
    if session.status == "closed":
        raise ValueError("Session is closed")

    # Record user message
    db.add(Message(session_id=session_id, role="user", content=user_message))
    db.commit()

    tools = list_tools(db)
    tools_text = "\n".join(f"- {t['name']}: {t['summary']}" for t in tools)
    system_prompt = AGENT_PROMPT.format(tools_list=tools_text)

    tools_used, thinking, turns = [], [], 0
    current = user_message
    final = ""

    while turns < max_turns:
        turns += 1
        ctx = _build_context(db, session_id, current)

        if os.getenv("MBCLAW_LLM_MOCK") == "1":
            final = f"[MOCK Agent] 收到: {user_message[:100]}。第{turns}轮，上下文{len(ctx)}字符。"
            break

        try:
            import httpx
            resp = httpx.post(f"{llm.base_url}/chat/completions", headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {llm.api_key}"} if llm.api_key else {})
            }, json={"model": llm.model, "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"## 上下文\n{ctx}\n\n## 当前输入\n{current}"}
            ], "temperature": 0.3, "max_tokens": 2000}, timeout=120)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            final = f"LLM调用失败: {e}"
            break

        # Parse
        tool_matches = [(m.group(1).strip(), m.group(2).strip()) for m in TOOL_RE.finditer(raw)]
        think_matches = [m.group(1).strip() for m in THINK_RE.finditer(raw)]
        clean = TOOL_RE.sub('', raw)
        clean = THINK_RE.sub('', clean).strip()
        thinking.extend(think_matches)
        final = clean

        if tool_matches:
            results = []
            for tname, tcontent in tool_matches:
                tools_used.append(tname)
                bump_usage(db, tname)
                r = exec_tool(db, tname, tcontent)
                results.append(f"<tool-result name=\"{tname}\">\n{r}\n</tool-result>")
                db.add(Message(session_id=session_id, role="assistant",
                               content=f"[tool:{tname}] {r[:200]}"))
            db.commit()
            current = "工具执行结果:\n" + "\n".join(results)
        else:
            break

    db.add(Message(session_id=session_id, role="assistant", content=final))
    db.commit()

    return {"session_id": session_id, "response": final, "tools_used": tools_used,
            "turns": turns, "thinking": thinking, "messages_added": turns + 1}
