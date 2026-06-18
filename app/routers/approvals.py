from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.schemas.approval import ApprovalThresholdUpdate, WriteApprovalRequest
from app.services.approval_gate import (
    evaluate_write, approve_pending, reject_pending,
    list_pending, list_approval_log,
    get_user_threshold, set_user_threshold,
)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# ── Settings ──

@router.get("/settings/threshold")
def get_threshold(user_id: int = Query(...), db: DBSession = Depends(get_db)):
    threshold = get_user_threshold(db, user_id)
    return {"user_id": user_id, "threshold": threshold}


@router.patch("/settings/threshold")
def update_threshold(user_id: int = Query(...), data: ApprovalThresholdUpdate = None,
                     db: DBSession = Depends(get_db)):
    if data is None:
        data = ApprovalThresholdUpdate()
    result = set_user_threshold(db, user_id, level=data.level, custom=data.custom)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


# ── Write gate ──

@router.post("/evaluate")
def evaluate(req: WriteApprovalRequest, db: DBSession = Depends(get_db)):
    """Evaluate a write operation: auto-approve or stage for review."""
    return evaluate_write(
        db, req.user_id, req.subsystem, req.scope, req.origin,
        req.content_chars, req.modifies_existing, req.detail, req.payload,
    )


# ── Pending review ──

@router.get("/pending")
def get_pending(user_id: int = Query(...), db: DBSession = Depends(get_db)):
    return list_pending(db, user_id)


@router.post("/pending/{pending_id}/approve")
def approve(pending_id: int, user_id: int = Query(...), db: DBSession = Depends(get_db)):
    result = approve_pending(db, pending_id, user_id)
    if "error" in result:
        raise HTTPException(status_code=404 if result["error"] == "not_found" else 400,
                            detail=result)
    return result


@router.post("/pending/{pending_id}/reject")
def reject(pending_id: int, user_id: int = Query(...), db: DBSession = Depends(get_db)):
    result = reject_pending(db, pending_id, user_id)
    if "error" in result:
        raise HTTPException(status_code=404 if result["error"] == "not_found" else 400,
                            detail=result)
    return result


# ── Audit log ──

@router.get("/log")
def get_log(user_id: int = Query(...), limit: int = 50, db: DBSession = Depends(get_db)):
    return list_approval_log(db, user_id, limit)
