"""Project 15: 乌托邦计划 API."""

import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.utopia import ChatImport, UtopiaInsight, UtopiaTask, UtopiaSubmission
from app.models.user_profile import ChatAnalysisRequest
from app.services.utopia_service import (
    import_chat_logs, extract_from_messages,
    prioritize_insights, generate_tasks,
    submit_solution, evaluate_submission, get_server_inbox,
)
from app.services.chat_extractor import (
    discover_chat_sources, extract_messages,
    parse_wechat_txt, parse_feishu_json, parse_feishu_csv,
)

router = APIRouter(prefix="/api/utopia", tags=["utopia"])


# ── Local Chat Discovery ─────────────────────────────

@router.get("/discover")
def discover_sources():
    """Auto-discover local chat databases (WeChat/QQ/Feishu/WeCom)."""
    sources = discover_chat_sources()
    return {"sources": sources, "count": len(sources)}


@router.post("/extract-local")
def extract_local(sources_json: str = "", db_key: str = ""):
    """Extract messages from local chat databases or export files.
    sources_json: JSON array of {platform, type, path} from /discover
    db_key: optional decryption key for encrypted databases
    """
    import json
    sources = json.loads(sources_json) if sources_json else discover_chat_sources()
    result = extract_messages(sources, db_key=db_key if db_key else None)
    return {
        "total_count": result["total_count"],
        "by_platform": {k: len(v) for k, v in result["by_platform"].items()},
        "sample": {k: v[:3] for k, v in result["by_platform"].items() if v},
    }


@router.post("/extract-local/full")
def extract_local_full(sources_json: str = "", db_key: str = "",
                       user_id: int = 0, db: DBSession = Depends(get_db)):
    """Extract + run full utopia pipeline on local chat data."""
    import json
    sources = json.loads(sources_json) if sources_json else discover_chat_sources()
    result = extract_messages(sources, db_key=db_key if db_key else None)

    if result["total_count"] == 0:
        return {"error": "no_messages_found", "sources_checked": len(sources)}

    # Flatten all messages
    all_msgs = []
    for platform, msgs in result["by_platform"].items():
        for m in msgs:
            m["platform"] = platform
            all_msgs.append(m)

    if not all_msgs:
        return {"error": "no_messages_extracted"}

    # Just the text content
    content_list = [m.get("content", "") for m in all_msgs if m.get("content")]

    # Import
    imp = import_chat_logs(db, user_id or 1, "multi", "local", "", content_list)
    import_id = imp["import_id"]

    # Extract insights
    ext = extract_from_messages(db, import_id, user_id or 1, content_list, "multi")
    insights_count = ext["insights_created"]

    # Prioritize
    pri = prioritize_insights(db, user_id or 1)

    # Generate tasks
    tasks = generate_tasks(db, user_id or 1)

    return {
        "import_id": import_id,
        "total_messages": len(content_list),
        "platforms_found": list(result["by_platform"].keys()),
        "insights_found": insights_count,
        "insights_scored": pri["scored"],
        "tasks_created": tasks["tasks_created"],
    }


@router.post("/parse-file")
def parse_file(filepath: str, platform: str = "auto"):
    """Parse a single exported chat file (.txt/.json/.csv)."""
    if platform == "auto":
        if filepath.endswith(".txt"):
            platform = "wechat"
        elif filepath.endswith(".json"):
            platform = "feishu"
        elif filepath.endswith(".csv"):
            platform = "feishu"
        else:
            return {"error": "unsupported_format"}

    msgs = []
    if platform == "wechat" and filepath.endswith(".txt"):
        msgs = parse_wechat_txt(filepath)
    elif platform == "feishu" and filepath.endswith(".json"):
        msgs = parse_feishu_json(filepath)
    elif platform == "feishu" and filepath.endswith(".csv"):
        msgs = parse_feishu_csv(filepath)

    return {"filepath": filepath, "platform": platform,
            "count": len(msgs), "messages": msgs[:10]}


# ── Step 1: Import chat logs ─────────────────────────────

@router.post("/import")
def utopia_import(user_id: int, source_platform: str, file_format: str,
                  filename: str = "", messages_json: str = "",
                  db: DBSession = Depends(get_db)):
    """Import chat logs from a file export.
    messages_json: JSON array of message strings.
    """
    try:
        messages = json.loads(messages_json) if messages_json else []
    except json.JSONDecodeError:
        raise HTTPException(400, "messages_json 格式错误，需要 JSON 数组")

    result = import_chat_logs(db, user_id, source_platform, file_format,
                              filename, messages)
    return result


# ── Step 2: Extract insights (call after import) ──────────

@router.post("/extract")
def utopia_extract(import_id: int, user_id: int,
                   messages_json: str = "",
                   db: DBSession = Depends(get_db)):
    """Extract agent-related insights from imported messages."""
    try:
        messages = json.loads(messages_json) if messages_json else []
    except json.JSONDecodeError:
        raise HTTPException(400, "messages_json 格式错误")

    result = extract_from_messages(db, import_id, user_id, messages)
    return result


# ── Full pipeline (import + extract + prioritize + generate tasks) ─

@router.post("/pipeline")
def utopia_pipeline(user_id: int, source_platform: str, messages_json: str,
                    db: DBSession = Depends(get_db)):
    """Run the full utopia pipeline in one call."""
    try:
        messages = json.loads(messages_json)
    except json.JSONDecodeError:
        raise HTTPException(400, "messages_json 格式错误")

    if not messages:
        return {"error": "empty_messages"}

    # Import
    imp = import_chat_logs(db, user_id, source_platform, "json", "", messages)
    import_id = imp["import_id"]

    # Extract
    ext = extract_from_messages(db, import_id, user_id, messages, source_platform)
    insights_count = ext["insights_created"]

    # Prioritize
    pri = prioritize_insights(db, user_id)

    # Generate tasks
    tasks = generate_tasks(db, user_id)

    return {
        "import_id": import_id,
        "message_count": len(messages),
        "insights_found": insights_count,
        "insights_scored": pri["scored"],
        "tasks_created": tasks["tasks_created"],
    }


# ── Insights listing ─────────────────────────────────────

@router.get("/insights")
def list_insights(user_id: int | None = None, category: str = "",
                  min_priority: float = 0.0, limit: int = 50,
                  db: DBSession = Depends(get_db)):
    """List de-identified insights."""
    query = db.query(UtopiaInsight)
    if user_id:
        query = query.filter(UtopiaInsight.user_id == user_id)
    if category:
        query = query.filter(UtopiaInsight.category == category)
    if min_priority > 0:
        query = query.filter(UtopiaInsight.priority >= min_priority)

    insights = query.order_by(UtopiaInsight.priority.desc()).limit(limit).all()
    return [{
        "id": i.id,
        "category": i.category,
        "sentiment": i.sentiment,
        "deidentified_text": i.deidentified_text[:200],
        "priority": i.priority,
        "clarity_score": i.clarity_score,
        "urgency_score": i.urgency_score,
        "mention_count": i.mention_count,
        "source_platform": i.source_platform,
    } for i in insights]


# ── Tasks ────────────────────────────────────────────────

@router.get("/tasks")
def list_tasks(user_id: int | None = None, status: str = "",
               limit: int = 20, db: DBSession = Depends(get_db)):
    """List utopia tasks ordered by priority."""
    query = db.query(UtopiaTask)
    if user_id:
        query = query.filter(UtopiaTask.user_id == user_id)
    if status:
        query = query.filter(UtopiaTask.status == status)

    tasks = query.order_by(UtopiaTask.priority.desc()).limit(limit).all()
    return [{
        "id": t.id,
        "title": t.title,
        "description": t.description[:200],
        "category": t.category,
        "priority": t.priority,
        "status": t.status,
        "created_at": t.created_at,
    } for t in tasks]


@router.post("/tasks/{task_id}/claim")
def claim_task(task_id: int, claimed_by: str = "",
               db: DBSession = Depends(get_db)):
    """Claim a task for working on."""
    task = db.query(UtopiaTask).filter(UtopiaTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in ("pending",):
        raise HTTPException(400, f"Task is {task.status}, cannot claim")
    task.status = "claimed"
    task.claimed_by = claimed_by
    task.claimed_at = datetime.now().isoformat()
    db.commit()
    return {"task_id": task_id, "status": "claimed"}


@router.post("/tasks/{task_id}/submit")
def submit_task_solution(task_id: int, user_id: int,
                         solution_text: str, solution_artifacts: str = "[]",
                         self_score: float = 0.0, self_rationale: str = "",
                         db: DBSession = Depends(get_db)):
    """Submit a creative solution for a task."""
    result = submit_solution(db, task_id, user_id, solution_text,
                             solution_artifacts, self_score, self_rationale)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ── Evaluation ───────────────────────────────────────────

@router.post("/submissions/{submission_id}/evaluate")
def evaluate_submission_endpoint(submission_id: int, user_score: float,
                                 user_feedback: str = "",
                                 db: DBSession = Depends(get_db)):
    """User evaluates a submission. Composite: user×0.80 + agent_self×0.20."""
    result = evaluate_submission(db, submission_id, user_score, user_feedback)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ── Server Inbox ─────────────────────────────────────────

@router.get("/server/inbox")
def server_inbox(user_id: int | None = None, db: DBSession = Depends(get_db)):
    """Server collects accepted submissions for next-phase planning."""
    return get_server_inbox(db, user_id)


# ── Stats ────────────────────────────────────────────────

@router.get("/stats")
def utopia_stats(user_id: int | None = None, db: DBSession = Depends(get_db)):
    """Aggregate utopia statistics."""
    iq = db.query(UtopiaInsight)
    tq = db.query(UtopiaTask)
    sq = db.query(UtopiaSubmission)
    if user_id:
        iq = iq.filter(UtopiaInsight.user_id == user_id)
        tq = tq.filter(UtopiaTask.user_id == user_id)
        sq = sq.filter(UtopiaSubmission.user_id == user_id)

    total_insights = iq.count()
    total_tasks = tq.count()
    accepted = sq.filter(UtopiaSubmission.status == "accepted").count()

    # Category breakdown
    from sqlalchemy import func
    cat_breakdown = dict(
        db.query(UtopiaInsight.category, func.count(UtopiaInsight.id))
        .filter(UtopiaInsight.user_id == user_id if user_id else True)
        .group_by(UtopiaInsight.category).all()
    )

    return {
        "total_insights": total_insights,
        "total_tasks": total_tasks,
        "accepted_submissions": accepted,
        "category_breakdown": cat_breakdown,
    }
