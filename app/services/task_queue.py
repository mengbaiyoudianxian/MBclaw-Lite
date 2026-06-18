"""Project 7: Task Queue — suspend/resume/background execution.

Key difference from OpenClaw: new user message = new task by default,
old task suspends to background (no /stop command needed).
"""

import json
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.task_queue import BackgroundTask


def create_task(db: DBSession, project_id: int, name: str, session_id: int | None = None,
                priority: int = 0) -> BackgroundTask:
    """Create a new task in the background queue."""
    now = datetime.now().isoformat()
    task = BackgroundTask(
        project_id=project_id,
        session_id=session_id,
        name=name,
        status="pending",
        priority=priority,
        progress=0.0,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_active_task(db: DBSession, project_id: int) -> BackgroundTask | None:
    """Get the currently active task for a project."""
    return db.query(BackgroundTask).filter(
        BackgroundTask.project_id == project_id,
        BackgroundTask.status == "active",
    ).first()


def get_pending_tasks(db: DBSession, project_id: int) -> list[BackgroundTask]:
    """Get all pending/suspended tasks ordered by priority."""
    return db.query(BackgroundTask).filter(
        BackgroundTask.project_id == project_id,
        BackgroundTask.status.in_(["pending", "suspended"]),
    ).order_by(BackgroundTask.priority.desc(), BackgroundTask.created_at.asc()).all()


def activate_task(db: DBSession, task_id: int) -> BackgroundTask:
    """Mark a task as active (running now)."""
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
    if task:
        task.status = "active"
        task.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(task)
    return task


def suspend_task(db: DBSession, task_id: int, checkpoint: dict | None = None) -> BackgroundTask:
    """Suspend a running task, saving checkpoint for later resumption."""
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
    if not task:
        return None
    task.status = "suspended"
    if checkpoint:
        task.checkpoint_json = json.dumps(checkpoint, ensure_ascii=False)
    task.updated_at = datetime.now().isoformat()
    db.commit()
    db.refresh(task)
    return task


def resume_task(db: DBSession, task_id: int) -> BackgroundTask:
    """Resume a suspended task."""
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
    if not task:
        return None
    task.status = "active"
    task.updated_at = datetime.now().isoformat()
    db.commit()
    db.refresh(task)
    return task


def complete_task(db: DBSession, task_id: int) -> BackgroundTask:
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
    if task:
        task.status = "completed"
        task.progress = 1.0
        task.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(task)
    return task


def fail_task(db: DBSession, task_id: int, error: str) -> BackgroundTask:
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
    if task:
        task.status = "failed"
        task.error_message = error
        task.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(task)
    return task


def update_progress(db: DBSession, task_id: int, progress: float,
                    tool_call_count: int = 0) -> BackgroundTask:
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
    if task:
        task.progress = min(1.0, max(0.0, progress))
        task.tool_call_count += tool_call_count
        task.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(task)
    return task


def get_task_summary(db: DBSession, project_id: int) -> dict:
    """Summary of all tasks for a project."""
    tasks = db.query(BackgroundTask).filter(
        BackgroundTask.project_id == project_id
    ).all()
    return {
        "total": len(tasks),
        "active": sum(1 for t in tasks if t.status == "active"),
        "pending": sum(1 for t in tasks if t.status == "pending"),
        "suspended": sum(1 for t in tasks if t.status == "suspended"),
        "completed": sum(1 for t in tasks if t.status == "completed"),
        "failed": sum(1 for t in tasks if t.status == "failed"),
        "tasks": [{
            "id": t.id, "name": t.name, "status": t.status,
            "priority": t.priority, "progress": t.progress,
            "session_id": t.session_id,
        } for t in tasks],
    }
