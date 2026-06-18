from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.session import Session
from app.models.message import Message
from app.models.summary import Summary


def generate_summary(db: DBSession, session: Session) -> Summary:
    messages = db.query(Message).filter(Message.session_id == session.id).order_by(Message.id).all()
    full_text = "\n".join(f"[{m.role}]: {m.content}" for m in messages)

    topic = _extract_topic(full_text, messages)
    conclusions = _extract_conclusions(full_text)
    decisions = _extract_decisions(full_text)
    next_steps = _extract_next_steps(full_text)

    existing = db.query(Summary).filter(Summary.session_id == session.id).first()
    if existing:
        existing.topic = topic
        existing.conclusions = conclusions
        existing.decisions = decisions
        existing.next_steps = next_steps
        existing.created_at = datetime.now().isoformat()
        db.flush()
        return existing

    summary = Summary(
        session_id=session.id,
        topic=topic,
        conclusions=conclusions,
        decisions=decisions,
        next_steps=next_steps,
    )
    db.add(summary)
    db.flush()
    return summary


def _extract_topic(full_text: str, messages: list) -> str:
    first_user_msgs = [m for m in messages if m.role == "user"]
    if first_user_msgs:
        content = first_user_msgs[0].content
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        for line in lines:
            if len(line) < 100 and not line.startswith("#"):
                return line[:200]
        return content[:200]
    return ""


def _extract_conclusions(full_text: str) -> str:
    conclusions = []
    for line in full_text.split("\n"):
        lowered = line.lower()
        if any(kw in lowered for kw in ["结论", "总结", "conclusion", "总之", "综上", "所以"]):
            conclusions.append(line.strip())
    return "\n".join(conclusions[-5:]) if conclusions else ""


def _extract_decisions(full_text: str) -> str:
    decisions = []
    for line in full_text.split("\n"):
        lowered = line.lower()
        if any(kw in lowered for kw in ["决定", "采用", "确定", "选择", "decision", "方案是", "最终方案"]):
            decisions.append(line.strip())
    return "\n".join(decisions[-5:]) if decisions else ""


def _extract_next_steps(full_text: str) -> str:
    steps = []
    for line in full_text.split("\n"):
        lowered = line.lower()
        if any(kw in lowered for kw in ["下一步", "后续", "计划", "待办", "todo", "接下来", "next step"]):
            steps.append(line.strip())
    return "\n".join(steps[-5:]) if steps else ""
