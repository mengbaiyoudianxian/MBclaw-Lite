import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.skill_card import SkillCard
from app.schemas.skill_card import SkillCardCreate, SkillCardUpdate, SkillCardOut

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
