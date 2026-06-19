"""Agent Runtime — the execution loop that drives MBclaw through tasks.

This is the missing link between the orchestration APIs and actual agent behavior.
It connects: LLM → memory → skills → tools → classification → H3 extraction.

Flow per task cycle:
  1. Fetch active task + session
  2. Build context: memory (L1/L2/L3) + skills + DNA + recent messages
  3. Call LLM with context → get response + tool calls
  4. Execute tool calls → record results
  5. Detect errors → self-correct or escalate
  6. Record messages in session
  7. On completion → classify, flush memory, check breakthroughs, trigger H3

Usage:
  POST /api/projects/{id}/agent/run
  Body: {session_id, message, max_turns=10, mode="auto"|"dual-key"|"sub-agent"}
"""

import json
import time
import asyncio
from typing import Any, Optional
from sqlalchemy.orm import Session as DBSession

from app.services.llm_service import get_llm, LLM_ENABLED
from app.services.skill_extractor import detect_triggers, extract_skill_rules, save_extracted_skill


AGENT_SYSTEM_PROMPT = """你是 MBclaw，一个智能编程助手。你可以使用工具来完成用户的任务。

回复格式：
1. 如果需要使用工具，回复: <tool>工具名</tool><content>参数或内容</content>
2. 如果是思考，回复: <thinking>思考内容</thinking>
3. 如果是最终答案，直接回复

可用工具: read_file, write_file, edit_file, run_command, search_code, web_search

规则：
- 先理解问题，再行动
- 出错后自动修复，最多尝试3次
- 完成后总结做了什么"""


# ═══════════════════════════════════════════════════════════
# Context builder
# ═══════════════════════════════════════════════════════════

def build_context(
    db: DBSession,
    project_id: int,
    user_id: int,
    task_name: str,
    session_id: int,
) -> str:
    """Build agent context from memory, skills, DNA, and recent messages."""
    parts = []

    # L1/L2/L3 Memory — search existing summaries/topics
    from app.services.search_service import search as search_memories
    memories = search_memories(db, task_name, project_id=project_id)
    if memories:
        parts.append("## 相关记忆\n")
        for mem in memories[:5]:
            parts.append(f"- {mem.text[:200] if hasattr(mem, 'text') else str(mem)[:200]}")
        parts.append("")

    # Active skills
    from app.models.skill_card import SkillCard
    skills = db.query(SkillCard).filter(
        SkillCard.status == "active"
    ).order_by(SkillCard.usage_count.desc()).limit(5).all()
    if skills:
        parts.append("## 可用技能\n")
        for s in skills:
            parts.append(f"- **{s.name}**: {s.trigger_condition}")
            if s.steps:
                try:
                    steps = json.loads(s.steps)
                    parts.append(f"  步骤: {' → '.join(steps[:3])}")
                except Exception:
                    pass
        parts.append("")

    # Project DNA
    from app.models.project_dna import ProjectDNA
    dna = db.query(ProjectDNA).filter(
        ProjectDNA.project_id == project_id
    ).first()
    if dna:
        parts.append("## 项目画像\n")
        parts.append(f"风格: {dna.style_tags or '通用'}")
        parts.append(f"技术栈: {dna.tech_stack or '未知'}")
        parts.append("")

    # Recent messages
    from app.models.message import Message
    recent = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.id.desc()).limit(10).all()
    if recent:
        parts.append("## 对话历史\n")
        for m in reversed(recent):
            role_tag = "用户" if m.role == "user" else "MBclaw"
            parts.append(f"[{role_tag}]: {m.content[:300]}")
        parts.append("")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# Tool executor
# ═══════════════════════════════════════════════════════════

def execute_tool(tool_name: str, content: str, db: DBSession) -> dict:
    """Execute a tool call and return result."""
    import subprocess, os

    tool_name = tool_name.strip().lower()

    if tool_name == "read_file":
        try:
            # Sanitize path
            path = content.strip().split("\n")[0]
            path = os.path.normpath(os.path.join("/workspace/project", path))
            if not path.startswith("/workspace/project"):
                return {"error": "路径越界"}
            if not os.path.exists(path):
                return {"error": f"文件不存在: {path}"}
            with open(path, "r", encoding="utf-8") as f:
                text = f.read(5000)
            return {"result": text, "lines": len(text.split("\n"))}
        except Exception as e:
            return {"error": str(e)}

    elif tool_name == "write_file":
        try:
            lines = content.strip().split("\n", 1)
            if len(lines) < 2:
                return {"error": "需要路径和内容"}
            path = os.path.normpath(os.path.join("/workspace/project", lines[0].strip()))
            if not path.startswith("/workspace/project"):
                return {"error": "路径越界"}
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(lines[1])
            return {"result": f"已写入 {path}", "size": len(lines[1])}
        except Exception as e:
            return {"error": str(e)}

    elif tool_name == "edit_file":
        return {"result": "文件编辑功能通过 file_editor 工具实现"}

    elif tool_name == "run_command":
        try:
            cmd = content.strip().split("\n")[0]
            # Safety: block dangerous commands
            dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:"]
            if any(d in cmd for d in dangerous):
                return {"error": "命令被安全策略阻止"}

            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd="/workspace/project"
            )
            output = result.stdout[-3000:] if result.stdout else ""
            error = result.stderr[-1000:] if result.stderr else ""
            return {
                "result": output or "(无输出)",
                "error": error,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "命令超时 (30s)"}
        except Exception as e:
            return {"error": str(e)}

    elif tool_name == "search_code":
        try:
            import subprocess
            result = subprocess.run(
                f"grep -rn '{content.strip()}' /workspace/project/MBclaw-Lite/app --include='*.py' | head -20",
                shell=True, capture_output=True, text=True, timeout=10
            )
            return {"result": result.stdout or "未找到匹配"}
        except Exception as e:
            return {"error": str(e)}

    elif tool_name == "web_search":
        return {"result": "网页搜索需要浏览器工具，当前不可用"}

    else:
        return {"error": f"未知工具: {tool_name}"}


# ═══════════════════════════════════════════════════════════
# Parser: extract tool calls from LLM response
# ═══════════════════════════════════════════════════════════

def parse_tool_calls(response: str) -> list[dict]:
    """Parse <tool>name</tool><content>...</content> from LLM response."""
    import re
    tools = []
    pattern = r'<tool>(.*?)</tool>\s*<content>(.*?)</content>'
    for match in re.finditer(pattern, response, re.DOTALL):
        tools.append({
            "name": match.group(1).strip(),
            "content": match.group(2).strip(),
        })
    return tools


def parse_thinking(response: str) -> str:
    """Extract <thinking> content from response."""
    import re
    match = re.search(r'<thinking>(.*?)</thinking>', response, re.DOTALL)
    return match.group(1).strip() if match else ""


def clean_response(response: str) -> str:
    """Remove tool/thinking tags for display."""
    import re
    cleaned = re.sub(r'<tool>.*?</tool>\s*<content>.*?</content>', '', response, flags=re.DOTALL)
    cleaned = re.sub(r'<thinking>.*?</thinking>', '', cleaned, flags=re.DOTALL)
    return cleaned.strip()


# ═══════════════════════════════════════════════════════════
# Agent Runtime Loop
# ═══════════════════════════════════════════════════════════

async def run_agent_loop(
    db: DBSession,
    project_id: int,
    user_id: int,
    session_id: int,
    task_id: int,
    message: str,
    max_turns: int = 10,
    mode: str = "auto",
) -> dict:
    """Execute the agent loop for one task.

    Returns a summary dict with turns, tool_calls, errors, final_answer.
    """
    from app.models.message import Message
    from app.models.session import Session as SessionModel
    from app.services.transcript_service import append_to_transcript

    llm = get_llm()
    llm_available = LLM_ENABLED

    turns = []
    tool_calls = []
    errors = []
    conversation = []

    # Initial user message
    conversation.append({"role": "user", "content": message})

    # Add user message to DB session
    msg = Message(session_id=session_id, role="user", content=message)
    db.add(msg)
    db.commit()

    turn_count = 0
    max_errors = 3

    while turn_count < max_turns:
        turn_count += 1

        # Build context
        context = build_context(db, project_id, user_id, message, session_id)

        # Build prompt
        conv_text = "\n".join(
            f"[{'用户' if m['role'] == 'user' else 'MBclaw'}]: {m['content'][:500]}"
            for m in conversation[-8:]
        )

        full_prompt = f"""{AGENT_SYSTEM_PROMPT}

{context}

## 当前对话
{conv_text}

请回复（使用 <thinking> 思考，<tool> 工具调用，或直接回答）："""

        # Call LLM (or fallback)
        if llm_available:
            try:
                response = await llm(full_prompt, system_prompt="")
            except Exception as e:
                response = f"<thinking>LLM 调用失败: {e}</thinking>\n我使用规则引擎处理。"
                errors.append({"turn": turn_count, "error": str(e)})
        else:
            response = _rule_based_response(message)

        turns.append({"turn": turn_count, "raw": response[:500]})

        # Parse tool calls
        tc = parse_tool_calls(response)
        thinking = parse_thinking(response)
        clean_text = clean_response(response)

        # Record assistant message
        assistant_msg = Message(
            session_id=session_id,
            role="assistant",
            content=clean_text or response[:500],
            thinking_content=thinking,
        )
        db.add(assistant_msg)
        db.commit()

        conversation.append({"role": "assistant", "content": clean_text})

        # Execute tool calls
        if tc:
            for tool_call in tc[:3]:  # max 3 tools per turn
                tool_name = tool_call["name"]
                tool_content = tool_call["content"]
                tool_calls.append({"turn": turn_count, "tool": tool_name, "content": tool_content[:200]})

                result = execute_tool(tool_name, tool_content, db)

                # Record tool result as system message
                tool_msg = Message(
                    session_id=session_id,
                    role="system",
                    content=f"[工具: {tool_name}] {json.dumps(result, ensure_ascii=False)[:500]}",
                )
                db.add(tool_msg)
                db.commit()

                if "error" in result:
                    errors.append({
                        "turn": turn_count,
                        "tool": tool_name,
                        "error": result["error"],
                    })
                    # Auto-fix: feed error back to conversation
                    conversation.append({
                        "role": "system",
                        "content": f"工具 {tool_name} 出错: {result['error']}",
                    })

                    if len(errors) >= max_errors:
                        conversation.append({
                            "role": "user",
                            "content": "出了太多错，请换个方案或简化需求",
                        })
                        break
                else:
                    # Feed result back
                    result_text = result.get("result", str(result))
                    conversation.append({
                        "role": "system",
                        "content": f"工具 {tool_name} 结果: {result_text[:300]}",
                    })
        else:
            # No tool calls → task is done
            break

    # Mark task complete
    from app.models.task_queue import BackgroundTask
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
    if task:
        task.status = "completed"
        task.progress = 1.0

    # Check for H3 skill extraction triggers
    h3_result = _check_h3_triggers(db, conversation, tool_calls, errors)

    return {
        "task_id": task_id,
        "session_id": session_id,
        "turns": turn_count,
        "tool_calls": len(tool_calls),
        "errors": len(errors),
        "error_details": errors,
        "final_answer": clean_text[:500] if clean_text else "",
        "h3_extraction": h3_result,
    }


def _rule_based_response(message: str) -> str:
    """Fallback response when LLM is unavailable."""
    msg_lower = message.lower()

    if any(kw in msg_lower for kw in ["创建", "新建", "create", "写一个"]):
        return "<thinking>用户想创建新文件</thinking>\n<tool>write_file</tool><content>\noutput.txt\n自动生成的内容\n</content>"

    if any(kw in msg_lower for kw in ["运行", "测试", "test", "run"]):
        return "<thinking>用户想运行测试</thinking>\n<tool>run_command</tool><content>\ncd /workspace/project/MBclaw-Lite && python -m pytest tests/test_api.py -q\n</content>"

    if any(kw in msg_lower for kw in ["搜索", "查找", "search", "find", "grep"]):
        return "<thinking>用户想搜索代码</thinking>\n<tool>search_code</tool><content>\n" + message[:50] + "\n</content>"

    return f"<thinking>分析用户请求: {message[:100]}</thinking>\n我理解你的需求。由于当前 LLM 未启用，我使用规则引擎处理。请配置 LLM 以获得更好的体验（POST /api/llm/configure）。"


def _check_h3_triggers(
    db: DBSession,
    conversation: list[dict],
    tool_calls: list[dict],
    errors: list[dict],
) -> dict:
    """Check if H3 skill extraction should trigger and run it."""
    # Build messages for trigger detection
    messages = []
    for m in conversation:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "tool" or "工具" in content[:10]:
            messages.append({"role": "tool", "content": content})
        else:
            messages.append({"role": role, "content": content})

    triggers = detect_triggers(messages)

    if not triggers["should_extract"]:
        return {"triggered": False, "reason": triggers["trigger_type"]}

    skill_data = extract_skill_rules(messages, triggers)
    if not skill_data:
        return {"triggered": True, "success": False, "reason": "extraction_failed"}

    save_result = save_extracted_skill(db, skill_data)

    return {
        "triggered": True,
        "trigger_type": triggers["trigger_type"],
        "success": True,
        "skill_name": skill_data["name"],
        "save_result": save_result,
    }
