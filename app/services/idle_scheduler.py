import asyncio
import threading
import time
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.models.session import Session
from app.services.classification_service import classify_session
from app.services.memory_service import dream

_last_request_time = time.time()
_last_curation_time = 0.0   # epoch timestamp of last curation run
CURATION_INTERVAL = 86400   # 24 hours
_lock = threading.Lock()
_scheduler_started = False


def mark_request():
    """Called by middleware on every API request."""
    global _last_request_time
    with _lock:
        _last_request_time = time.time()


def _get_idle_seconds() -> float:
    with _lock:
        return time.time() - _last_request_time


async def _idle_loop(idle_threshold: int = 120, check_interval: int = 30):
    """Background loop: when idle > threshold, classify unclassified sessions."""
    while True:
        await asyncio.sleep(check_interval)
        if _get_idle_seconds() < idle_threshold:
            continue

        db = SessionLocal()
        try:
            # Classify sessions that have status=completed but no classification node
            unclassified = (
                db.query(Session)
                .filter(
                    Session.status == "completed",
                    ~Session.classification_nodes.any(),
                )
                .limit(5)
                .all()
            )
            for sess in unclassified:
                try:
                    classify_session(db, sess)
                except Exception:
                    pass

            # Run dreaming for projects with recent activity
            from app.models.project import Project
            projects = db.query(Project).all()
            for proj in projects:
                try:
                    dream(db, proj)
                except Exception:
                    pass

            # H4: Curator — run once per 24h
            _run_curator_if_needed(db)
        finally:
            db.close()


def _run_curator_if_needed(db: DBSession):
    global _last_curation_time
    now = time.time()
    if now - _last_curation_time >= CURATION_INTERVAL:
        try:
            from app.services.curator import run_curation
            run_curation(db)
            _last_curation_time = now
        except Exception:
            pass


def start_idle_scheduler(idle_threshold: int = 120, check_interval: int = 30):
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_idle_loop(idle_threshold, check_interval))
    t = threading.Thread(target=_run, daemon=True)
    t.start()
