
import pytest, json
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.phase1_db import write_raw, search_fts, run_migration
from app.encoder import l1_judge, MemoryEncoder
from app.phase4_failure import classify_failure
from app.context.builder import ContextBuilder
from app.correction import correct_memory
from app.schema_validator import validate_memory_output, safe_parse
from app.phase1_models import MemoryNode
from app.phase3_consolidation import ConsolidationEngine
from app.llm import LLMClient
import os

run_migration()
client = TestClient(app)

def test_write_and_search():
    db = SessionLocal()
    write_raw(db, 1, "user", "database connection pool exhausted 500 error")
    db.close()
    r = search_fts("数据库连接池", 1, 5)
    assert len(r) > 0

def test_l1_failure_detect():
    layer, imp = l1_judge("deploy to k8s error ImagePullBackOff")
    assert layer == "failure"

def test_failure_classify():
    assert classify_failure("connection timeout") == "environmental"

def test_api_search():
    resp = client.post("/memory/search", json={"query":"test","workspace_id":1})
    assert resp.status_code == 200

def test_api_failures():
    resp = client.get("/memory/failures?ws=1")
    assert resp.status_code == 200

def test_context_builder():
    db = SessionLocal()
    ctx, ids = ContextBuilder(db).build(1, "test")
    assert len(ctx) <= 800
    db.close()

def test_consolidation():
    db = SessionLocal()
    r = ConsolidationEngine(db).daily(1)
    assert r["total_raws"] >= 0
    db.close()

def test_schema_valid():
    ok, _ = validate_memory_output('{"episodes":[],"semantics":[],"procedures":[],"failures":[]}')
    assert ok

def test_correction():
    db = SessionLocal()
    nodes = db.query(MemoryNode).limit(1).all()
    if nodes:
        result = correct_memory(db, nodes[0].id, "wrong")
        assert result["quality_score"] == 0.0
    db.close()
