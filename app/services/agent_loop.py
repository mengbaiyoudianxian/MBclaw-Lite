"""Project 7+4+10: Agent Loop — the core runtime.

Ties together:
  - Message priority (Project 7): new message interrupts old task
  - Task queue (Project 7): suspend/resume/background
  - Context injection: SessionBootstrap auto-retrieves history
  - Auto mode (Project 4): decision engine when user says "全自动"
  - Dual-key (Project 5): maker+reviewer orchestration (stub)
  - Sub-agent coordination (Project 10): shared channel (stub)

Architecture (inspired by OpenClaw, independently implemented):
  1. Check message queue for new user message → interrupt if new topic
  2. Inject historical context from SessionBootstrap
  3. Process task (or resume from checkpoint)
  4. On completion → classify + extract skills (H3 stub)
"""

import json
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session as DBSession

from app.services.task_queue import (
    create_task, get_active_task, get_pending_tasks,
    activate_task, suspend_task, resume_task, complete_task, fail_task,
    update_progress, get_task_summary,
)
from app.services.message_priority import decide_interrupt
from app.services.session_bootstrap import bootstrap_session_context


class AgentLoop:
    """Single-project agent loop. Manages task lifecycle for one project."""

    def __init__(self, db: DBSession, project_id: int):
        self.db = db
        self.project_id = project_id

    # ── message handling ───────────────────────────────────

    def on_user_message(self, session_id: int, message: str,
                        task_name: str = "") -> dict[str, Any]:
        """Called when user sends a message. Decides interrupt/continue.

        Returns instructions for the caller:
          {action: "continue"|"interrupt", task_id, checkpoint, ...}
        """
        active = get_active_task(self.db, self.project_id)

        if active:
            decision = decide_interrupt(active.name, message)
            if decision["interrupt"]:
                checkpoint = {
                    "task_id": active.id,
                    "session_id": active.session_id,
                    "progress": active.progress,
                    "tool_call_count": active.tool_call_count,
                    "timestamp": datetime.now().isoformat(),
                }
                suspend_task(self.db, active.id, checkpoint)
                new_task = create_task(
                    self.db, self.project_id, task_name or _truncate(message, 60),
                    session_id=session_id,
                    priority=active.priority + 1,  # new message = higher priority
                )
                activate_task(self.db, new_task.id)
                return {
                    "action": "interrupt",
                    "suspended_task_id": active.id,
                    "new_task_id": new_task.id,
                    "checkpoint": checkpoint,
                    "reason": decision["reason"],
                }
            else:
                return {"action": "continue", "task_id": active.id,
                        "reason": decision["reason"]}

        # No active task → create new
        task = create_task(
            self.db, self.project_id,
            task_name or _truncate(message, 60),
            session_id=session_id,
        )
        activate_task(self.db, task.id)
        return {"action": "new", "task_id": task.id}

    # ── task lifecycle ─────────────────────────────────────

    def complete_current_task(self) -> dict:
        active = get_active_task(self.db, self.project_id)
        if not active:
            return {"error": "no_active_task"}
        complete_task(self.db, active.id)

        # Auto-resume next suspended task
        pending = get_pending_tasks(self.db, self.project_id)
        next_task_id = None
        if pending:
            next_task = pending[0]
            resume_task(self.db, next_task.id)
            next_task_id = next_task.id

        return {
            "completed_task_id": active.id,
            "resumed_task_id": next_task_id,
        }

    def fail_current_task(self, error: str) -> dict:
        active = get_active_task(self.db, self.project_id)
        if not active:
            return {"error": "no_active_task"}
        fail_task(self.db, active.id, error)
        return {"failed_task_id": active.id, "error": error}

    # ── progress tracking ──────────────────────────────────

    def report_progress(self, task_id: int, progress: float,
                        tool_call_count: int = 0) -> dict:
        task = update_progress(self.db, task_id, progress, tool_call_count)
        return {
            "task_id": task_id, "progress": task.progress if task else 0,
            "status": task.status if task else "unknown",
        }

    # ── context injection ──────────────────────────────────

    def inject_context(self, session) -> str:
        """Auto-inject historical context for the active session."""
        return bootstrap_session_context(self.db, session, session.title)

    # ── summary ────────────────────────────────────────────

    def get_status(self) -> dict:
        return get_task_summary(self.db, self.project_id)


def _truncate(s: str, n: int) -> str:
    return s[:n] + ("..." if len(s) > n else "")
