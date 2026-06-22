"""Tests for tool registry and execution."""
import importlib, os, tempfile
import pytest
import app.db, app.models

@pytest.fixture
def ctx():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        old = os.environ.get("MBCLAW_DB_PATH")
        os.environ["MBCLAW_DB_PATH"] = db_path; os.environ["MBCLAW_LLM_MOCK"]="1"
        importlib.reload(app.db); importlib.reload(app.models)
        importlib.reload(importlib.import_module("app.tools"))
        app.db.init_db()
        from app.tools import list_tools, get_tool, search_tools, execute, bump_usage
        db = app.db.SessionLocal()
        yield {"db":db,"list":list_tools,"get":get_tool,"search":search_tools,"exec":execute,"bump":bump_usage}
        db.close()
        if old: os.environ["MBCLAW_DB_PATH"] = old

def test_seed(ctx): assert len(ctx["list"](ctx["db"])) >= 17
def test_category(ctx): assert all(t["category"]=="file" for t in ctx["list"](ctx["db"],category="file"))
def test_detail(ctx): assert ctx["get"](ctx["db"],1)["name"] == "read_file"
def test_search(ctx): assert any("memory" in r["name"] for r in ctx["search"](ctx["db"],"memory"))
def test_read(ctx):
    with open("/tmp/_t.txt","w") as f: f.write("hello")
    assert "hello" in ctx["exec"](ctx["db"],"read_file","/tmp/_t.txt")
def test_write(ctx):
    ctx["exec"](ctx["db"],"write_file","/tmp/_tw.txt\n测试")
    assert open("/tmp/_tw.txt").read()=="测试"
def test_cmd(ctx): assert "tooltest" in ctx["exec"](ctx["db"],"run_command","echo tooltest")
def test_classify(ctx): assert "技术选型" in ctx["exec"](ctx["db"],"classify_content","用SQLite还是PostgreSQL")
def test_keywords(ctx): assert "SQLite" in ctx["exec"](ctx["db"],"extract_keywords","使用SQLite FTS5")
def test_device(ctx): assert "Python" in ctx["exec"](ctx["db"],"get_device_info","")
def test_unknown(ctx): assert "未知工具" in ctx["exec"](ctx["db"],"blah","")
def test_bump(ctx): ctx["bump"](ctx["db"],"read_file"); assert ctx["get"](ctx["db"],1)["usage_count"]>=1
def test_write_error(ctx): assert "需要" in ctx["exec"](ctx["db"],"write_file","/tmp/x")  # missing content
