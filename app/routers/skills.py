import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.skill_card import SkillCard
from app.schemas.skill_card import SkillCardCreate, SkillCardUpdate, SkillCardOut
from app.services.curator import run_curation, get_stale_skills, manually_archive, manually_restore
from app.services.skill_extractor import detect_triggers, extract_skill_rules, save_extracted_skill

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _to_out(card: SkillCard) -> dict:
    return {
        "id": card.id, "name": card.name,
        "trigger_condition": card.trigger_condition,
        "steps": card.steps, "known_pitfalls": card.known_pitfalls,
        "category": card.category, "created_by": card.created_by,
        "pinned": card.pinned, "last_used_at": card.last_used_at,
        "usage_count": card.usage_count, "status": card.status,
        "task_hash": card.task_hash,
        "created_at": card.created_at, "updated_at": card.updated_at,
    }


@router.get("", response_model=list[SkillCardOut])
def list_skills(status: str | None = None, db: DBSession = Depends(get_db)):
    q = db.query(SkillCard)
    if status:
        q = q.filter(SkillCard.status == status)
    return q.order_by(SkillCard.usage_count.desc()).all()


@router.post("", response_model=SkillCardOut, status_code=201)
def create_skill(data: SkillCardCreate, db: DBSession = Depends(get_db)):
    existing = db.query(SkillCard).filter(SkillCard.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="技能名称已存在")
    now = datetime.now().isoformat()
    card = SkillCard(
        name=data.name,
        trigger_condition=data.trigger_condition,
        steps=json.dumps(data.steps, ensure_ascii=False),
        known_pitfalls=json.dumps(data.known_pitfalls, ensure_ascii=False),
        category=data.category,
        pinned=data.pinned,
        created_at=now,
        updated_at=now,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("/stale")
def list_stale(db: DBSession = Depends(get_db)):
    """List stale or archivable skills for review."""
    skills = get_stale_skills(db)
    return [{"id": s.id, "name": s.name, "status": s.status,
             "last_used_at": s.last_used_at, "pinned": s.pinned,
             "created_by": s.created_by}
            for s in skills]


@router.get("/{skill_id}", response_model=SkillCardOut)
def get_skill(skill_id: int, db: DBSession = Depends(get_db)):
    card = db.query(SkillCard).filter(SkillCard.id == skill_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="技能不存在")
    return card


@router.patch("/{skill_id}", response_model=SkillCardOut)
def update_skill(skill_id: int, data: SkillCardUpdate, db: DBSession = Depends(get_db)):
    card = db.query(SkillCard).filter(SkillCard.id == skill_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="技能不存在")

    updates = data.model_dump(exclude_unset=True)
    if "steps" in updates:
        updates["steps"] = json.dumps(updates["steps"], ensure_ascii=False)
    if "known_pitfalls" in updates:
        updates["known_pitfalls"] = json.dumps(updates["known_pitfalls"], ensure_ascii=False)
    updates["updated_at"] = datetime.now().isoformat()

    for k, v in updates.items():
        setattr(card, k, v)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/{skill_id}", status_code=204)
def delete_skill(skill_id: int, db: DBSession = Depends(get_db)):
    card = db.query(SkillCard).filter(SkillCard.id == skill_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="技能不存在")
    db.delete(card)
    db.commit()


@router.post("/{skill_id}/use")
def mark_used(skill_id: int, db: DBSession = Depends(get_db)):
    """Mark a skill as used, updating its last_used_at and usage_count."""
    card = db.query(SkillCard).filter(SkillCard.id == skill_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="技能不存在")
    card.last_used_at = datetime.now().isoformat()
    card.usage_count = (card.usage_count or 0) + 1
    if card.status == "stale":
        card.status = "active"
    db.commit()
    return {"ok": True, "usage_count": card.usage_count}


# ── H4: Curator lifecycle management ──────────────────────

@router.post("/curate")
def trigger_curation(db: DBSession = Depends(get_db)):
    """Manually trigger a curation cycle. Auto-runs every 24h via scheduler."""
    summary = run_curation(db)
    return summary


@router.post("/{skill_id}/archive")
def archive_skill(skill_id: int, db: DBSession = Depends(get_db)):
    """Manually archive a skill."""
    result = manually_archive(db, skill_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/{skill_id}/restore")
def restore_skill(skill_id: int, db: DBSession = Depends(get_db)):
    """Restore an archived skill back to active."""
    result = manually_restore(db, skill_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# ── H3: Auto Skill Extraction ─────────────────────────

@router.post("/extract")
def trigger_skill_extraction(messages_json: str,
                             db: DBSession = Depends(get_db)):
    """H3: Analyze conversation messages, detect triggers, extract SkillCard."""
    try:
        import json as _json
        messages = _json.loads(messages_json)
    except Exception:
        raise HTTPException(400, "messages_json 格式错误")

    triggers = detect_triggers(messages)

    if not triggers["should_extract"]:
        return {"triggered": False, "trigger_type": triggers["trigger_type"],
                "tool_count": triggers["tool_count"],
                "error_count": triggers["error_count"],
                "user_corrections": triggers["user_corrections"],
                "explicit_trigger": triggers["explicit_trigger"],
                "reason": "no_trigger"}

    skill_data = extract_skill_rules(messages, triggers)
    if not skill_data:
        return {"triggered": True, "trigger_type": triggers["trigger_type"],
                "success": False, "reason": "extraction_failed"}

    save_result = save_extracted_skill(db, skill_data)

    return {
        "triggered": True,
        "trigger_type": triggers["trigger_type"],
        "success": True,
        "skill_data": skill_data,
        "save_result": save_result,
    }


@router.post("/detect-triggers")
def check_triggers(messages_json: str):
    """H3a: Only detect triggers, don't extract. For testing."""
    try:
        import json as _json
        messages = _json.loads(messages_json)
    except Exception:
        raise HTTPException(400, "messages_json 格式错误")

    return detect_triggers(messages)
