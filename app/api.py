"""T5.1 — REST API router (5 endpoints).

Never imports Summary/Keyword/Experience directly (铁律 #5 + CI guard).
"""

import fcntl
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm import LLMClient, LLMError, get_llm
from app.memory import MemoryRepo
from app.models import Message, Session as SessionModel  # orchestrator-only
from app.pipeline import close_session
from app.agent import agent_run
from app.providers import list_providers
from app.tools import execute as tool_execute, get_tool, list_tools, search_tools

router = APIRouter()

# ── JSONL transcript helper ─────────────────────────────────

TRANSCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "transcripts")


def _append_transcript(sid: int, msg: dict) -> None:
    """Thread-safe append of a single message to a session transcript JSONL."""
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    path = os.path.join(TRANSCRIPT_DIR, f"session-{sid}.jsonl")
    line = json.dumps(msg, ensure_ascii=False) + "\n"
    with open(path, "a") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        try:
            fp.write(line)
        finally:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)

# ── request / response schemas ──────────────────────────────

class CreateSessionRequest(BaseModel):
    title: str = ""


class SessionResponse(BaseModel):
    session_id: int
    title: str
    status: str
    injected_system_message: dict | None = None


class AddMessageRequest(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime


class CloseResponse(BaseModel):
    session_id: int
    status: str
    summary: str
    keywords: list[dict]
    experiences: list[dict]
    stats: dict


class SearchHit(BaseModel):
    session_id: int
    summary: str
    keywords: list[str]
    score: float


# ── endpoints ───────────────────────────────────────────────


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    req: CreateSessionRequest,
    db: Session = Depends(get_db),
):
    """Create a new session with optional memory injection."""
    session = SessionModel(title=req.title, status="active")
    db.add(session)
    db.commit()
    db.refresh(session)

    injected = None
    repo = MemoryRepo(db)
    rendered = repo.render_injection_for_new_session(exclude_sid=session.id)
    if rendered:
        injected = {"role": "system", "content": rendered}
        db.add(Message(session_id=session.id, role="system", content=rendered))
        db.commit()

    return SessionResponse(
        session_id=session.id,
        title=session.title,
        status=session.status,
        injected_system_message=injected,
    )


@router.post("/sessions/{sid}/messages", response_model=MessageResponse)
def add_message(
    sid: int,
    req: AddMessageRequest,
    db: Session = Depends(get_db),
):
    """Append a message to a session and the JSONL transcript."""
    session = db.query(SessionModel).filter(SessionModel.id == sid).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == "closed":
        raise HTTPException(400, "Session is closed")

    msg = Message(session_id=sid, role=req.role, content=req.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    _append_transcript(sid, {
        "id": msg.id, "session_id": sid, "role": msg.role,
        "content": msg.content, "created_at": msg.created_at.isoformat(),
    })

    return MessageResponse(
        id=msg.id, session_id=msg.session_id,
        role=msg.role, content=msg.content, created_at=msg.created_at,
    )


@router.post("/sessions/{sid}/close", response_model=CloseResponse)
def close(
    sid: int,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    """Close a session: summarise, persist memory, mark closed."""
    try:
        result = close_session(db, sid, llm)
    except LLMError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return CloseResponse(**result)


@router.get("/sessions/{sid}/messages", response_model=list[MessageResponse])
def list_messages(
    sid: int,
    db: Session = Depends(get_db),
):
    """Return all messages for a session in chronological order."""
    msgs = db.query(Message).filter(
        Message.session_id == sid
    ).order_by(Message.created_at).all()
    return [
        MessageResponse(
            id=m.id, session_id=m.session_id,
            role=m.role, content=m.content, created_at=m.created_at,
        )
        for m in msgs
    ]


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Full-text + keyword search across past session summaries."""
    repo = MemoryRepo(db)
    hits = repo.query(q, top_n=limit)
    return [SearchHit(
        session_id=h.session_id, summary=h.summary,
        keywords=h.keywords, score=h.score,
    ) for h in hits]


# ── agent ──────────────────────────────────────────────────

class AgentRequest(BaseModel):
    message: str
    max_turns: int = 5


@router.post("/agent/run")
def agent_chat(req: AgentRequest, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    """Run agent loop: context → LLM → tools → response."""
    session = db.query(SessionModel).filter(SessionModel.status == "active").order_by(SessionModel.started_at.desc()).first()
    if not session:
        session = SessionModel(title="Agent Chat", status="active")
        db.add(session); db.commit(); db.refresh(session)
        record_session_created()
    try:
        return agent_run(db, session.id, req.message, llm, req.max_turns)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/agent/status")
def agent_status(db: Session = Depends(get_db)):
    """Current agent session info."""
    session = db.query(SessionModel).filter(SessionModel.status == "active").order_by(SessionModel.started_at.desc()).first()
    if not session:
        return {"active": False, "session_id": None, "message_count": 0}
    count = db.query(Message).filter(Message.session_id == session.id).count()
    return {"active": True, "session_id": session.id, "title": session.title, "message_count": count,
            "started_at": session.started_at.isoformat() if session.started_at else None}


# ── providers ───────────────────────────────────────────────

@router.get("/providers")
def get_providers(db: Session = Depends(get_db)):
    """List configured LLM providers with status."""
    return [p.model_dump() for p in list_providers(db)]


# ── tools ───────────────────────────────────────────────────

class ToolExecuteRequest(BaseModel):
    name: str
    content: str = ""


@router.get("/tools")
def get_tools(category: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    """L1/L2: list tools, optionally filtered by category or tag."""
    return list_tools(db, category, tag)


@router.get("/tools/search")
def search_tools_endpoint(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    """Search tools by name/description."""
    return search_tools(db, q)


@router.get("/tools/{tool_id}")
def get_tool_detail(tool_id: int, db: Session = Depends(get_db)):
    """L3: full tool detail."""
    t = get_tool(db, tool_id)
    if not t: raise HTTPException(404, "Tool not found")
    return t


@router.post("/tools/execute")
def execute_tool(req: ToolExecuteRequest, db: Session = Depends(get_db)):
    """Execute a tool and return the result."""
    from app.tools import bump_usage
    bump_usage(db, req.name)
    return {"name": req.name, "result": tool_execute(db, req.name, req.content)}


# ── Workspace (Memory System v1) ─────────────────────────────

from app.workspace.manager import WorkspaceManager


class CreateWorkspaceRequest(BaseModel):
    name: str
    topic: str = ""


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    topic: str
    created_at: str
    is_archived: int


@router.post("/workspace/create", response_model=WorkspaceResponse)
def create_workspace(req: CreateWorkspaceRequest, db: Session = Depends(get_db)):
    """创建新工作区。"""
    mgr = WorkspaceManager(db)
    try:
        ws = mgr.create(req.name, req.topic)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return WorkspaceResponse(
        id=ws.id, name=ws.name, topic=ws.topic,
        created_at=str(ws.created_at), is_archived=ws.is_archived,
    )


@router.get("/workspace/list", response_model=list[WorkspaceResponse])
def list_workspaces(db: Session = Depends(get_db)):
    """列出活跃工作区。"""
    mgr = WorkspaceManager(db)
    return [
        WorkspaceResponse(
            id=w.id, name=w.name, topic=w.topic,
            created_at=str(w.created_at), is_archived=w.is_archived,
        )
        for w in mgr.list_active()
    ]


@router.post("/workspace/{ws_id}/archive")
def archive_workspace(ws_id: int, db: Session = Depends(get_db)):
    """归档工作区。"""
    mgr = WorkspaceManager(db)
    try:
        mgr.archive(ws_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "id": ws_id}

# ── Memory System v1 新端点 ──

class CloseV2Response(BaseModel):
    session_id: int
    status: str
    old_pipeline: dict
    memory_v2: dict

@router.post("/session/{sid}/close-v2", response_model=CloseV2Response)
def close_session_v2(sid: int, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
    """关闭会话 + v2 memory encoder (新旧管线并行)."""
    from app.pipeline import close_session as _old_close, _write_memory_v2
    old_result = _old_close(db, sid, llm)
    v2_result = _write_memory_v2(db, sid, llm)
    return CloseV2Response(
        session_id=sid,
        status="closed",
        old_pipeline=old_result,
        memory_v2=v2_result,
    )


class MemorySearchResponse(BaseModel):
    results: list[dict]
    query: str
    workspace_id: int

@router.get("/memory/search", response_model=MemorySearchResponse)
def search_memory_v2(q: str = "", ws: int = 1, limit: int = 5, db: Session = Depends(get_db)):
    """v2 记忆检索 (embedding + FTS5 + failure boost)."""
    from app.memory import search_v2_memory
    results = search_v2_memory(db, ws, q, limit)
    return MemorySearchResponse(results=results, query=q, workspace_id=ws)


@router.get("/memory/failures")
def list_failures(ws: int = 1, db: Session = Depends(get_db)):
    """列出 workspace 的失败记忆."""
    from app.models import Memory
    import json as _json
    failures = db.query(Memory).filter(
        Memory.workspace_id == ws,
        Memory.type == "failure"
    ).order_by(Memory.importance_score.desc()).limit(20).all()
    return [
        {"id": f.id, "content": _json.loads(f.content_json) if f.content_json else {},
         "importance": f.importance_score, "usage": f.usage_count}
        for f in failures
    ]


@router.get("/workspace/{ws_id}/context")
def workspace_context(ws_id: int, q: str = "", db: Session = Depends(get_db)):
    """获取 workspace 注入上下文."""
    from app.context.builder import ContextBuilder
    builder = ContextBuilder(db)
    text, ids = builder.build(ws_id, q)
    return {"context": text, "used_memory_ids": ids, "workspace_id": ws_id}

# Phase1: Memory Search API
from pydantic import BaseModel as _PB

class MemorySearchRequest(_PB):
    query: str
    workspace_id: int = 1
    user_id: str = ''
    max_results: int = 5

class MemorySearchResponse(_PB):
    items: list[dict]
    warnings: list[dict]

@router.post('/memory/search', response_model=MemorySearchResponse)
def memory_search(req: MemorySearchRequest, db: Session = Depends(get_db)):
    from app.memory import search_phase1
    results = search_phase1(db, req.workspace_id, req.query, req.max_results)
    items = []
    warnings = []
    for r in results:
        items.append({
            'id': str(r.get('id','')),
            'layer': str(r.get('type','')),
            'summary': str(r.get('summary',''))[:100],
            'snippet': str(r.get('content',''))[:150],
            'relevance_score': float(r.get('score', 0)),
            'importance': float(r.get('importance', 0.5)),
        })
        if r.get('type') == 'failure' and float(r.get('score',0)) > 0.7:
            c = r.get('content', {})
            warnings.append({
                'level': 'strong',
                'message': 'History failure: ' + str(c.get('task','')) + ' - ' + str(c.get('lesson',''))
            })
    return MemorySearchResponse(items=items, warnings=warnings)

@router.get('/memory/failures')
def memory_failures(ws: int = 1, db: Session = Depends(get_db)):
    from app.models import Memory as _Mem
    j = __import__('json')
    failures = db.query(_Mem).filter(
        _Mem.workspace_id == ws, _Mem.type == 'failure'
    ).order_by(_Mem.importance_score.desc()).limit(20).all()
    return [{
        'id': f.id, 'summary': f.summary,
        'content': j.loads(f.content_json) if f.content_json else {},
        'importance': f.importance_score,
        'usage': f.usage_count or 0
    } for f in failures]
