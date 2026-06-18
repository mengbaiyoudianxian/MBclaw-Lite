"""Breakthrough detection + snapshot creation service."""

import json
import os
import re
import shutil
import tarfile
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.config import DATA_DIR
from app.models.project import Project
from app.models.project_dna import ProjectDNA
from app.models.session import Session
from app.models.summary import Summary
from app.models.snapshot import Snapshot

SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")
SUCCESS_KEYWORDS = re.compile(r"成功|解决|完成|突破|行了|好了|nice|great|solved|fixed|works", re.IGNORECASE)
EXCITED_KEYWORDS = re.compile(r"太好了|成功了|终于|awesome|perfect|excellent|amazing", re.IGNORECASE)


def _ensure_dir():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


def check_breakthrough(db: DBSession, session: Session) -> tuple[bool, str]:
    """Return (is_breakthrough, reason) based on 3 detection rules."""
    rules_triggered = 0
    reasons = []

    # Rule 1: ProjectDNA successful_approaches has new entry
    dna = db.query(ProjectDNA).filter(ProjectDNA.project_id == session.project_id).first()
    if dna and dna.successful_approaches and dna.successful_approaches != "[]":
        try:
            arr = json.loads(dna.successful_approaches)
            if len(arr) > 0:
                rules_triggered += 1
                reasons.append("new_successful_approach")
        except (json.JSONDecodeError, TypeError):
            pass

    # Rule 2: Summary conclusions match success keywords
    summary = db.query(Summary).filter(Summary.session_id == session.id).first()
    if summary and summary.conclusions:
        if SUCCESS_KEYWORDS.search(summary.conclusions):
            rules_triggered += 1
            reasons.append("success_conclusion_match")

    # Rule 3: User messages contain excited keywords
    from app.models.message import Message
    user_msgs = db.query(Message).filter(
        Message.session_id == session.id, Message.role == "user"
    ).all()
    for msg in user_msgs:
        if EXCITED_KEYWORDS.search(msg.content):
            rules_triggered += 1
            reasons.append("excited_user_message")
            break

    reason = "+".join(reasons) if reasons else "manual"
    return (rules_triggered >= 2, reason)


def create_snapshot(db: DBSession, project_id: int, reason: str = "manual",
                    trigger_rule: str = "") -> Snapshot:
    """Capture full project state as JSON + tar.gz memory files."""
    _ensure_dir()

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("项目不存在")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", project.name)
    snap_dir = os.path.join(SNAPSHOTS_DIR, f"{safe_name}", timestamp)
    os.makedirs(snap_dir, exist_ok=True)

    # Dump project DB rows as JSON
    from app.models.session import Session as SessionModel
    from app.models.message import Message
    from app.models.summary import Summary as SummaryModel
    from app.models.keyword import Keyword
    from app.models.project_dna import ProjectDNA as DNA

    sessions = db.query(SessionModel).filter(SessionModel.project_id == project_id).all()
    dump = {
        "project": {"id": project.id, "name": project.name, "user_id": project.user_id},
        "sessions": [],
    }

    for sess in sessions:
        msgs = db.query(Message).filter(Message.session_id == sess.id).order_by(Message.id).all()
        summs = db.query(SummaryModel).filter(SummaryModel.session_id == sess.id).all()
        kws = db.query(Keyword).filter(Keyword.session_id == sess.id).all()
        sess_data = {
            "id": sess.id, "title": sess.title, "status": sess.status,
            "session_number": sess.session_number,
            "messages": [{c.name: getattr(m, c.name) for c in Message.__table__.columns}
                         for m in msgs],
            "summaries": [{c.name: getattr(s, c.name) for c in SummaryModel.__table__.columns}
                          for s in summs],
            "keywords": [{c.name: getattr(k, c.name) for c in Keyword.__table__.columns}
                         for k in kws],
        }
        dump["sessions"].append(sess_data)

    # DNA
    dna = db.query(DNA).filter(DNA.project_id == project_id).first()
    if dna:
        dump["dna"] = {c.name: getattr(dna, c.name) for c in DNA.__table__.columns}

    # Write JSON
    json_path = os.path.join(snap_dir, "db_dump.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2, default=str)

    # Tar memory dir
    memory_dir = os.path.join(DATA_DIR, "memory")
    if os.path.exists(memory_dir):
        tar_path = os.path.join(snap_dir, "memory.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            # Only include project-related memory files
            for fname in os.listdir(memory_dir):
                if fname.endswith(".md") or fname.endswith(".json"):
                    full = os.path.join(memory_dir, fname)
                    tar.add(full, arcname=fname)

    # Record in DB
    snapshot = Snapshot(
        project_id=project_id,
        path=snap_dir,
        reason=reason,
        trigger_rule=trigger_rule,
        content_json=json.dumps(dump, ensure_ascii=False, default=str),
        created_at=datetime.now().isoformat(),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return snapshot


def restore_snapshot(db: DBSession, snapshot_id: int) -> dict:
    """Restore project state from a snapshot."""
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        return {"success": False, "message": "快照不存在"}

    try:
        dump = json.loads(snapshot.content_json)
    except (json.JSONDecodeError, TypeError):
        return {"success": False, "message": "快照数据损坏"}

    project_data = dump.get("project", {})
    project = db.query(Project).filter(Project.id == snapshot.project_id).first()
    if not project:
        return {"success": False, "message": "项目中不存在"}

    # Restore sessions, messages, summaries, keywords
    from app.models.session import Session as SessionModel
    from app.models.message import Message
    from app.models.summary import Summary as SummaryModel
    from app.models.keyword import Keyword

    # Clear existing project data
    old_sessions = db.query(SessionModel).filter(SessionModel.project_id == snapshot.project_id).all()
    for s in old_sessions:
        db.query(Message).filter(Message.session_id == s.id).delete()
        db.query(SummaryModel).filter(SummaryModel.session_id == s.id).delete()
        db.query(Keyword).filter(Keyword.session_id == s.id).delete()
        db.delete(s)

    # Restore sessions
    for sess_data in dump.get("sessions", []):
        session = SessionModel(
            id=sess_data["id"],
            project_id=snapshot.project_id,
            title=sess_data.get("title", "Restored"),
            status=sess_data.get("status", "completed"),
            session_number=sess_data.get("session_number", 1),
        )
        db.add(session)
        db.flush()

        for mdata in sess_data.get("messages", []):
            msg = Message(
                session_id=session.id,
                role=mdata.get("role", "user"),
                content=mdata.get("content", ""),
                thinking_content=mdata.get("thinking_content", ""),
                changed_files=mdata.get("changed_files", "[]"),
                created_at=mdata.get("created_at", ""),
            )
            db.add(msg)

        for sdata in sess_data.get("summaries", []):
            summ = SummaryModel(
                session_id=session.id,
                topic=sdata.get("topic", ""),
                conclusions=sdata.get("conclusions", ""),
            )
            db.add(summ)

        for kdata in sess_data.get("keywords", []):
            kw = Keyword(
                session_id=session.id,
                project_id=snapshot.project_id,
                keyword=kdata.get("keyword", ""),
                weight=kdata.get("weight", 1.0),
            )
            db.add(kw)

    db.commit()
    return {"success": True, "snapshot_id": snapshot_id, "message": "快照恢复成功"}
