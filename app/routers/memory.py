from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from app.database import get_db
from app.models.project import Project
from app.services.memory_service import (
    read_memory_md, write_memory_md, read_daily_notes,
    append_daily_note, read_dreams, dream,
)
from app.schemas.skill_card import BatchMemoryRequest, MemoryEntryWrite
from app.services.memory_store import get_memory_store, reset_memory_store

router = APIRouter(prefix="/api/projects/{project_id}/memory", tags=["memory"])


class MemoryWrite(BaseModel):
    content: str


class DailyNote(BaseModel):
    content: str


class DreamOut(BaseModel):
    candidates: int
    promoted: int


def _get_project(project_id: int, db: DBSession) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ---- Tier 1: MEMORY.md (legacy raw content API) ----

@router.get("/durable")
def get_durable_memory(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    content = read_memory_md(project.name)
    return {"project": project.name, "content": content}


@router.put("/durable")
def set_durable_memory(project_id: int, data: MemoryWrite, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    write_memory_md(project.name, data.content)
    return {"project": project.name, "status": "saved"}


# ---- Hermes H1: MemoryStore managed memory (snapshot + budget + batch) ----

@router.get("/store")
def get_memory_store_state(project_id: int, db: DBSession = Depends(get_db)):
    """H1a: Full memory store state including live entries + frozen snapshot."""
    _get_project(project_id, db)
    store = get_memory_store()
    if not store.memory_entries and not store.user_entries:
        store.load_from_disk()
    return store.get_full_state()


@router.get("/store/entries")
def get_memory_entries(project_id: int, target: str = "memory", db: DBSession = Depends(get_db)):
    """H1a: Get entries as a list for the given target (memory/user)."""
    _get_project(project_id, db)
    store = get_memory_store()
    if not store.memory_entries and not store.user_entries:
        store.load_from_disk()
    return {"target": target, "entries": store.get_entries(target)}


@router.get("/store/snapshot")
def get_memory_snapshot(project_id: int, target: str = "memory", db: DBSession = Depends(get_db)):
    """H1a: Get the frozen system-prompt snapshot (session-start state)."""
    _get_project(project_id, db)
    store = get_memory_store()
    if not store._system_prompt_snapshot.get(target):
        store.load_from_disk()
    return {"target": target, "snapshot": store.format_for_system_prompt(target)}


@router.post("/store/entry")
def add_memory_entry(project_id: int, data: MemoryEntryWrite, db: DBSession = Depends(get_db)):
    """H1b: Add a single entry with char budget enforcement."""
    _get_project(project_id, db)
    store = get_memory_store()
    if not store.memory_entries and not store.user_entries:
        store.load_from_disk()

    # H6: drift check
    drift = store._pre_mutation_check()
    if drift:
        return drift

    result = store.add(data.target, data.entry)
    return result


@router.post("/store/batch")
def batch_memory(project_id: int, data: BatchMemoryRequest, db: DBSession = Depends(get_db)):
    """H1c: Atomic batch [remove, replace, add] with final-state budget check."""
    _get_project(project_id, db)
    store = get_memory_store()
    if not store.memory_entries and not store.user_entries:
        store.load_from_disk()

    # H6: drift check
    drift = store._pre_mutation_check()
    if drift:
        return drift

    result = store.apply_batch(data.target, data.operations)
    return result


@router.delete("/store/entry")
def remove_memory_entry(project_id: int, target: str, entry: str, db: DBSession = Depends(get_db)):
    """Remove a single entry."""
    _get_project(project_id, db)
    store = get_memory_store()
    if not store.memory_entries and not store.user_entries:
        store.load_from_disk()

    drift = store._pre_mutation_check()
    if drift:
        return drift

    return store.remove(target, entry)


@router.post("/store/reset")
def reset_store(project_id: int, db: DBSession = Depends(get_db)):
    """Reset the memory store (force reload from disk on next use)."""
    _get_project(project_id, db)
    reset_memory_store()
    return {"ok": True, "message": "MemoryStore 已重置"}


# ---- Tier 2: Daily Notes ----

@router.get("/daily")
def get_daily_notes(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    content = read_daily_notes(project.name)
    return {"project": project.name, "content": content}


@router.post("/daily")
def add_daily_note(project_id: int, data: DailyNote, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    append_daily_note(project.name, data.content)
    return {"project": project.name, "status": "appended"}


# ---- Tier 3: Dreams ----

@router.get("/dreams")
def get_dreams(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    content = read_dreams(project.name)
    return {"project": project.name, "content": content}


@router.post("/dream", response_model=DreamOut)
def run_dream(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    result = dream(db, project)
    db.commit()
    return result
