import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.encoder import l1_judge

client = TestClient(app)

def test_l1_judge_failure():
    layer, imp = l1_judge("部署失败，报错404")
    assert layer == 'failure'
    assert imp >= 0.85

def test_l1_judge_decision():
    layer, imp = l1_judge("我决定用SQLite")
    assert layer == 'decision'

def test_l1_judge_none():
    layer, imp = l1_judge("好的")
    assert layer is None

def _skip_test_memory_search_api():
    from app.phase1_db import run_migration
    run_migration()
    resp = client.post('/memory/search', json={'query':'test','workspace_id':1})
    assert resp.status_code == 200
    assert 'items' in resp.json()

def _skip_test_memory_failures_api():
    from app.phase1_db import run_migration
    run_migration()
    resp = client.get('/memory/failures?ws=1')
    assert resp.status_code == 200
