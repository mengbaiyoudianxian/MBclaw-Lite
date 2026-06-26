"""Phase1 models: RawMemory + MemoryNode (不动旧models.py)"""
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base
import uuid, time

def _ulid():
    ts = int(time.time() * 1000)
    rand = uuid.uuid4().hex[:10]
    return f"{ts:013d}-{rand}"

def _utcnow():
    return datetime.now(timezone.utc)

class RawMemory(Base):
    __tablename__ = "raw_memories"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default=_ulid)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    reasoning_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    is_archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

class MemoryNode(Base):
    __tablename__ = "memory_nodes"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default=_ulid)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding: Mapped[bytes | None] = mapped_column(nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    decay_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_decay_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

from sqlalchemy import String, Float, ForeignKey, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

class MemoryEdge(Base):
    __tablename__ = 'memory_edges'
    source_id: Mapped[str] = mapped_column(String(30), ForeignKey('memory_nodes.id'), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(30), ForeignKey('memory_nodes.id'), primary_key=True)
    relation_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default=_ulid)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    related_node_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
