"""T?? — In-memory metrics for R1.1 monitoring.

Tracks session count, search hit rate, LLM error rate.
All counters are process-local; no persistence needed for R1.
"""

from threading import Lock

_lock = Lock()
_counters: dict[str, int] = {}


def _inc(key: str, delta: int = 1) -> None:
    with _lock:
        _counters[key] = _counters.get(key, 0) + delta


def _get(key: str) -> int:
    with _lock:
        return _counters.get(key, 0)


# ── public API ──────────────────────────────────────────────

def record_session_created() -> None:
    _inc("sessions_created")


def record_session_closed() -> None:
    _inc("sessions_closed")


def record_search(q: str, hit_count: int) -> None:
    _inc("searches_total")
    if hit_count > 0:
        _inc("searches_hit")


def record_llm_success() -> None:
    _inc("llm_successes")


def record_llm_error() -> None:
    _inc("llm_errors")


def snapshot() -> dict:
    """Return current metrics snapshot for /metrics endpoint."""
    with _lock:
        total = _counters.get("searches_total", 0)
        hits = _counters.get("searches_hit", 0)
        llm_ok = _counters.get("llm_successes", 0)
        llm_err = _counters.get("llm_errors", 0)

    return {
        "sessions_created": _counters.get("sessions_created", 0),
        "sessions_closed": _counters.get("sessions_closed", 0),
        "searches_total": total,
        "searches_hit": hits,
        "search_hit_rate": round(hits / total, 3) if total > 0 else None,
        "llm_successes": llm_ok,
        "llm_errors": llm_err,
        "llm_error_rate": round(llm_err / (llm_ok + llm_err), 3) if (llm_ok + llm_err) > 0 else None,
    }
