"""R1.1 — Unit tests for app.metrics."""

import importlib

import app.metrics


def setup_module():
    importlib.reload(app.metrics)


def test_snapshot_starts_empty():
    s = app.metrics.snapshot()
    assert s["sessions_created"] == 0
    assert s["searches_total"] == 0
    assert s["search_hit_rate"] is None
    assert s["llm_error_rate"] is None


def test_record_session_created():
    app.metrics.record_session_created()
    assert app.metrics.snapshot()["sessions_created"] == 1


def test_record_session_closed():
    app.metrics.record_session_closed()
    assert app.metrics.snapshot()["sessions_closed"] >= 1


def test_record_search_hit():
    app.metrics.record_search("q", 3)
    s = app.metrics.snapshot()
    assert s["searches_total"] >= 1
    assert s["searches_hit"] >= 1
    assert s["search_hit_rate"] is not None


def test_record_search_miss():
    app.metrics.record_search("q", 0)
    s = app.metrics.snapshot()
    assert s["search_hit_rate"] is not None and s["search_hit_rate"] < 1.0


def test_record_llm_success():
    app.metrics.record_llm_success()
    assert app.metrics.snapshot()["llm_successes"] >= 1


def test_record_llm_error():
    app.metrics.record_llm_error()
    s = app.metrics.snapshot()
    assert s["llm_errors"] >= 1
    assert s["llm_error_rate"] is not None and s["llm_error_rate"] > 0


def test_thread_safety():
    import threading
    errors = []

    def bump():
        try:
            for _ in range(100):
                app.metrics.record_session_created()
        except Exception as e:
            errors.append(e)

    ts = [threading.Thread(target=bump) for _ in range(10)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors
