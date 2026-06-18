from fastapi import APIRouter

from app.services.startup_checker import run_startup_checks, get_health_report

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """Full system health check. Runs all 5 phases."""
    return await run_startup_checks()


@router.get("/health/summary")
def health_summary():
    """Quick health summary from last check (no re-run)."""
    report = get_health_report()
    if report is None:
        return {"status": "unknown", "detail": "Startup checks not yet run"}
    return report
