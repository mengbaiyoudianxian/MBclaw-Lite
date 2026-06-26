"""T1.2 — ORM models for MBclaw Memory System v1.

7 tables: workspaces, sessions(+workspace_id), messages, summaries, keywords,
         experiences, memory(v2), tools, model_profiles.
No business methods.  All mutable state lives in MemoryRepo (T3.x).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Session ──────────────────────────────────────────────────

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("workspaces.id"), nullable=True, default=None)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


# ── Message ──────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


# ── Summary ──────────────────────────────────────────────────

class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


# ── Keyword ──────────────────────────────────────────────────

class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


# ── Experience ───────────────────────────────────────────────

class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_recalled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    recall_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

# ── Workspace (Memory System v1) ──────────────────────────────

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    is_archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ── Memory (Memory System v1 — 统一记忆表) ────────────────────

class Memory(Base):
    __tablename__ = "memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # episode/semantic/procedure/failure
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes | None] = mapped_column(nullable=True)  # float32 BLOB
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ── Tool ────────────────────────────────────────────────────

class Tool(Base):
    __tablename__ = "tools"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="utility")
    summary: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    tags: Mapped[str] = mapped_column(String(500), nullable=False, default="[]")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameters: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    examples: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# ── ModelProfile ────────────────────────────────────────────

class ModelProfile(Base):
    __tablename__ = "model_profiles"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_alias: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="openai")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_base: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    api_key_env: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    priority: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
