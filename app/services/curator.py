"""H4: Curator — automated skill card lifecycle management.

Pure SQL, no LLM calls, zero API cost.

Rules:
  - 30 days since last_used_at → mark status="stale"
  - 90 days since last_used_at → mark status="archived"

Three safety lines (Hermes pattern 4):
  1. pinned=True → permanently skipped
  2. seed-on-first-sight → newly created skills skip first curation cycle
     (prevents mass-archival when booting a fresh system)
  3. created_by="user" → never auto-archive (only agent-created skills)

Scheduling: run every 24h or when idle_duration ≥ 2h.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession

from app.models.skill_card import SkillCard

# Thresholds
STALE_DAYS = 30
ARCHIVE_DAYS = 90
FIRST_SEEN_GRACE_DAYS = 3  # seed-on-first-sight grace period


def run_curation(db: DBSession, now_override: datetime | None = None) -> dict:
    """Run a full curation cycle.

    Returns summary: {stale_count, archived_count, skipped_pinned, skipped_user, skipped_first_seen}
    """
    now = now_override or datetime.now()
    stale_threshold = now - timedelta(days=STALE_DAYS)
    archive_threshold = now - timedelta(days=ARCHIVE_DAYS)
    first_seen_cutoff = now - timedelta(days=FIRST_SEEN_GRACE_DAYS)

    summary = {
        "stale_count": 0,
        "archived_count": 0,
        "skipped_pinned": 0,
        "skipped_user": 0,
        "skipped_first_seen": 0,
    }

    skills = db.query(SkillCard).filter(
        SkillCard.status.in_(["active", "stale"])
    ).all()

    for s in skills:
        # ── Safety line 1: pinned → never touch ──
        if s.pinned:
            summary["skipped_pinned"] += 1
            continue

        # ── Safety line 3: user-created → never auto-archive ──
        if s.created_by != "agent":
            summary["skipped_user"] += 1
            continue

        # ── Safety line 2: seed-on-first-sight ──
        created_at = _parse_datetime(s.created_at)
        if created_at and created_at > first_seen_cutoff:
            summary["skipped_first_seen"] += 1
            continue

        # ── Parse last_used_at ──
        last_used = _parse_datetime(s.last_used_at)
        if not last_used:
            continue

        # ── Archival logic ──
        if s.status == "active" and last_used < stale_threshold:
            if last_used < archive_threshold:
                s.status = "archived"
                summary["archived_count"] += 1
            else:
                s.status = "stale"
                summary["stale_count"] += 1
        elif s.status == "stale" and last_used < archive_threshold:
            s.status = "archived"
            summary["archived_count"] += 1

    db.commit()
    return summary


def get_stale_skills(db: DBSession) -> list[SkillCard]:
    """Get all stale or archivable skills for review."""
    return db.query(SkillCard).filter(
        SkillCard.status.in_(["stale", "active"])
    ).order_by(SkillCard.last_used_at.asc()).all()


def manually_archive(db: DBSession, skill_id: int) -> dict:
    """Manually archive a skill (for user action)."""
    s = db.query(SkillCard).filter(SkillCard.id == skill_id).first()
    if not s:
        return {"error": "not_found"}
    s.status = "archived"
    db.commit()
    return {"id": s.id, "name": s.name, "status": "archived"}


def manually_restore(db: DBSession, skill_id: int) -> dict:
    """Restore an archived skill back to active."""
    s = db.query(SkillCard).filter(SkillCard.id == skill_id).first()
    if not s:
        return {"error": "not_found"}
    s.status = "active"
    s.last_used_at = datetime.now().isoformat()
    db.commit()
    return {"id": s.id, "name": s.name, "status": "active"}


def _parse_datetime(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None
