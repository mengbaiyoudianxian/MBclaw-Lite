"""F1+F2: Feedback + User Profile API."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.user_profile import UserProfile, PositivePattern, ChatAnalysisRequest
from app.models.feedback import Feedback
from app.services.feedback_service import (
    create_feedback, get_feedback_for_session, get_feedback_for_project,
    get_feedback_stats, update_approach_success_rate, get_approach_ranking,
    solicitation_message,
)
from app.services.psychology_engine import (
    update_profile_from_feedback, generate_persona_block,
    get_archetype_style_rules,
)

router = APIRouter(prefix="/api", tags=["feedback"])


# ── F1: Feedback CRUD ─────────────────────────────────────

@router.post("/projects/{project_id}/feedback", status_code=201)
def submit_feedback(project_id: int, overall_rating: int,
                    session_id: int | None = None,
                    task_id: int | None = None,
                    helpfulness: int = 0, accuracy: int = 0,
                    speed: int = 0, clarity: int = 0,
                    what_went_well: str = "", what_to_improve: str = "",
                    free_text: str = "", solicited: str = "auto",
                    db: DBSession = Depends(get_db)):
    fb = create_feedback(
        db, project_id,
        session_id=session_id,
        task_id=task_id,
        overall_rating=overall_rating,
        helpfulness=helpfulness, accuracy=accuracy,
        speed=speed, clarity=clarity,
        what_went_well=what_went_well,
        what_to_improve=what_to_improve,
        free_text=free_text, solicited=solicited,
    )

    # ── F2: Update user profile from feedback ──
    profile_result = None
    if free_text or what_went_well:
        # Get or create user profile for project owner
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.user_id:
            profile = db.query(UserProfile).filter(
                UserProfile.user_id == project.user_id
            ).first()
            if not profile:
                profile = UserProfile(user_id=project.user_id)
                db.add(profile)
                db.commit()
                db.refresh(profile)

            combined_text = f"{what_went_well} {what_to_improve} {free_text}"
            ratings = {"overall": overall_rating}
            profile_result = update_profile_from_feedback(profile, combined_text, ratings)
            db.commit()

    return {
        "feedback_id": fb.id,
        "overall_rating": fb.overall_rating,
        "profile_update": profile_result,
    }


@router.get("/projects/{project_id}/feedback")
def list_feedback(project_id: int, session_id: int = 0, limit: int = 50,
                  db: DBSession = Depends(get_db)):
    if session_id:
        items = get_feedback_for_session(db, session_id)
    else:
        items = get_feedback_for_project(db, project_id, limit)
    return [{"id": f.id, "overall_rating": f.overall_rating,
             "what_went_well": f.what_went_well, "created_at": f.created_at}
            for f in items]


@router.get("/projects/{project_id}/feedback/stats")
def feedback_stats(project_id: int, db: DBSession = Depends(get_db)):
    return get_feedback_stats(db, project_id)


@router.get("/projects/{project_id}/feedback/solicit")
def solicit(project_id: int, session_title: str = "", db: DBSession = Depends(get_db)):
    from app.models.project import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    project_name = project.name if project else ""
    return solicitation_message(project_name, session_title)


# ── F1: Approach success rate tracking ────────────────────

@router.post("/projects/{project_id}/approaches/success-rate")
def track_approach(project_id: int, approach_name: str, success: bool,
                   rating: int = 0, db: DBSession = Depends(get_db)):
    asr = update_approach_success_rate(db, project_id, approach_name, success, rating)
    return {
        "approach": asr.approach_name,
        "success_rate": round(asr.success_rate, 3),
        "total_attempts": asr.total_attempts,
    }


@router.get("/projects/{project_id}/approaches/ranking")
def approach_ranking(project_id: int, db: DBSession = Depends(get_db)):
    return get_approach_ranking(db, project_id)


# ── F2: User Profile ──────────────────────────────────────

@router.get("/users/{user_id}/profile")
def get_user_profile(user_id: int, db: DBSession = Depends(get_db)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        return {"user_id": user_id, "exists": False}
    return {
        "user_id": profile.user_id,
        "traits": {
            "social_energy": profile.social_energy,
            "decision_style": profile.decision_style,
            "communication": profile.communication,
            "structure_pref": profile.structure_pref,
        },
        "companion_archetype": profile.companion_archetype,
        "archetype_confidence": profile.archetype_confidence,
        "formality_level": profile.formality_level,
        "feedback_count": profile.feedback_count,
        "confidence_score": profile.confidence_score,
        "praised_language": profile.praised_language,
        "praised_behaviors": profile.praised_behaviors,
    }


@router.get("/users/{user_id}/profile/persona")
def get_user_persona(user_id: int, db: DBSession = Depends(get_db)):
    """Get the persona block for system prompt injection."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        return {"user_id": user_id, "persona": "", "exists": False}

    persona = generate_persona_block(profile)
    archetype = get_archetype_style_rules(profile.companion_archetype)
    return {
        "user_id": user_id,
        "exists": True,
        "persona": persona,
        "archetype": archetype,
        "confidence": profile.confidence_score,
    }


# ── F2: Chat Analysis Request ─────────────────────────────

@router.post("/users/{user_id}/chat-analysis/request")
def request_chat_analysis(user_id: int, chat_source: str,
                          db: DBSession = Depends(get_db)):
    """Request permission to analyze user's chats with others."""
    req = ChatAnalysisRequest(
        user_id=user_id,
        chat_source=chat_source,
        status="pending",
        created_at=datetime.now().isoformat(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "request_id": req.id,
        "status": req.status,
        "message": f"已向用户申请查看'{chat_source}'的聊天记录，等待用户批准。",
    }


@router.post("/users/{user_id}/chat-analysis/{request_id}/approve")
def approve_chat_analysis(user_id: int, request_id: int,
                          db: DBSession = Depends(get_db)):
    """User approves the chat analysis request."""
    req = db.query(ChatAnalysisRequest).filter(
        ChatAnalysisRequest.id == request_id,
        ChatAnalysisRequest.user_id == user_id,
    ).first()
    if not req:
        raise HTTPException(404, "Request not found")
    req.status = "approved"
    req.permission_granted_at = datetime.now().isoformat()
    db.commit()
    return {"request_id": req.id, "status": "approved",
            "message": "已获授权，可以开始分析聊天记录"}


@router.post("/users/{user_id}/chat-analysis/{request_id}/complete")
def complete_chat_analysis(user_id: int, request_id: int,
                           analysis_result: str = "",
                           db: DBSession = Depends(get_db)):
    """Mark analysis as complete and store results."""
    req = db.query(ChatAnalysisRequest).filter(
        ChatAnalysisRequest.id == request_id,
        ChatAnalysisRequest.user_id == user_id,
        ChatAnalysisRequest.status == "approved",
    ).first()
    if not req:
        raise HTTPException(404, "Request not found or not approved")
    req.status = "completed"
    req.analysis_result = analysis_result
    req.analyzed_at = datetime.now().isoformat()
    db.commit()

    # Update user profile with analysis results
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile and analysis_result:
        result = update_profile_from_feedback(profile, analysis_result, {})
        db.commit()
        return {"request_id": req.id, "status": "completed",
                "profile_update": result}

    return {"request_id": req.id, "status": "completed"}


# ── F2: Positive Pattern management ───────────────────────

@router.get("/users/{user_id}/patterns")
def get_positive_patterns(user_id: int, category: str = "",
                          db: DBSession = Depends(get_db)):
    query = db.query(PositivePattern).filter(PositivePattern.user_id == user_id)
    if category:
        query = query.filter(PositivePattern.category == category)
    patterns = query.order_by(PositivePattern.strength.desc()).all()
    return [{"id": p.id, "category": p.category, "pattern": p.pattern,
             "strength": p.strength, "occurrences": p.occurrences}
            for p in patterns]


@router.post("/users/{user_id}/patterns")
def add_positive_pattern(user_id: int, category: str, pattern: str,
                         source: str = "feedback", db: DBSession = Depends(get_db)):
    # Upsert: increment strength if exists
    existing = db.query(PositivePattern).filter(
        PositivePattern.user_id == user_id,
        PositivePattern.pattern == pattern,
    ).first()
    if existing:
        existing.occurrences += 1
        existing.strength = min(5.0, existing.strength + 0.5)
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "occurrences": existing.occurrences,
                "strength": existing.strength, "updated": True}

    p = PositivePattern(
        user_id=user_id, category=category, pattern=pattern,
        source=source, strength=1.0, occurrences=1,
        created_at=datetime.now().isoformat(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "created": True}
