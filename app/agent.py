"""Agent Runtime — execution loop: LLM → context → tools → memory → classify.

Flow:
  1. Load session + recent messages
  2. Build context: memory hits + skills + project info
  3. Call LLM with context → parse response for tool calls
  4. Execute tools → record results → loop if needed
  5. On completion → classify content, check skill triggers
"""

import json
import re
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.llm import LLMClient, LLMError
from app.memory import MemoryRepo
from app.models import Message, Session as SessionModel


# ── system prompt ───────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """你是 MBclaw，一个智能编程助手。你可以使用工具来完成用户的任务。

回复格式：
1. 如果需要使用工具，回复: <tool>工具名</tool><content>参数或内容</content>
2. 如果是思考过程，回复: <thinking>思考内容</thinking>
3. 如果是最终答案，直接回复

可用工具:
- read_file(path) — 读取文件内容
- write_file(path, content) — 写入文件
- edit_file(path, old_str, new_str) — 编辑文件
- run_command(cmd) — 执行 shell 命令
- search_memory(query) — 搜索记忆库
- web_search(query) — 搜索网络

规则：
- 先理解问题，再决定行动
- 优先搜索记忆库，避免重复犯错
- 出错后自动修复，最多尝试3次
- 完成后总结做了什么
- 如果用户只是聊天，直接回复，不需要工具"""


# ── context builder ─────────────────────────────────────────

def build_agent_context(
    db: DBSession,
    session_id: int,
    user_message: str,
) -> str:
    """Assemble context: memory + recent messages."""
    parts: list[str] = []

    # Recent messages (last 20, oldest first)
    recent = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.desc()).limit(20).all()
    recent = list(reversed(recent))

    if recent:
        parts.append("## 对话历史\n")
        for m in recent:
            role_label = "用户" if m.role == "user" else "助手" if m.role == "assistant" else m.role
            parts.append(f"[{role_label}]: {m.content[:500]}")
        parts.append("")

    # Memory search (from other sessions)
    repo = MemoryRepo(db)
    hits = repo.query(user_message, top_n=3)
    if hits:
        parts.append("## 相关记忆\n")
        for h in hits:
            parts.append(f"- [#{h.session_id}] {h.summary[:200]}")
            if h.keywords:
                parts.append(f"  关键词: {', '.join(h.keywords[:5])}")
        parts.append("")

    return "\n".join(parts)


# ── tool parser ─────────────────────────────────────────────

TOOL_PATTERN = re.compile(r'<tool>(.*?)</tool>\s*<content>(.*?)</content>', re.DOTALL)
THINKING_PATTERN = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)


def parse_llm_response(response: str) -> dict:
    """Extract tool calls and thinking from LLM response."""
    tools = []
    for match in TOOL_PATTERN.finditer(response):
        tools.append({
            "name": match.group(1).strip(),
            "content": match.group(2).strip(),
        })

    thinkings = [m.group(1).strip() for m in THINKING_PATTERN.finditer(response)]

    # Clean text: remove XML tags
    clean = TOOL_PATTERN.sub('', response)
    clean = THINKING_PATTERN.sub('', clean).strip()

    return {
        "text": clean,
        "tools": tools,
        "thinking": thinkings,
    }


# ── tool executor ───────────────────────────────────────────

def execute_tool(tool_name: str, content: str, db: DBSession) -> str:
    """Execute a tool call and return the result."""
    try:
        if tool_name == "read_file":
            path = content.strip()
            if not os.path.isabs(path):
                return f"错误: 需要绝对路径，收到: {path}"
            if not os.path.exists(path):
                return f"文件不存在: {path}"
            with open(path) as f:
                text = f.read()
            if len(text) > 3000:
                text = text[:3000] + f"\n... (截断，共 {len(text)} 字符)"
            return text

        elif tool_name == "write_file":
            # Expected format: path\n---\ncontent
            parts = content.split('\n', 1)
            if len(parts) < 2:
                return "错误: write_file 需要 path 和 content，用换行分隔"
            path = parts[0].strip()
            body = parts[1]
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w') as f:
                f.write(body)
            return f"写入成功: {path}"

        elif tool_name == "edit_file":
            # Expected format: path\n---\nold_str\n---\nnew_str
            parts = content.split('\n---\n')
            if len(parts) < 3:
                return "错误: edit_file 需要 path, old_str, new_str，用 --- 分隔"
            path, old, new = parts[0].strip(), parts[1], parts[2]
            if not os.path.exists(path):
                return f"文件不存在: {path}"
            with open(path) as f:
                text = f.read()
            if old not in text:
                return f"未找到要替换的文本"
            text = text.replace(old, new, 1)
            with open(path, 'w') as f:
                f.write(text)
            return f"编辑成功: {path}"

        elif tool_name == "run_command":
            import subprocess
            result = subprocess.run(content, shell=True, capture_output=True, text=True, timeout=30)
            out = result.stdout
            if result.stderr:
                out += f"\n[stderr]: {result.stderr}"
            if len(out) > 2000:
                out = out[:2000] + f"\n... (截断)"
            return out or f"(退出码: {result.returncode})"

        elif tool_name == "search_memory":
            repo = MemoryRepo(db)
            hits = repo.query(content, top_n=5)
            if not hits:
                return "未找到相关记忆"
            lines = []
            for h in hits:
                lines.append(f"- [#{h.session_id}] {h.summary[:200]}")
            return "\n".join(lines)

        elif tool_name == "web_search":
            return f"[web_search] 功能需要外部 API，当前不可用。建议用 search_memory 在本地记忆库中查找。查询: {content[:100]}"

        else:
            return f"未知工具: {tool_name}"

    except Exception as e:
        return f"工具执行出错: {e}"


# ── agent run ───────────────────────────────────────────────

def agent_run(
    db: DBSession,
    session_id: int,
    user_message: str,
    llm: LLMClient,
    max_turns: int = 5,
) -> dict:
    """Execute one agent turn: build context → LLM → tools → loop → final response.

    Returns:
        {response, tools_used, turns, thinking, messages_added}
    """
    # Verify session
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise ValueError(f"Session {session_id} not found")
    if session.status == "closed":
        raise ValueError(f"Session {session_id} is closed")

    # Record user message
    user_msg = Message(session_id=session_id, role="user", content=user_message)
    db.add(user_msg)
    db.commit()

    tools_used: list[str] = []
    all_thinking: list[str] = []
    turns = 0
    final_response = ""

    current_input = user_message

    while turns < max_turns:
        turns += 1

        # Build context
        ctx_text = build_agent_context(db, session_id, current_input)

        # Mock mode — skip real LLM call
        if os.getenv("MBCLAW_LLM_MOCK") == "1":
            final_response = (
                f"[MOCK Agent] 收到: {user_message[:100]}。"
                f"第 {turns} 轮，上下文 {len(ctx_text)} 字符。"
            )
            break

        # Build messages for LLM
        llm_messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"## 上下文\n{ctx_text}\n\n## 当前输入\n{current_input}"},
        ]

        try:
            # Call LLM — use raw /chat/completions to get free-form response
            import httpx
            url = f"{llm.base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if llm.api_key:
                headers["Authorization"] = f"Bearer {llm.api_key}"
            body = {
                "model": llm.model,
                "messages": llm_messages,
                "temperature": 0.3,
                "max_tokens": 2000,
            }

            resp = httpx.post(url, headers=headers, json=body, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]

        except Exception as e:
            final_response = f"LLM 调用失败: {e}"
            break

        # Parse response
        parsed = parse_llm_response(raw)
        all_thinking.extend(parsed["thinking"])
        final_response = parsed["text"]

        # Execute tools
        if parsed["tools"]:
            tool_results: list[str] = []
            for tool in parsed["tools"]:
                tools_used.append(tool["name"])
                result = execute_tool(tool["name"], tool["content"], db)
                tool_results.append(f"<tool-result name=\"{tool['name']}\">\n{result}\n</tool-result>")

            # Feed tool results back to LLM
            current_input = f"工具执行结果:\n" + "\n".join(tool_results)
            # Record tool call as assistant message
            record_msg = Message(
                session_id=session_id, role="assistant",
                content=f"[tool: {', '.join(t['name'] for t in parsed['tools'])}]"
            )
            db.add(record_msg)
            db.commit()
        else:
            # No more tools — final answer
            break

    # Record final response
    final_msg = Message(session_id=session_id, role="assistant", content=final_response)
    db.add(final_msg)
    db.commit()

    return {
        "session_id": session_id,
        "response": final_response,
        "tools_used": tools_used,
        "turns": turns,
        "thinking": all_thinking,
        "messages_added": turns + 1,  # user message + assistant turns
    }
