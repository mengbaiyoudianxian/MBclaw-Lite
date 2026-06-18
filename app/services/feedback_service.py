"""F1: Feedback service — collect, store, analyze user ratings."""

import json
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.feedback import Feedback, ApproachSuccessRate
from app.models.user_profile import UserProfile
from app.services.psychology_engine import (
    update_profile_from_feedback, generate_persona_block,
)


def create_feedback(db: DBSession, project_id: int, session_id: int | None,
                    overall_rating: int, helpfulness: int = 0,
                    accuracy: int = 0, speed: int = 0, clarity: int = 0,
                    what_went_well: str = "", what_to_improve: str = "",
                    free_text: str = "", solicited: str = "auto",
                    task_id: int | None = None) -> Feedback:
    fb = Feedback(
        project_id=project_id,
        session_id=session_id,
        task_id=task_id,
        overall_rating=overall_rating,
        helpfulness=helpfulness,
        accuracy=accuracy,
        speed=speed,
        clarity=clarity,
        what_went_well=what_went_well,
        what_to_improve=what_to_improve,
        free_text=free_text,
        solicited=solicited,
        created_at=datetime.now().isoformat(),
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def get_feedback_for_session(db: DBSession, session_id: int) -> list[Feedback]:
    return db.query(Feedback).filter(Feedback.session_id == session_id).all()


def get_feedback_for_project(db: DBSession, project_id: int,
                             limit: int = 50) -> list[Feedback]:
    return db.query(Feedback).filter(
        Feedback.project_id == project_id
    ).order_by(Feedback.created_at.desc()).limit(limit).all()


def get_feedback_stats(db: DBSession, project_id: int) -> dict:
    """Aggregate stats for a project."""
    all_fb = db.query(Feedback).filter(
        Feedback.project_id == project_id
    ).all()

    if not all_fb:
        return {"total": 0, "avg_rating": 0, "avg_helpfulness": 0,
                "avg_accuracy": 0, "avg_speed": 0, "avg_clarity": 0}

    n = len(all_fb)
    return {
        "total": n,
        "avg_rating": round(sum(f.overall_rating for f in all_fb) / n, 2),
        "avg_helpfulness": round(sum(f.helpfulness for f in all_fb if f.helpfulness) / max(1, sum(1 for f in all_fb if f.helpfulness)), 2),
        "avg_accuracy": round(sum(f.accuracy for f in all_fb if f.accuracy) / max(1, sum(1 for f in all_fb if f.accuracy)), 2),
        "avg_speed": round(sum(f.speed for f in all_fb if f.speed) / max(1, sum(1 for f in all_fb if f.speed)), 2),
        "avg_clarity": round(sum(f.clarity for f in all_fb if f.clarity) / max(1, sum(1 for f in all_fb if f.clarity)), 2),
    }


def update_approach_success_rate(db: DBSession, project_id: int,
                                 approach_name: str, success: bool,
                                 rating: int = 0) -> ApproachSuccessRate:
    """Update success rate tracking for a specific approach."""
    asr = db.query(ApproachSuccessRate).filter(
        ApproachSuccessRate.project_id == project_id,
        ApproachSuccessRate.approach_name == approach_name,
    ).first()

    if not asr:
        asr = ApproachSuccessRate(project_id=project_id, approach_name=approach_name,
                                  total_attempts=0, successes=0, failures=0, avg_rating=0.0)
        db.add(asr)
        db.flush()

    asr.total_attempts = (asr.total_attempts or 0) + 1
    if success:
        asr.successes = (asr.successes or 0) + 1
    else:
        asr.failures = (asr.failures or 0) + 1

    if rating > 0:
        # Weighted moving average
        old_weight = asr.total_attempts - 1
        new_weight = 1
        asr.avg_rating = round(
            (asr.avg_rating * old_weight + rating * new_weight) / asr.total_attempts, 2
        )

    asr.updated_at = datetime.now().isoformat()
    db.commit()
    db.refresh(asr)
    return asr


def get_approach_ranking(db: DBSession, project_id: int) -> list[dict]:
    """Rank approaches by success rate."""
    approaches = db.query(ApproachSuccessRate).filter(
        ApproachSuccessRate.project_id == project_id
    ).all()

    # Sort in Python since success_rate is a @property, not a column
    approaches.sort(key=lambda a: a.success_rate, reverse=True)

    return [{
        "approach": a.approach_name,
        "success_rate": round(a.success_rate, 3),
        "total_attempts": a.total_attempts,
        "successes": a.successes,
        "failures": a.failures,
        "avg_rating": a.avg_rating,
    } for a in approaches]


def solicitation_message(project_name: str = "", session_title: str = "") -> dict:
    """Generate the auto-solicitation message after session complete.

    Returns a message the agent can send to ask for feedback.
    """
    context = f"关于'{session_title}'" if session_title else ""
    return {
        "solicit": True,
        "message": f"hi～ 刚才{context}的任务做完了！能给我打个分吗？（1-5分）\n"
                   f"可以从这几个方面评价："
                   f"帮助程度 / 准确性 / 速度 / 表达清晰度\n"
                   f"也可以直接告诉我哪里做得好、哪里需要改进～",
        "rating_fields": ["overall_rating", "helpfulness", "accuracy", "speed", "clarity"],
    }
