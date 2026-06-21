"""Tool Registry — register, search, and execute tools. Derived from tool_service.py."""

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.db import Base


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    tags: Mapped[str] = mapped_column(String(500), nullable=False, default="[]")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    examples: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


BUILTIN_TOOLS = [
    {"name": "read_file", "summary": "读取文件内容", "tags": '["file","io"]',
     "description": "读取指定路径的文件，返回文本内容。支持绝对路径。", "examples": '["read_file /tmp/test.txt"]'},
    {"name": "write_file", "summary": "写入文件", "tags": '["file","io"]',
     "description": "将内容写入指定路径。会自动创建父目录。", "examples": '["write_file /tmp/out.txt\\ncontent"]'},
    {"name": "run_command", "summary": "执行Shell命令", "tags": '["system","shell"]',
     "description": "执行shell命令并返回结果。超时30秒。", "examples": '["run_command ls -la"]'},
    {"name": "search_memory", "summary": "搜索记忆库", "tags": '["memory","search"]',
     "description": "在MBclaw记忆库中搜索相关内容。", "examples": '["search_memory 全文检索方案"]'},
    {"name": "web_search", "summary": "网络搜索", "tags": '["search","web"]',
     "description": "搜索网络获取最新信息。需要配置搜索API。", "examples": '["web_search Python3.14新特性"]'},
    {"name": "edit_file", "summary": "编辑文件", "tags": '["file","edit"]',
     "description": "替换文件中的指定文本。old_str必须精确匹配。", "examples": '["edit_file /tmp/x.py\\nold\\nnew"]'},
]


def seed_tools(db: Session):
    """Ensure built-in tools exist."""
    for cfg in BUILTIN_TOOLS:
        existing = db.query(Tool).filter(Tool.name == cfg["name"]).first()
        if not existing:
            db.add(Tool(**cfg))
    db.commit()


def list_tools(db: Session, tag: str = None) -> list[dict]:
    """L1/L2: list all tools, optionally filtered by tag."""
    seed_tools(db)
    query = db.query(Tool).order_by(Tool.usage_count.desc())
    if tag:
        query = query.filter(Tool.tags.contains(tag))
    tools = query.all()
    return [{"id": t.id, "name": t.name, "summary": t.summary,
             "tags": json.loads(t.tags), "usage_count": t.usage_count} for t in tools]


def get_tool(db: Session, tool_id: int) -> dict | None:
    """L3: full tool detail."""
    t = db.query(Tool).filter(Tool.id == tool_id).first()
    if not t:
        return None
    return {"id": t.id, "name": t.name, "summary": t.summary,
            "description": t.description, "tags": json.loads(t.tags),
            "examples": json.loads(t.examples), "usage_count": t.usage_count}


def bump_usage(db: Session, tool_name: str):
    """Increment usage counter for a tool."""
    t = db.query(Tool).filter(Tool.name == tool_name).first()
    if t:
        t.usage_count += 1
        db.commit()


def execute(db: Session, tool_name: str, content: str) -> str:
    """Execute a built-in tool. Returns result string."""
    import os, subprocess
    try:
        if tool_name == "read_file":
            path = content.strip()
            if not os.path.isabs(path):
                return f"错误: 需要绝对路径"
            if not os.path.exists(path):
                return f"文件不存在: {path}"
            with open(path) as f:
                text = f.read()
            return text[:3000] + (f"\n...(截断,共{len(text)}字)" if len(text) > 3000 else "")

        elif tool_name == "write_file":
            parts = content.split('\n', 1)
            if len(parts) < 2:
                return "错误: 需要 path 和 content"
            path, body = parts[0].strip(), parts[1]
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w') as f:
                f.write(body)
            return f"写入成功: {path}"

        elif tool_name == "run_command":
            r = subprocess.run(content, shell=True, capture_output=True, text=True, timeout=30)
            out = r.stdout + (f"\n[stderr]:{r.stderr}" if r.stderr else "")
            return out[:2000] or f"(退出码:{r.returncode})"

        elif tool_name == "edit_file":
            parts = content.split('\n---\n')
            if len(parts) < 3:
                return "错误: 需要 path, old_str, new_str"
            path, old, new = parts[0].strip(), parts[1], parts[2]
            with open(path) as f:
                text = f.read()
            if old not in text:
                return "未找到要替换的文本"
            with open(path, 'w') as f:
                f.write(text.replace(old, new, 1))
            return f"编辑成功: {path}"

        elif tool_name == "search_memory":
            from app.memory import MemoryRepo
            hits = MemoryRepo(db).query(content, top_n=5)
            return "\n".join(f"- [#{h.session_id}] {h.summary[:200]}" for h in hits) or "未找到"

        elif tool_name == "web_search":
            return f"[web_search] 查询: {content[:100]} — 需要配置搜索API"

        else:
            return f"未知工具: {tool_name}"
    except Exception as e:
        return f"工具执行错误: {e}"
