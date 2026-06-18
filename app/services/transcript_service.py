import os
import json
import fcntl
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.config import DATA_DIR
from app.models.session import Session
from app.models.message import Message

TRANSCRIPTS_DIR = os.path.join(DATA_DIR, "transcripts")
MAX_SHARD_BYTES = 5 * 1024 * 1024  # 5MB per shard


def _ensure_dir():
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)


def _shard_path(session_id: int, part: int = 1) -> str:
    if part == 1:
        return os.path.join(TRANSCRIPTS_DIR, f"{session_id}.jsonl")
    return os.path.join(TRANSCRIPTS_DIR, f"{session_id}_part{part}.jsonl")


def _current_shard(session_id: int) -> tuple[int, int]:
    """Returns (part_number, size_in_bytes) of the active shard."""
    part = 1
    path = _shard_path(session_id, part)
    while os.path.exists(path):
        size = os.path.getsize(path)
        if size < MAX_SHARD_BYTES:
            return part, size
        part += 1
        path = _shard_path(session_id, part)
    return part, 0


def append_to_transcript(session: Session, message: dict):
    """Append one message line to the session JSONL transcript (with sharding)."""
    _ensure_dir()
    part, size = _current_shard(session.id)
    line = json.dumps({
        "session_id": session.id,
        "session_number": session.session_number,
        "project_id": session.project_id,
        "role": message.get("role"),
        "content": message.get("content"),
        "thinking": message.get("thinking_content", ""),
        "changed_files": message.get("changed_files", "[]"),
        "created_at": message.get("created_at", datetime.now().isoformat()),
    }, ensure_ascii=False)
    line_bytes = len((line + "\n").encode("utf-8"))
    if size + line_bytes > MAX_SHARD_BYTES and size > 0:
        part += 1
    path = _shard_path(session.id, part)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_transcript(session_id: int) -> list[dict]:
    """Read all lines from a session JSONL transcript (across shards)."""
    lines = []
    for part in range(1, 10):
        path = _shard_path(session_id, part)
        if not os.path.exists(path):
            break
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return lines


def write_final_transcript(db: DBSession, session: Session) -> str:
    """Write complete transcript with enhanced fields (thinking, changed_files, sharded)."""
    messages = db.query(Message).filter(Message.session_id == session.id).order_by(Message.id).all()
    _ensure_dir()

    # Clean old shards
    for part in range(1, 20):
        path = _shard_path(session.id, part)
        if os.path.exists(path):
            os.remove(path)

    part = 1
    current_bytes = 0
    path = _shard_path(session.id, part)
    tmp = path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        for m in messages:
            line = json.dumps({
                "session_id": session.id,
                "session_number": session.session_number,
                "project_id": session.project_id,
                "role": m.role,
                "content": m.content,
                "thinking": m.thinking_content or "",
                "changed_files": m.changed_files or "[]",
                "created_at": m.created_at,
            }, ensure_ascii=False)
            line_bytes = len((line + "\n").encode("utf-8"))

            if current_bytes + line_bytes > MAX_SHARD_BYTES and current_bytes > 0:
                f.flush()
                os.fsync(f.fileno())
                os.replace(tmp, path)
                part += 1
                current_bytes = 0
                path = _shard_path(session.id, part)
                tmp = path + ".tmp"

            f.write(line + "\n")
            current_bytes += line_bytes

        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return _shard_path(session.id, 1)
