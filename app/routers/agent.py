"""Unified Agent Runtime router — Projects 4/5/7/10.

/api/projects/{id}/agent:
  POST /run         → execute agent loop for a task (Agent Runtime)
  POST /auto        → start full-auto mode (Project 4)
  POST /interrupt   → message interrupt (Project 7)
  POST /dual-key    → maker+reviewer cycle (Project 5)
  POST /sub-agent   → sub-agent coordination (Project 10)
  GET  /status      → loop + task status
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.services.agent_loop import AgentLoop
from app.services.auto_mode import get_auto_mode
from app.services.dual_key import DualKey, ReviewDecision
from app.services.sub_agent_coordinator import get_coordinator
from app.services.agent_runtime import run_agent_loop

router = APIRouter(prefix="/api/projects/{project_id}/agent", tags=["agent"])


# ── Project 7: Message interrupt ──────────────────────────

@router.post("/interrupt")
def interrupt(project_id: int, session_id: int, message: str,
              task_name: str = "", db: DBSession = Depends(get_db)):
    """User sent a message → decide interrupt/continue."""
    loop = AgentLoop(db, project_id)
    return loop.on_user_message(session_id, message, task_name)


@router.get("/status")
def agent_status(project_id: int, db: DBSession = Depends(get_db)):
    """Get agent loop status + task queue."""
    loop = AgentLoop(db, project_id)
    return loop.get_status()


# ── Project 4: Full Auto Mode ─────────────────────────────

@router.post("/auto")
def auto_mode(project_id: int, message: str, db: DBSession = Depends(get_db)):
    """Start or continue full-auto mode."""
    auto = get_auto_mode(project_id)
    if auto.is_auto_trigger(message):
        return auto.start()
    return {"mode": "auto", "status": "continue", "branches": len(auto.branches)}


@router.post("/auto/branch")
def auto_branch(project_id: int, name: str, approach: str,
                estimated_steps: int = 0):
    """Add a parallel solution branch."""
    auto = get_auto_mode(project_id)
    branch_id = auto.add_branch(name, approach, estimated_steps)
    if branch_id < 0:
        raise HTTPException(400, "Max parallel branch limit reached")
    return {"branch_id": branch_id, "name": name}


@router.patch("/auto/branch/{branch_id}")
def auto_branch_update(project_id: int, branch_id: int, status: str = "",
                       error_count: int = -1, result: str = ""):
    """Update branch status."""
    auto = get_auto_mode(project_id)
    kwargs = {}
    if status:
        kwargs["status"] = status
    if error_count >= 0:
        kwargs["error_count"] = error_count
    if result:
        kwargs["result"] = result
    if not auto.update_branch(branch_id, **kwargs):
        raise HTTPException(404, "Branch not found")
    return {"branch_id": branch_id, "updated": True}


@router.post("/auto/select")
def auto_select_best(project_id: int):
    """Auto-select best branch."""
    auto = get_auto_mode(project_id)
    best = auto.select_best()
    if best is None:
        raise HTTPException(400, "No branches available")
    return {"selected_branch": best, "summary": auto.summary()}


@router.get("/auto/status")
def auto_status(project_id: int):
    auto = get_auto_mode(project_id)
    return auto.summary()


# ── Project 5: Dual-Key Collaboration ─────────────────────

@router.post("/dual-key/start")
def dual_key_start(project_id: int, maker_key: str = "key1",
                   reviewer_key: str = "key2"):
    """Initialize dual-key session."""
    dk = DualKey(maker_key, reviewer_key)
    _dual_keys[project_id] = dk
    return {"project_id": project_id, "maker": maker_key, "reviewer": reviewer_key}


@router.post("/dual-key/produce")
def dual_key_produce(project_id: int, content: str, artifact_type: str = "code"):
    dk = _dual_keys.get(project_id)
    if not dk:
        raise HTTPException(400, "Dual-key session not started. Call /dual-key/start first.")
    return dk.maker_produce(content, artifact_type)


@router.post("/dual-key/review")
def dual_key_review(project_id: int, cycle_number: int, decision: str,
                    score: int = 0, feedback: str = "", suggested_fix: str = ""):
    dk = _dual_keys.get(project_id)
    if not dk:
        raise HTTPException(400, "Dual-key session not started.")
    try:
        dec = ReviewDecision(decision)
    except ValueError:
        raise HTTPException(400, f"Invalid decision. Must be one of: {[d.value for d in ReviewDecision]}")
    return dk.reviewer_evaluate(cycle_number, dec, score, feedback, suggested_fix)


@router.post("/dual-key/revise")
def dual_key_revise(project_id: int, cycle_number: int, revised_content: str):
    dk = _dual_keys.get(project_id)
    if not dk:
        raise HTTPException(400, "Dual-key session not started.")
    result = dk.maker_revise(cycle_number, revised_content)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/dual-key/summary")
def dual_key_summary(project_id: int):
    dk = _dual_keys.get(project_id)
    if not dk:
        raise HTTPException(400, "Dual-key session not started.")
    return dk.get_summary()


_dual_keys: dict[int, DualKey] = {}


# ── Project 10: Sub-Agent Coordination ────────────────────

@router.post("/sub-agent/broadcast")
def sub_agent_broadcast(project_id: int, agent_id: str, message: str,
                        msg_type: str = "info"):
    coord = get_coordinator(project_id)
    msg_id = coord.broadcast(agent_id, message, msg_type)
    return {"message_id": msg_id}


@router.get("/sub-agent/channel")
def sub_agent_channel(project_id: int, last_id: int = 0):
    coord = get_coordinator(project_id)
    return coord.read_since(last_id)


@router.post("/sub-agent/claim")
def sub_agent_claim(project_id: int, agent_id: str, task_name: str):
    coord = get_coordinator(project_id)
    if coord.dedup_task(task_name):
        existing = coord.dedup_task(task_name)
        return {"claimed": False, "reason": "dedup", "existing_task": existing}
    ok = coord.claim(agent_id, task_name)
    return {"claimed": ok, "task_name": task_name}


@router.post("/sub-agent/complete")
def sub_agent_complete(project_id: int, agent_id: str, task_name: str,
                       result: str = ""):
    coord = get_coordinator(project_id)
    coord.complete_task(agent_id, task_name, result)
    return {"completed": True, "task_name": task_name}


@router.post("/sub-agent/conflict")
def sub_agent_conflict(project_id: int, agent_id: str, file_path: str,
                       description: str):
    coord = get_coordinator(project_id)
    coord.report_conflict(agent_id, file_path, description)
    return {"reported": True, "file_path": file_path}


@router.get("/sub-agent/summary")
def sub_agent_summary(project_id: int):
    coord = get_coordinator(project_id)
    return coord.get_summary()


# ── Agent Runtime: execute task ──────────────────────────

@router.post("/run")
async def agent_run(
    project_id: int,
    payload: dict = Body({}),
    db: DBSession = Depends(get_db),
):
    """Execute the agent loop for a task.

    Creates a new session + task, runs the agent loop, and returns results.
    Triggers H3 skill extraction if patterns are detected.

    Body (JSON):
      {"message": "帮我写一个测试", "user_id": 1, "session_id": 0, "max_turns": 5, "mode": "auto"}
    """
    from app.models.session import Session as SessionModel
    from app.models.task_queue import BackgroundTask

    message = payload.get("message", "")
    user_id = payload.get("user_id", 0)
    session_id = payload.get("session_id", 0)
    max_turns = payload.get("max_turns", 10)
    mode = payload.get("mode", "auto")

    if not message:
        raise HTTPException(400, "message is required")

    # Find or create task
    active_task = db.query(BackgroundTask).filter(
        BackgroundTask.project_id == project_id,
        BackgroundTask.status == "active",
    ).first()

    if not active_task:
        active_task = BackgroundTask(
            project_id=project_id,
            name=message[:80] or "untitled",
            status="active",
            priority=1,
            progress=0.0,
        )
        db.add(active_task)
        db.commit()
        db.refresh(active_task)

    # Find or create session
    if session_id:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(404, f"Session {session_id} not found")
    else:
        # Find active session or create new one
        session = db.query(SessionModel).filter(
            SessionModel.project_id == project_id,
            SessionModel.status == "active",
        ).first()

    if not session:
        # Calculate next session_number for this project
        max_num = db.query(SessionModel).filter(
            SessionModel.project_id == project_id
        ).count()
        session = SessionModel(
            project_id=project_id,
            session_number=max_num + 1,
            title=message[:50] or "Agent Run",
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    result = await run_agent_loop(
        db=db,
        project_id=project_id,
        user_id=user_id,
        session_id=session.id,
        task_id=active_task.id,
        message=message,
        max_turns=max_turns,
        mode=mode,
    )

    return result
