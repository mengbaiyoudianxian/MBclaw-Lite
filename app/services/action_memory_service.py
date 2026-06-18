from sqlalchemy.orm import Session as DBSession
from app.models.session import Session
from app.models.action_memory import ActionMemory


def extract_action_memories(db: DBSession, session: Session) -> list[ActionMemory]:
    """Extract action-sensitive memories from a completed session."""
    messages = session.messages
    results = []

    for msg in messages:
        content = msg.content
        lower = content.lower()

        if any(kw in lower for kw in ["permission", "权限", "grant", "授权"]):
            results.append(ActionMemory(
                session_id=session.id,
                project_id=session.project_id,
                action=content[:500],
                permissions=_extract_permissions(content),
                source_authority=msg.role if msg.role in ("user", "assistant") else "system",
            ))

        if any(kw in lower for kw in ["schedule", "remind", "deadline", "日程", "提醒", "截止", "timing", "when"]):
            results.append(ActionMemory(
                session_id=session.id,
                project_id=session.project_id,
                action=content[:500],
                timing=_extract_timing(content),
                source_authority=msg.role if msg.role in ("user", "assistant") else "system",
            ))

        if any(kw in lower for kw in ["expire", "过期", "valid until", "有效期", "ttl"]):
            results.append(ActionMemory(
                session_id=session.id,
                project_id=session.project_id,
                action=content[:500],
                expiry=_extract_expiry(content),
                source_authority=msg.role if msg.role in ("user", "assistant") else "system",
            ))

    return results


def _extract_permissions(text: str) -> str:
    perms = []
    for kw in ["root", "sudo", "admin", "read", "write", "execute", "api_key", "token", "管理员"]:
        if kw in text.lower():
            perms.append(kw)
    return ", ".join(perms) if perms else "unknown"


def _extract_timing(text: str) -> str:
    import re
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}:\d{2}",
        r"tomorrow|明天|next week|下周|today|今天",
    ]
    found = []
    for p in patterns:
        matches = re.findall(p, text, re.IGNORECASE)
        found.extend(matches)
    return ", ".join(found[:5]) if found else "unspecified"


def _extract_expiry(text: str) -> str:
    import re
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d+\s*(day|hour|min|天|小时|分钟|周|月)",
        r"never|永久|permanent",
    ]
    found = []
    for p in patterns:
        matches = re.findall(p, text, re.IGNORECASE)
        if matches:
            if isinstance(matches[0], tuple):
                found.extend(m[0] for m in matches)
            else:
                found.extend(matches)
    return ", ".join(found[:5]) if found else "unspecified"
