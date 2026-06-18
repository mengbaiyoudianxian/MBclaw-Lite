"""H5: Write-approval gate with configurable risk-scoring thresholds.

Five risk dimensions, weighted:
  subsystem (0.30): which part of the system is being changed
  scope     (0.25): single add vs batch delete vs full clear
  origin    (0.20): user manual vs agent foreground vs background
  content_size (0.10): how much content is affected
  modifies_existing (0.15): pure add vs modify vs delete

Decision matrix:
  risk_score <= user_threshold → AUTO_APPROVE (log to ApprovalLog)
  risk_score >  user_threshold → REQUIRE_APPROVAL (save to PendingApproval)
"""

import json
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.user_settings import UserSettings
from app.models.approval_log import ApprovalLog
from app.models.pending_approval import PendingApproval

# ── threshold presets ──────────────────────────────────────

THRESHOLD_LEVELS = {
    "minimal":   0.05,
    "low":       0.25,
    "medium":    0.45,
    "high":      0.70,
    "maximum":   0.95,
    "full_auto": 1.00,
}

LEVEL_LABELS = {
    0.05:  "极低",
    0.25:  "低",
    0.45:  "中",
    0.70:  "中高",
    0.95:  "极高",
    1.00:  "全自动",
}

# ── risk scoring ───────────────────────────────────────────

RISK_WEIGHTS = {
    "subsystem":         0.30,
    "scope":             0.25,
    "origin":            0.20,
    "content_size":      0.10,
    "modifies_existing": 0.15,
}

SUBSYSTEM_SCORES = {
    "memory":          0.3,
    "user":            0.3,
    "skill":           0.6,
    "dna":             0.7,
    "snapshot":        0.7,
    "snapshot_delete": 0.9,
    "tool":            0.5,
    "integration":     0.6,
    "model_profile":   0.4,
}

SCOPE_SCORES = {
    "single_add":    0.10,
    "single_update": 0.35,
    "single_delete": 0.50,
    "batch_add":     0.30,
    "batch_mixed":   0.50,
    "batch_delete":  0.80,
    "full_clear":    0.95,
}

ORIGIN_SCORES = {
    "user_manual":     0.0,
    "agent_foreground": 0.3,
    "agent_background": 0.6,
    "daemon":          0.8,
}

CONTENT_SIZE_SCORES = {
    "tiny":   0.10,   # < 100 chars
    "small":  0.20,   # 100-500
    "medium": 0.40,   # 500-2000
    "large":  0.70,   # > 2000
}

MODIFIES_EXISTING_SCORES = {
    "pure_add":    0.10,
    "modify":      0.50,
    "delete":      0.80,
}


def score_content_size(chars: int) -> float:
    if chars < 100:
        return CONTENT_SIZE_SCORES["tiny"]
    if chars < 500:
        return CONTENT_SIZE_SCORES["small"]
    if chars < 2000:
        return CONTENT_SIZE_SCORES["medium"]
    return CONTENT_SIZE_SCORES["large"]


def calculate_risk(subsystem: str, scope: str, origin: str,
                   content_chars: int = 0, modifies_existing: str = "pure_add") -> float:
    """Return risk score 0.0-1.0. Weights are applied to each dimension."""
    scores = {
        "subsystem":         SUBSYSTEM_SCORES.get(subsystem, 0.5),
        "scope":             SCOPE_SCORES.get(scope, 0.5),
        "origin":            ORIGIN_SCORES.get(origin, 0.3),
        "content_size":      score_content_size(content_chars),
        "modifies_existing": MODIFIES_EXISTING_SCORES.get(modifies_existing, 0.5),
    }
    raw = sum(RISK_WEIGHTS[k] * scores[k] for k in RISK_WEIGHTS)
    return round(min(raw, 1.0), 3)


# ── user settings ──────────────────────────────────────────

def get_user_threshold(db: DBSession, user_id: int) -> float:
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        return THRESHOLD_LEVELS["medium"]
    return settings.approval_threshold


def set_user_threshold(db: DBSession, user_id: int, level: str | None = None,
                       custom: float | None = None) -> dict:
    if custom is not None:
        threshold = max(0.0, min(1.0, custom))
        level = LEVEL_LABELS.get(threshold, "自定义")
    elif level and level in THRESHOLD_LEVELS:
        threshold = THRESHOLD_LEVELS[level]
    else:
        return {"error": "invalid_level", "valid": list(THRESHOLD_LEVELS.keys())}

    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)

    settings.approval_threshold = threshold
    settings.approval_level = level or "custom"
    settings.updated_at = datetime.now().isoformat()
    db.commit()
    db.refresh(settings)

    return {
        "user_id": user_id,
        "threshold": threshold,
        "level": settings.approval_level,
        "label": LEVEL_LABELS.get(threshold, "自定义"),
    }


# ── gate evaluation ────────────────────────────────────────

def evaluate_write(db: DBSession, user_id: int, subsystem: str, scope: str,
                   origin: str, content_chars: int = 0,
                   modifies_existing: str = "pure_add",
                   detail: str = "", payload: dict | None = None) -> dict:
    """
    Evaluate a write operation against the user's approval threshold.

    Returns:
      {decision: "auto_approved"|"pending", risk_score, threshold, ...}
      On pending: also includes pending_id.
    """
    threshold = get_user_threshold(db, user_id)
    risk = calculate_risk(subsystem, scope, origin, content_chars, modifies_existing)
    now = datetime.now().isoformat()

    if risk <= threshold:
        # Auto-approve: log and return
        log = ApprovalLog(
            user_id=user_id,
            operation=f"{subsystem}.{scope}",
            subsystem=subsystem,
            scope=scope,
            origin=origin,
            risk_score=risk,
            threshold=threshold,
            decision="auto_approved",
            detail=detail,
            created_at=now,
        )
        db.add(log)
        db.commit()
        return {
            "decision": "auto_approved",
            "risk_score": risk,
            "threshold": threshold,
            "log_id": log.id,
            "note": "自动批准 — 可通过 GET /api/approvals/log 审查",
        }

    # Require approval: stage to pending
    pending = PendingApproval(
        user_id=user_id,
        operation=f"{subsystem}.{scope}",
        subsystem=subsystem,
        scope=scope,
        origin=origin,
        risk_score=risk,
        threshold=threshold,
        status="pending",
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
        detail=detail,
        created_at=now,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)

    return {
        "decision": "pending",
        "risk_score": risk,
        "threshold": threshold,
        "pending_id": pending.id,
        "note": f"需要审批 — 风险分数 {risk} > 阈值 {threshold}",
    }


# ── pending review ─────────────────────────────────────────

def list_pending(db: DBSession, user_id: int) -> list[dict]:
    items = db.query(PendingApproval).filter(
        PendingApproval.user_id == user_id,
        PendingApproval.status == "pending",
    ).order_by(PendingApproval.created_at.desc()).all()

    return [{
        "id": p.id, "operation": p.operation, "subsystem": p.subsystem,
        "scope": p.scope, "origin": p.origin,
        "risk_score": p.risk_score, "threshold": p.threshold,
        "status": p.status, "detail": p.detail,
        "created_at": p.created_at,
    } for p in items]


def approve_pending(db: DBSession, pending_id: int, user_id: int) -> dict:
    p = db.query(PendingApproval).filter(
        PendingApproval.id == pending_id, PendingApproval.user_id == user_id
    ).first()
    if not p:
        return {"error": "not_found"}
    if p.status != "pending":
        return {"error": "already_resolved", "status": p.status}

    p.status = "approved"
    p.resolved_at = datetime.now().isoformat()
    db.commit()

    # Also log to ApprovalLog for audit
    log = ApprovalLog(
        user_id=user_id,
        operation=p.operation,
        subsystem=p.subsystem,
        scope=p.scope,
        origin=p.origin,
        risk_score=p.risk_score,
        threshold=p.threshold,
        decision="user_approved",
        detail=p.detail,
        created_at=datetime.now().isoformat(),
    )
    db.add(log)
    db.commit()

    return {"decision": "approved", "pending_id": pending_id, "payload": p.payload_json}


def reject_pending(db: DBSession, pending_id: int, user_id: int) -> dict:
    p = db.query(PendingApproval).filter(
        PendingApproval.id == pending_id, PendingApproval.user_id == user_id
    ).first()
    if not p:
        return {"error": "not_found"}
    if p.status != "pending":
        return {"error": "already_resolved", "status": p.status}

    p.status = "rejected"
    p.resolved_at = datetime.now().isoformat()
    db.commit()

    return {"decision": "rejected", "pending_id": pending_id}


def list_approval_log(db: DBSession, user_id: int, limit: int = 50) -> list[dict]:
    items = db.query(ApprovalLog).filter(
        ApprovalLog.user_id == user_id
    ).order_by(ApprovalLog.created_at.desc()).limit(limit).all()

    return [{
        "id": a.id, "operation": a.operation, "subsystem": a.subsystem,
        "scope": a.scope, "origin": a.origin,
        "risk_score": a.risk_score, "threshold": a.threshold,
        "decision": a.decision, "detail": a.detail,
        "created_at": a.created_at,
    } for a in items]
