import os
import json
import fcntl
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession

from app.config import DATA_DIR
from app.models.project import Project
from app.models.session import Session
from app.models.message import Message
from app.models.summary import Summary
from app.models.keyword import Keyword


def _memory_dir(project_name: str) -> str:
    path = os.path.join(DATA_DIR, "memory", project_name)
    os.makedirs(path, exist_ok=True)
    return path


def _safe_write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _safe_append(path: str, line: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def _safe_read(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return f.read()


# ---- Three-tier memory ----

def write_memory_md(project_name: str, content: str):
    """Tier 1: durable curated facts (MEMORY.md)."""
    path = os.path.join(_memory_dir(project_name), "MEMORY.md")
    _safe_write(path, content)


def read_memory_md(project_name: str) -> str:
    path = os.path.join(_memory_dir(project_name), "MEMORY.md")
    return _safe_read(path)


def append_daily_note(project_name: str, content: str):
    """Tier 2: daily working notes (YYYY-MM-DD.md)."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(_memory_dir(project_name), f"{today}.md")
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"## {timestamp}\n\n{content}\n"
    _safe_append(path, entry)


def read_daily_notes(project_name: str) -> str:
    """Read today + yesterday notes."""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    parts = []
    for day in (yesterday, today):
        path = os.path.join(_memory_dir(project_name), f"{day}.md")
        content = _safe_read(path)
        if content:
            parts.append(f"# {day}\n\n{content}")
    return "\n\n".join(parts)


def append_dream_entry(project_name: str, content: str):
    """Tier 3: consolidation diary (DREAMS.md)."""
    path = os.path.join(_memory_dir(project_name), "DREAMS.md")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"## {timestamp}\n\n{content}\n"
    _safe_append(path, entry)


def read_dreams(project_name: str) -> str:
    path = os.path.join(_memory_dir(project_name), "DREAMS.md")
    return _safe_read(path)


# ---- Memory Flush ----

def memory_flush(db: DBSession, session: Session) -> dict:
    """Save important context from a session before compaction."""
    project = session.project
    project_name = project.name

    messages = db.query(Message).filter(Message.session_id == session.id).order_by(Message.id).all()
    summary = db.query(Summary).filter(Summary.session_id == session.id).first()
    keywords = db.query(Keyword).filter(Keyword.session_id == session.id).all()

    daily_parts = [
        f"Session #{session.session_number}: {session.title or 'Untitled'}",
        f"Status: {session.status}",
    ]

    if summary:
        if summary.topic:
            daily_parts.append(f"Topic: {summary.topic}")
        if summary.conclusions:
            daily_parts.append(f"Conclusions: {summary.conclusions}")
        if summary.decisions:
            daily_parts.append(f"Decisions: {summary.decisions}")
        if summary.next_steps:
            daily_parts.append(f"Next Steps: {summary.next_steps}")

    if keywords:
        kw_list = ", ".join(f"{k.keyword}({k.weight})" for k in keywords[:10])
        daily_parts.append(f"Keywords: {kw_list}")

    if messages:
        last_msgs = messages[-6:]
        dialog = "\n".join(f"  [{m.role}]: {m.content[:200]}" for m in last_msgs)
        daily_parts.append(f"Recent dialog:\n{dialog}")

    daily_content = "\n".join(daily_parts)
    append_daily_note(project_name, daily_content)

    return {"daily_note": daily_content, "messages_count": len(messages)}


# ---- Dreaming (consolidation) ----

def dream(db: DBSession, project: Project) -> dict:
    """Background consolidation: score recent signals, promote qualified items to MEMORY.md."""
    project_name = project.name

    recent_window = (datetime.now() - timedelta(days=7)).isoformat()
    summaries = (
        db.query(Summary)
        .join(Summary.session)
        .filter(Summary.session.has(project_id=project.id))
        .filter(Summary.created_at >= recent_window)
        .all()
    )

    keywords = (
        db.query(Keyword)
        .filter(Keyword.project_id == project.id)
        .all()
    )

    candidates = []

    for s in summaries:
        if s.conclusions:
            candidates.append({"source": "conclusion", "text": s.conclusions, "session_id": s.session_id})
        if s.decisions:
            candidates.append({"source": "decision", "text": s.decisions, "session_id": s.session_id})

    kw_counter = {}
    for k in keywords:
        kw_counter[k.keyword] = kw_counter.get(k.keyword, 0) + k.weight

    recurring_kw = [kw for kw, score in kw_counter.items() if score >= 2.0]
    if recurring_kw:
        candidates.append({
            "source": "recurring_keywords",
            "text": f"Recurring topics: {', '.join(recurring_kw)}",
        })

    promoted = []
    for c in candidates:
        if len(c["text"]) > 20:
            promoted.append(c["text"])

    if promoted:
        dream_content = "## Consolidated Signals\n\n"
        for i, p in enumerate(promoted, 1):
            dream_content += f"{i}. {p}\n"
        append_dream_entry(project_name, dream_content)

        existing_memory = read_memory_md(project_name)
        if existing_memory:
            new_section = "\n\n## Consolidated (auto)\n\n" + "\n".join(f"- {p}" for p in promoted)
            if new_section not in existing_memory:
                write_memory_md(project_name, existing_memory + new_section)
        else:
            write_memory_md(project_name, "# Memory\n\n## Consolidated (auto)\n\n" + "\n".join(f"- {p}" for p in promoted))

    return {"candidates": len(candidates), "promoted": len(promoted)}
