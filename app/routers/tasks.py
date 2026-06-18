"""Project 7+4: Task queue + Agent Loop management API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.services.task_queue import (
    create_task, get_active_task, get_pending_tasks,
    activate_task, suspend_task, resume_task,
    complete_task, fail_task, update_progress, get_task_summary,
)
from app.services.agent_loop import AgentLoop

router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])


@router.get("")
def list_tasks(project_id: int, db: DBSession = Depends(get_db)):
    return get_task_summary(db, project_id)


@router.post("", status_code=201)
def new_task(project_id: int, name: str, session_id: int = 0,
             priority: int = 0, db: DBSession = Depends(get_db)):
    sid = session_id if session_id else None
    task = create_task(db, project_id, name, session_id=sid, priority=priority)
    return {"id": task.id, "name": task.name, "status": task.status}


@router.post("/{task_id}/activate")
def activate(project_id: int, task_id: int, db: DBSession = Depends(get_db)):
    task = activate_task(db, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"id": task.id, "status": task.status}


@router.post("/{task_id}/suspend")
def suspend(project_id: int, task_id: int, db: DBSession = Depends(get_db)):
    task = suspend_task(db, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"id": task.id, "status": task.status}


@router.post("/{task_id}/resume")
def resume(project_id: int, task_id: int, db: DBSession = Depends(get_db)):
    task = resume_task(db, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"id": task.id, "status": task.status}


@router.post("/{task_id}/complete")
def complete(project_id: int, task_id: int, db: DBSession = Depends(get_db)):
    task = complete_task(db, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"id": task.id, "status": task.status}


@router.post("/{task_id}/fail")
def fail(project_id: int, task_id: int, error: str, db: DBSession = Depends(get_db)):
    task = fail_task(db, task_id, error)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"id": task.id, "status": task.status, "error": error}


@router.post("/{task_id}/progress")
def progress(project_id: int, task_id: int, progress: float = 0.0,
             tool_call_count: int = 0, db: DBSession = Depends(get_db)):
    task = update_progress(db, task_id, progress, tool_call_count)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"id": task.id, "status": task.status, "progress": task.progress}


@router.post("/interrupt")
def interrupt_for_message(project_id: int, session_id: int, message: str,
                          task_name: str = "", db: DBSession = Depends(get_db)):
    """Called when user sends a message: decide interrupt/continue."""
    loop = AgentLoop(db, project_id)
    result = loop.on_user_message(session_id, message, task_name)
    return result


@router.get("/active")
def active_task(project_id: int, db: DBSession = Depends(get_db)):
    task = get_active_task(db, project_id)
    if not task:
        return {"active": False}
    return {
        "active": True,
        "id": task.id, "name": task.name, "status": task.status,
        "progress": task.progress, "tool_call_count": task.tool_call_count,
    }


@router.get("/pending")
def pending_tasks(project_id: int, db: DBSession = Depends(get_db)):
    tasks = get_pending_tasks(db, project_id)
    return [{"id": t.id, "name": t.name, "status": t.status, "priority": t.priority}
            for t in tasks]
