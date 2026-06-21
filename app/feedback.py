"""Feedback System — collect, store, and aggregate user feedback."""

from sqlalchemy.orm import Session as DBSession

from app.models import Feedback


def submit_feedback(
    db: DBSession,
    session_id: int,
    rating: int,
    category: str = "general",
    comment: str = "",
) -> dict:
    """Record user feedback for a session."""
    if not 1 <= rating <= 5:
        raise ValueError(f"Rating must be 1-5, got {rating}")

    fb = Feedback(
        session_id=session_id,
        rating=rating,
        category=category,
        comment=comment[:500],
    )
    db.add(fb)
    db.commit()

    return {
        "id": fb.id,
        "session_id": session_id,
        "rating": rating,
        "category": category,
        "created_at": fb.created_at.isoformat(),
    }


def get_feedback_stats(db: DBSession) -> dict:
    """Aggregate feedback statistics."""
    total = db.query(Feedback).count()
    if total == 0:
        return {"total": 0, "avg_rating": None, "by_category": {}}

    from sqlalchemy import func
    avg = db.query(func.avg(Feedback.rating)).scalar()
    by_cat = dict(
        db.query(Feedback.category, func.count(Feedback.id))
        .group_by(Feedback.category)
        .all()
    )

    return {
        "total": total,
        "avg_rating": round(avg, 2) if avg else None,
        "by_category": by_cat,
    }
