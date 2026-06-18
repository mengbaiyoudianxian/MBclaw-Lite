"""Project 14: Thought Collision API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.services.collision_engine import (
    run_collision, save_collision_result, mark_collision_tested,
    get_top_collisions, get_collision_context_for_bootstrap,
)

router = APIRouter(prefix="/api/projects/{project_id}/collisions", tags=["collisions"])


@router.post("/collide")
def trigger_collision(project_id: int, db: DBSession = Depends(get_db)):
    """Trigger a thought collision session. Returns ingredients + synthesis prompt."""
    result = run_collision(db, project_id)
    return result


@router.patch("/{collision_id}/result")
def save_result(project_id: int, collision_id: int, combo_name: str,
                combo_description: str = "", expected_synergy: str = "",
                synergy_score: float = 0.0, db: DBSession = Depends(get_db)):
    """Save the LLM's synthesis result for a collision."""
    result = save_collision_result(db, collision_id, combo_name,
                                   combo_description, expected_synergy, synergy_score)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/{collision_id}/test")
def mark_tested(project_id: int, collision_id: int, success: bool,
                result: str = "", db: DBSession = Depends(get_db)):
    """Mark a collision as tested with outcome."""
    res = mark_collision_tested(db, collision_id, success, result)
    if "error" in res:
        raise HTTPException(404, res["error"])
    return res


@router.get("")
def list_collisions(project_id: int, limit: int = 10, db: DBSession = Depends(get_db)):
    """Get top collisions ordered by priority."""
    return get_top_collisions(db, project_id, limit)


@router.get("/context")
def collision_context(project_id: int, db: DBSession = Depends(get_db)):
    """Get collision context ready for system prompt injection."""
    lines = get_collision_context_for_bootstrap(project_id)
    return {"lines": lines, "count": len(lines)}
