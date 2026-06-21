"""Snapshot Service — create named restore points of database state."""

import os
import shutil
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from app.models import Session as SessionModel


SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "snapshots")


def create_snapshot(db: DBSession, name: str, description: str = "") -> dict:
    """Create a database snapshot using VACUUM INTO."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    filename = f"{ts}_{safe_name}.db"
    path = os.path.join(SNAPSHOT_DIR, filename)

    # VACUUM INTO creates a clean copy
    from sqlalchemy import text
    db.execute(text(f"VACUUM INTO '{path}'"))
    db.commit()

    size = os.path.getsize(path)
    sessions_count = db.query(SessionModel).count()

    return {
        "name": name,
        "description": description,
        "filename": filename,
        "path": path,
        "size_bytes": size,
        "sessions_count": sessions_count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def list_snapshots() -> list[dict]:
    """List all available snapshots."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    snaps = []
    for fname in sorted(os.listdir(SNAPSHOT_DIR), reverse=True):
        if fname.endswith(".db"):
            fpath = os.path.join(SNAPSHOT_DIR, fname)
            snaps.append({
                "filename": fname,
                "size_bytes": os.path.getsize(fpath),
                "created_at": datetime.fromtimestamp(
                    os.path.getmtime(fpath), tz=timezone.utc
                ).isoformat(),
            })
    return snaps[:20]
