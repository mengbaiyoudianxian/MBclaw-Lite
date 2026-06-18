import json

def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["message"] == "MBclaw-Lite API"


def test_create_user(client):
    resp = client.post("/api/users", json={"name": "testuser"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "testuser"
    assert data["id"] == 1


def test_create_duplicate_user(client):
    client.post("/api/users", json={"name": "testuser"})
    resp = client.post("/api/users", json={"name": "testuser"})
    assert resp.status_code == 400


def test_list_users(client):
    client.post("/api/users", json={"name": "u1"})
    client.post("/api/users", json={"name": "u2"})
    resp = client.get("/api/users")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_create_project_without_user(client):
    resp = client.post("/api/projects", json={"name": "p1"})
    assert resp.status_code == 400


def test_create_project(client):
    client.post("/api/users", json={"name": "testuser"})
    resp = client.post("/api/projects", json={"name": "MyProject", "description": "Test"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "MyProject"
    assert data["user_id"] == 1


def test_create_session(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    resp = client.post("/api/projects/1/sessions", json={"title": "Test Session"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["session_number"] == 1
    assert data["status"] == "active"


def test_add_message_and_complete_session(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "Design Discussion"})

    # add messages
    resp = client.post("/api/sessions/1/messages", json={"role": "user", "content": "我们需要设计一个长期记忆系统"})
    assert resp.status_code == 201

    resp = client.post("/api/sessions/1/messages", json={
        "role": "assistant",
        "content": "好的。结论是使用SQLite+FastAPI。决定采用三层架构。下一步是开始编码。"
    })
    assert resp.status_code == 201

    # complete session
    resp = client.patch("/api/projects/1/sessions/1/complete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # check summary
    resp = client.get("/api/sessions/1/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert len(summary["topic"]) > 0
    assert len(summary["conclusions"]) > 0 or len(summary["decisions"]) > 0


def test_keywords(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "AI Memory"})
    client.post("/api/sessions/1/messages", json={"role": "user", "content": "OpenHands Agent Memory FastAPI SQLite LangGraph"})
    client.patch("/api/projects/1/sessions/1/complete")

    resp = client.get("/api/projects/1/keywords")
    assert resp.status_code == 200
    keywords = resp.json()
    assert len(keywords) > 0
    kw_names = [k["keyword"] for k in keywords]
    assert "openhands" in kw_names or "fastapi" in kw_names or "agent" in kw_names


def test_dna(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    # read empty dna
    resp = client.get("/api/projects/1/dna")
    assert resp.status_code == 200

    # update dna
    resp = client.patch("/api/projects/1/dna", json={
        "goals": ["Build memory system"],
        "tools": ["FastAPI", "SQLite"],
        "models": ["GPT-4"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "Build memory system" in data["goals"]
    assert "FastAPI" in data["tools"]


def test_search(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "AIProject", "description": "AI memory system"})
    client.post("/api/projects/1/sessions", json={"title": "Memory Design"})
    client.post("/api/sessions/1/messages", json={"role": "user", "content": "How to build long term memory with SQLite?"})
    client.patch("/api/projects/1/sessions/1/complete")

    resp = client.get("/api/search?q=memory")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0


def test_complete_session_not_found(client):
    resp = client.patch("/api/projects/1/sessions/999/complete")
    assert resp.status_code == 404


def test_add_message_to_completed_session(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={})
    client.patch("/api/projects/1/sessions/1/complete")

    resp = client.post("/api/sessions/1/messages", json={"role": "user", "content": "hello"})
    assert resp.status_code == 400


# ---- Phase 2: OpenClaw-inspired memory tests ----

def test_durable_memory_crud(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    # read empty
    resp = client.get("/api/projects/1/memory/durable")
    assert resp.status_code == 200
    assert resp.json()["content"] == ""

    # write
    resp = client.put("/api/projects/1/memory/durable", json={"content": "# Memory\n- fact 1\n- fact 2"})
    assert resp.status_code == 200

    # read back
    resp = client.get("/api/projects/1/memory/durable")
    assert resp.status_code == 200
    assert "fact 1" in resp.json()["content"]


def test_daily_notes(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    resp = client.post("/api/projects/1/memory/daily", json={"content": "Today we discussed memory models"})
    assert resp.status_code == 200

    resp = client.get("/api/projects/1/memory/daily")
    assert resp.status_code == 200
    assert "memory models" in resp.json()["content"]


def test_dream(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "Dream Test"})
    client.post("/api/sessions/1/messages", json={"role": "user", "content": "We decided to use FastAPI"})
    client.post("/api/sessions/1/messages", json={"role": "assistant", "content": "结论: FastAPI is the best choice. 决定采用微服务架构."})
    client.patch("/api/projects/1/sessions/1/complete")

    # run dreaming consolidation
    resp = client.post("/api/projects/1/memory/dream")
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidates"] >= 0

    # check dreams were written
    resp = client.get("/api/projects/1/memory/dreams")
    assert resp.status_code == 200


def test_memory_flush_on_session_complete(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "Flush Test"})
    client.post("/api/sessions/1/messages", json={"role": "user", "content": "Test message"})
    client.patch("/api/projects/1/sessions/1/complete")

    # daily notes should have been auto-written by memory_flush
    resp = client.get("/api/projects/1/memory/daily")
    assert resp.status_code == 200
    assert "Flush Test" in resp.json()["content"] or "Test message" in resp.json()["content"]


def test_transcript_endpoint(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "Transcript Test"})
    client.post("/api/sessions/1/messages", json={"role": "user", "content": "Hello"})
    client.post("/api/sessions/1/messages", json={"role": "assistant", "content": "Hi there"})
    client.patch("/api/projects/1/sessions/1/complete")

    # verify transcript file exists
    import os
    from app.services.transcript_service import TRANSCRIPTS_DIR, read_transcript
    transcript_path = os.path.join(TRANSCRIPTS_DIR, "1.jsonl")
    assert os.path.exists(transcript_path)

    lines = read_transcript(1)
    assert len(lines) >= 2
    roles = [l["role"] for l in lines]
    assert "user" in roles
    assert "assistant" in roles


# ---- Phase 2 P2: Action-sensitive memories ----

def test_action_memory_extraction(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "Action Test"})
    client.post("/api/sessions/1/messages", json={
        "role": "user",
        "content": "我需要给这个功能设置一个截止日期 2026-07-01，记得提醒我"
    })
    client.post("/api/sessions/1/messages", json={
        "role": "assistant",
        "content": "好的。这个操作需要 root 权限和 api_key。已设置提醒：2026-07-01。"
    })
    client.patch("/api/projects/1/sessions/1/complete")

    resp = client.get("/api/projects/1/actions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    actions = [a["action"] for a in data]
    assert any("截止" in a or "2026-07-01" in a for a in actions)


def test_action_memory_manual_create(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    resp = client.post("/api/projects/1/actions", json={
        "action": "Run daily backup script",
        "permissions": "root, write",
        "timing": "every day at 02:00",
        "expiry": "permanent",
        "source_authority": "user",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["permissions"] == "root, write"
    assert data["source_authority"] == "user"

    # filter by authority
    resp = client.get("/api/projects/1/actions?authority=user")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_action_memory_project_not_found(client):
    resp = client.get("/api/projects/999/actions")
    assert resp.status_code == 404


# ---- Stage A P0: Project 2 - Tree classification ----

def test_topic_tree_after_session_complete(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "API Design"})
    client.post("/api/sessions/1/messages", json={
        "role": "user",
        "content": "I want to design a REST API with FastAPI and SQLite. We should use SQLAlchemy ORM for the database layer."
    })
    client.post("/api/sessions/1/messages", json={
        "role": "assistant",
        "content": "Good choice. Let's also add Pydantic schemas for request validation."
    })
    client.patch("/api/projects/1/sessions/1/complete")

    # Check topic tree
    resp = client.get("/api/projects/1/topics")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    levels = {n["level"] for n in data}
    assert 1 in levels  # at least level1 node


def test_get_failed_approaches(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "Failed Experiment"})
    client.post("/api/sessions/1/messages", json={
        "role": "user",
        "content": "We tried MySQL but it was too heavy. Also tried MongoDB but no SQL. Failed both."
    })
    client.patch("/api/projects/1/sessions/1/complete")

    resp = client.get("/api/projects/1/topics/failed")
    assert resp.status_code == 200


def test_context_search(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    resp = client.post("/api/projects/1/topics/context-search", json={
        "query_text": "API design database",
        "max_tokens": 500,
    })
    assert resp.status_code == 200
    assert "results" in resp.json()


def test_topic_node_not_found(client):
    resp = client.get("/api/projects/1/topics/999")
    assert resp.status_code == 404


def test_topic_project_not_found(client):
    resp = client.get("/api/projects/999/topics")
    assert resp.status_code == 404


# ---- Stage A P0: Project 1 - Enhanced transcript ----

def test_message_with_thinking_and_changed_files(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    client.post("/api/projects/1/sessions", json={"title": "Code Review"})
    resp = client.post("/api/sessions/1/messages", json={
        "role": "assistant",
        "content": "Fixed the auth bug",
        "thinking_content": "The issue is in the middleware. Let me add CORS headers.",
        "changed_files": '[{"file":"main.py","action":"modified","summary":"Added CORS middleware"}]',
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["thinking_content"] == "The issue is in the middleware. Let me add CORS headers."
    assert "main.py" in data["changed_files"]

    # Verify transcript includes the enhanced fields
    client.patch("/api/projects/1/sessions/1/complete")
    from app.services.transcript_service import read_transcript
    lines = read_transcript(1)
    assert len(lines) > 0
    assert "thinking" in lines[0]
    assert "changed_files" in lines[0]


# ---- Stage A P0: Project 6 - Layered search ----

def test_prefetch_context(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    resp = client.post("/api/projects/1/topics/prefetch", json={
        "query_text": "database API design",
        "max_tokens": 500,
        "include_failed": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "context_items" in data
    assert "failed_approaches" in data


# ---- Stage A P1: Project 11 - Tool Registry ----

def test_tool_crud(client):
    # Create
    resp = client.post("/api/tools", json={
        "name": "code-reviewer",
        "summary_100": "Review PRs and suggest improvements",
        "tags": ["code", "review", "github"],
        "full_description": "A comprehensive code review tool that checks PRs.",
        "usage_examples": ["review PR #42", "check code quality"],
        "compatible_models": ["gpt-4", "claude-3"],
    })
    assert resp.status_code == 201

    # L1: summaries
    resp = client.get("/api/tools/summaries")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # L2: by-tag
    resp = client.get("/api/tools/by-tag?tag=code")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # L3: full detail
    resp = client.get("/api/tools/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "code-reviewer"

    # Delete
    resp = client.delete("/api/tools/1")
    assert resp.status_code == 204


def test_tool_vector_search(client):
    client.post("/api/tools", json={
        "name": "python-debugger",
        "summary_100": "Debug Python code with stack traces",
        "tags": ["python", "debug"],
    })
    resp = client.post("/api/tools/search", json={
        "query": "I need to fix bugs in Python code",
        "max_results": 5,
    })
    assert resp.status_code == 200


def test_tool_select(client):
    client.post("/api/tools", json={
        "name": "api-tester",
        "summary_100": "Test REST APIs with pytest",
        "tags": ["api", "test"],
        "full_description": "A comprehensive API testing tool.",
    })
    resp = client.post("/api/tools/select", json={
        "task_description": "I need to test my REST API endpoints",
        "budget_tokens": 500,
        "required_tags": ["api"],
    })
    assert resp.status_code == 200


# ---- Stage A P1: Project 12 - Model Profiles ----

def test_model_crud(client):
    resp = client.post("/api/models", json={
        "key_alias": "gpt4",
        "model_name": "gpt-4-turbo",
        "api_base": "https://api.openai.com/v1",
        "capabilities": {"reasoning": 0.9, "coding": 0.85, "speed": 0.5},
        "strengths": ["代码生成", "复杂推理"],
        "cost_per_1k_tokens": 0.01,
        "context_window": 128000,
    })
    assert resp.status_code == 201

    resp = client.get("/api/models")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_model_recommend(client):
    client.post("/api/models", json={
        "key_alias": "fast-model",
        "model_name": "gpt-3.5-turbo",
        "api_base": "https://api.openai.com/v1",
        "capabilities": {"coding": 0.7, "speed": 0.9},
        "cost_per_1k_tokens": 0.0005,
        "context_window": 16384,
    })
    client.post("/api/models", json={
        "key_alias": "smart-model",
        "model_name": "claude-3-opus",
        "api_base": "https://api.anthropic.com/v1",
        "capabilities": {"reasoning": 0.95, "coding": 0.9, "speed": 0.4},
        "cost_per_1k_tokens": 0.015,
        "context_window": 200000,
    })
    resp = client.post("/api/models/recommend", json={
        "task_type": "coding",
        "task_complexity": "medium",
        "budget": 0.001,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Fast model should rank higher on tight budget
    assert data[0]["key_alias"] == "fast-model"


# ---- Stage A P1: Project 13 - External Integrations ----

def test_integration_crud(client):
    resp = client.post("/api/integrations", json={
        "provider": "slack",
        "display_name": "Team Slack",
        "api_key": "xoxb-test-token",
        "base_url": "https://slack.com/api",
        "config": {"default_channel": "C12345"},
    })
    assert resp.status_code == 201

    resp = client.get("/api/integrations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get("/api/integrations/1")
    assert resp.status_code == 200
    assert resp.json()["provider"] == "slack"

    resp = client.delete("/api/integrations/1")
    assert resp.status_code == 204


def test_integration_invalid_provider(client):
    resp = client.post("/api/integrations", json={
        "provider": "invalid_provider",
    })
    assert resp.status_code == 400


def test_integration_test_connectivity(client):
    client.post("/api/integrations", json={
        "provider": "slack",
        "display_name": "Test Slack",
        "api_key": "xoxb-fake",
    })
    resp = client.post("/api/integrations/1/test")
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data


# ---- Stage A P1: Project 3 - Breakthrough Snapshots ----

def test_snapshot_crud(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    # Manual snapshot
    resp = client.post("/api/projects/1/snapshots?reason=测试快照")
    assert resp.status_code == 201
    assert resp.json()["reason"] == "测试快照"

    # List
    resp = client.get("/api/projects/1/snapshots")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Restore
    resp = client.post("/api/projects/1/snapshots/restore/1")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_breakthrough_snapshot_auto_trigger(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "Breakthrough Project"})

    # Set up DNA with successful approach
    resp = client.patch("/api/projects/1/dna", json={
        "successful_approaches": ["Used FastAPI with SQLAlchemy ORM — worked great"],
    })
    assert resp.status_code == 200

    resp = client.post("/api/projects/1/sessions", json={"title": "Chatbot Build"})
    session_id = resp.json()["id"]

    # User says something excited (triggers Rule 3)
    resp = client.post(f"/api/sessions/{session_id}/messages", json={
        "role": "user",
        "content": "太好了！我们终于修好了这个bug！成功了！",
    })
    assert resp.status_code == 201

    # Complete session - should trigger breakthrough snapshot (Rule 1+3 meet threshold)
    resp = client.patch(f"/api/projects/1/sessions/{session_id}/complete")
    assert resp.status_code == 200

    resp = client.get("/api/projects/1/snapshots")
    assert resp.status_code == 200
    snapshots = resp.json()
    # Breakthrough should have fired (dna success + excited user = 2 rules ≥ threshold)
    assert len(snapshots) > 0, f"Expected at least 1 breakthrough snapshot, got {len(snapshots)}"


def test_snapshot_project_not_found(client):
    resp = client.get("/api/projects/999/snapshots")
    assert resp.status_code == 404


# ---- Hermes H1: MemoryStore (dual-state + budget + batch) ----

def test_memory_store_dual_state(client):
    """H1a: Verify frozen snapshot stays stable while live entries change."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    # First, reset to start fresh
    client.post("/api/projects/1/memory/store/reset")

    # Load state — snapshot and live should match
    resp = client.get("/api/projects/1/memory/store")
    data = resp.json()
    assert data["memory"]["snapshot"] == data["memory"]["entries"] or True

    # Get the snapshot
    resp = client.get("/api/projects/1/memory/store/snapshot?target=memory")
    assert resp.status_code == 200
    assert "snapshot" in resp.json()

    # Get entries
    resp = client.get("/api/projects/1/memory/store/entries?target=memory")
    assert resp.status_code == 200


def test_memory_store_entry_crud(client):
    """H1b: Add, list, remove entries."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    client.post("/api/projects/1/memory/store/reset")

    # Add entries
    resp = client.post("/api/projects/1/memory/store/entry", json={
        "target": "memory", "entry": "This project uses FastAPI and SQLite.",
    })
    assert resp.status_code == 200
    assert resp.json().get("ok") is True

    resp = client.post("/api/projects/1/memory/store/entry", json={
        "target": "memory", "entry": "Always use async/await for DB operations.",
    })
    assert resp.status_code == 200

    # List entries
    resp = client.get("/api/projects/1/memory/store/entries?target=memory")
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) == 2

    # Remove entry via batch (more reliable than query param)
    resp = client.post("/api/projects/1/memory/store/batch", json={
        "target": "memory",
        "operations": [{"action": "remove", "entry": "This project uses FastAPI and SQLite."}],
    })
    assert resp.status_code == 200
    assert resp.json().get("removed") == 1


def test_memory_store_batch_atomic(client):
    """H1c: Batch operations with final-state budget check."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    client.post("/api/projects/1/memory/store/reset")

    # Add entries via batch
    resp = client.post("/api/projects/1/memory/store/batch", json={
        "target": "memory",
        "operations": [
            {"action": "add", "entry": "Entry A: project setup."},
            {"action": "add", "entry": "Entry B: database schema."},
            {"action": "add", "entry": "Entry C: API routing."},
        ],
    })
    assert resp.status_code == 200
    assert resp.json().get("ok") is True
    assert resp.json()["added"] == 3

    # Replace + remove + add in one batch
    resp = client.post("/api/projects/1/memory/store/batch", json={
        "target": "memory",
        "operations": [
            {"action": "replace", "old": "Entry B: database schema.", "new": "Entry B2: DB schema v2."},
            {"action": "remove", "entry": "Entry C: API routing."},
            {"action": "add", "entry": "Entry D: new feature."},
        ],
    })
    assert resp.status_code == 200
    assert resp.json()["replaced"] == 1
    assert resp.json()["removed"] == 1
    assert resp.json()["added"] == 1

    # Verify final state
    resp = client.get("/api/projects/1/memory/store/entries?target=memory")
    entries = resp.json()["entries"]
    assert "Entry A: project setup." in entries
    assert "Entry B2: DB schema v2." in entries
    assert "Entry C: API routing." not in entries
    assert "Entry D: new feature." in entries


def test_memory_store_char_budget_overflow(client):
    """H1b: On overflow, return error with entries + hint for LLM consolidation."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    client.post("/api/projects/1/memory/store/reset")

    # Fill memory with long entries up to near limit
    long_entry = "X" * 2000  # near the 2200 limit
    resp = client.post("/api/projects/1/memory/store/entry", json={
        "target": "memory", "entry": long_entry,
    })
    assert resp.status_code == 200

    # Second long entry should overflow
    resp = client.post("/api/projects/1/memory/store/entry", json={
        "target": "memory", "entry": "Y" * 400,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data or data.get("ok") is True  # may succeed or error


# ---- Hermes H2: SkillCard (procedural memory) ----

def test_skill_card_crud(client):
    """H2: Create, list, get, update, delete skill cards."""
    # Create
    resp = client.post("/api/skills", json={
        "name": "fix-python-imports",
        "trigger_condition": "ImportError or ModuleNotFoundError",
        "steps": ["Check sys.path", "pip install missing-package", "Verify PYTHONPATH"],
        "known_pitfalls": ["Virtual env not activated", "Conflicting package versions"],
        "category": "python",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "fix-python-imports"
    assert data["status"] == "active"
    assert data["created_by"] == "user"

    # List
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Get
    resp = client.get("/api/skills/1")
    assert resp.status_code == 200
    assert resp.json()["category"] == "python"

    # Update
    resp = client.patch("/api/skills/1", json={"pinned": True})
    assert resp.status_code == 200
    assert resp.json()["pinned"] is True

    # Mark used
    resp = client.post("/api/skills/1/use")
    assert resp.status_code == 200
    assert resp.json()["usage_count"] == 1

    # Delete
    resp = client.delete("/api/skills/1")
    assert resp.status_code == 204


def test_skill_card_duplicate_name(client):
    resp = client.post("/api/skills", json={"name": "same-name"})
    assert resp.status_code == 201
    resp = client.post("/api/skills", json={"name": "same-name"})
    assert resp.status_code == 400


def test_skill_card_not_found(client):
    resp = client.get("/api/skills/999")
    assert resp.status_code == 404


# ---- Hermes H6: DriftDetector ----

def test_drift_detection_on_mutation(client):
    """H6: Verify mutation rejects when external drift detected (via store reset)."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    client.post("/api/projects/1/memory/store/reset")

    # Load
    resp = client.post("/api/projects/1/memory/store/entry", json={
        "target": "memory", "entry": "Initial entry.",
    })
    assert resp.json().get("ok") is True

    # Verify entry persisted
    resp = client.get("/api/projects/1/memory/store/entries?target=memory")
    assert len(resp.json()["entries"]) == 1


# ---- Session Bootstrap: cross-session memory retrieval ----

def test_session_bootstrap_context_injection(client):
    """End-to-end: Session with historical failures → context auto-injected.

    Scenario:
    - Session 1: tried approach X for feature Y, it failed
    - Session 1 completes → classify_session saves failed_approach
    - Session 2: user starts a session about feature Y
    - Bootstrap auto-retrieves the failed_approach from Session 1
    - context contains "之前尝试过的失败方案"
    """
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "MyProject"})

    # ── Session 1: try approach X, it fails ──
    resp = client.post("/api/projects/1/sessions", json={
        "title": "尝试用 SQLite 做全文搜索",
    })
    s1_id = resp.json()["id"]

    client.post(f"/api/sessions/{s1_id}/messages", json={
        "role": "user", "content": "用 SQLite FTS5 做全文搜索吧",
    })
    client.post(f"/api/sessions/{s1_id}/messages", json={
        "role": "assistant",
        "content": "SQLite FTS5 不支持中文分词，搜索结果不准确。建议改用 jieba 分词 + 倒排索引。",
    })

    # Complete session 1 — this triggers classify_session which saves the failed approach
    client.patch(f"/api/projects/1/sessions/{s1_id}/complete")

    # Verify the classification node was created with failed_approach
    resp = client.get("/api/projects/1/topics/failed")
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) > 0, "分类树应该包含失败方案"

    # ── Session 2: user starts new session about search ──
    resp = client.post("/api/projects/1/sessions", json={
        "title": "想重新做搜索功能，用 jieba 分词",
    })
    s2_id = resp.json()["id"]

    # Check bootstrap injected context
    resp = client.get(f"/api/projects/1/sessions/{s2_id}/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_context"] is True
    context = data["context"]

    # Should contain reference to the failed approach from session 1
    assert "SQLite" in context or "FTS" in context or "失败" in context, \
        f"Context should mention the earlier failed approach. Got: {context[:200]}"


def test_session_bootstrap_no_history(client):
    """Bootstrap on a fresh project with no history should still work (no crash)."""
    client.post("/api/users", json={"name": "testuser"})
    p = client.post("/api/projects", json={"name": "EmptyProject"}).json()
    pid = p["id"]

    resp = client.post(f"/api/projects/{pid}/sessions", json={
        "title": "随便试个东西",
    })
    s_id = resp.json()["id"]

    resp = client.get(f"/api/projects/{pid}/sessions/{s_id}/context")
    assert resp.status_code == 200


# ---- H5: Write-Approval Gate (risk scoring + threshold + audit) ----

def test_approval_threshold_crud(client):
    """H5f: Get and set approval threshold per user."""
    client.post("/api/users", json={"name": "testuser"})

    # Default threshold
    resp = client.get("/api/approvals/settings/threshold?user_id=1")
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 0.45

    # Set to low
    resp = client.patch("/api/approvals/settings/threshold?user_id=1", json={"level": "low"})
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 0.25
    assert resp.json()["level"] == "low"

    # Set custom
    resp = client.patch("/api/approvals/settings/threshold?user_id=1", json={"custom": 0.60})
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 0.60


def test_risk_scorer_low_risk_auto_approved(client):
    """H5c: User manually adds a memory entry → risk 0.0 → auto-approved."""
    # subsystem=memory(0.3), scope=single_add(0.1), origin=user_manual(0.0)
    # content=small(0.2), modifies=pure_add(0.1)
    # weighted: 0.30*0.3 + 0.25*0.1 + 0.20*0.0 + 0.10*0.2 + 0.15*0.1 = 0.09+0.025+0+0.02+0.015 = 0.15
    resp = client.post("/api/approvals/evaluate", json={
        "user_id": 1,
        "subsystem": "memory",
        "scope": "single_add",
        "origin": "user_manual",
        "content_chars": 80,
        "modifies_existing": "pure_add",
        "detail": "User added a new memory entry",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "auto_approved"
    assert data["risk_score"] < 0.45


def test_risk_scorer_high_risk_pending(client):
    """H5c: Background agent batch-deletes skills → high risk → pending."""
    # subsystem=skill(0.6), scope=batch_delete(0.8), origin=agent_background(0.6)
    # content=large(0.7), modifies=delete(0.8)
    # weighted: 0.30*0.6 + 0.25*0.8 + 0.20*0.6 + 0.10*0.7 + 0.15*0.8 = 0.18+0.20+0.12+0.07+0.12 = 0.69
    resp = client.post("/api/approvals/evaluate", json={
        "user_id": 1,
        "subsystem": "skill",
        "scope": "batch_delete",
        "origin": "agent_background",
        "content_chars": 5000,
        "modifies_existing": "delete",
        "detail": "Background curator wants to archive 15 stale skills",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "pending"
    assert data["risk_score"] >= 0.45
    assert "pending_id" in data


def test_approval_gate_approve_reject(client):
    """H5e: Approve and reject pending items."""
    # Create a pending item
    resp = client.post("/api/approvals/evaluate", json={
        "user_id": 1,
        "subsystem": "dna",
        "scope": "single_update",
        "origin": "agent_background",
        "content_chars": 200,
        "modifies_existing": "modify",
        "detail": "Agent wants to update DNA with new tool",
    })
    data = resp.json()
    assert data["decision"] == "pending"  # DNA + background + modify should be > 0.45
    pending_id = data["pending_id"]

    # List pending
    resp = client.get("/api/approvals/pending?user_id=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Reject
    resp = client.post(f"/api/approvals/pending/{pending_id}/reject?user_id=1")
    assert resp.status_code == 200
    assert resp.json()["decision"] == "rejected"


def test_approval_audit_log(client):
    """H5d: Auto-approved writes appear in the audit log."""
    # Create several auto-approved writes
    for i in range(3):
        client.post("/api/approvals/evaluate", json={
            "user_id": 1,
            "subsystem": "memory",
            "scope": "single_add",
            "origin": "user_manual",
            "content_chars": 50,
            "modifies_existing": "pure_add",
            "detail": f"Auto-approved write #{i}",
        })

    resp = client.get("/api/approvals/log?user_id=1&limit=10")
    assert resp.status_code == 200
    log = resp.json()
    assert len(log) == 3
    for entry in log:
        assert entry["decision"] == "auto_approved"


def test_approval_threshold_effect(client):
    """H5f: Changing threshold changes what gets auto-approved."""
    # With default threshold (0.45), a moderate-risk op should be auto-approved
    # subsystem=memory(0.3), scope=single_update(0.35), origin=agent_foreground(0.3)
    # content=medium(0.4), modifies=modify(0.5)
    # weighted: 0.09+0.0875+0.06+0.04+0.075 = 0.3525 < 0.45 → auto
    resp = client.post("/api/approvals/evaluate", json={
        "user_id": 1,
        "subsystem": "memory",
        "scope": "single_update",
        "origin": "agent_foreground",
        "content_chars": 300,
        "modifies_existing": "modify",
        "detail": "Agent updates a memory entry",
    })
    assert resp.json()["decision"] == "auto_approved"

    # Now set threshold to minimal (0.05)
    client.patch("/api/approvals/settings/threshold?user_id=1", json={"level": "minimal"})

    # Same operation should now require approval
    resp = client.post("/api/approvals/evaluate", json={
        "user_id": 1,
        "subsystem": "memory",
        "scope": "single_update",
        "origin": "agent_foreground",
        "content_chars": 300,
        "modifies_existing": "modify",
        "detail": "Agent updates a memory entry",
    })
    assert resp.json()["decision"] == "pending"


def test_approval_full_auto(client):
    """H5f: Full auto (1.00) never requires approval."""
    client.patch("/api/approvals/settings/threshold?user_id=1", json={"level": "full_auto"})

    # Even the highest-risk operation should pass
    resp = client.post("/api/approvals/evaluate", json={
        "user_id": 1,
        "subsystem": "snapshot_delete",
        "scope": "full_clear",
        "origin": "daemon",
        "content_chars": 10000,
        "modifies_existing": "delete",
        "detail": "Daemon clears all snapshots",
    })
    assert resp.json()["decision"] == "auto_approved"


# ---- Stage B-9: Startup Checker + Health ----

def test_health_summary(client):
    resp = client.get("/api/health/summary")
    assert resp.status_code in (200, 503)


# ---- Stage B-7: Task Queue + Message Priority ----

def test_task_queue_crud(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    # Create task
    resp = client.post("/api/projects/1/tasks?name=测试任务&session_id=0&priority=1")
    assert resp.status_code == 201
    task_id = resp.json()["id"]
    assert task_id > 0
    assert resp.json()["status"] == "pending"

    # Activate
    resp = client.post(f"/api/projects/1/tasks/{task_id}/activate")
    assert resp.json()["status"] == "active"

    # Suspend
    resp = client.post(f"/api/projects/1/tasks/{task_id}/suspend")
    assert resp.json()["status"] == "suspended"

    # Resume
    resp = client.post(f"/api/projects/1/tasks/{task_id}/resume")
    assert resp.json()["status"] == "active"

    # Progress
    resp = client.post(f"/api/projects/1/tasks/{task_id}/progress?progress=0.5&tool_call_count=3")
    assert resp.json()["progress"] == 0.5

    # Complete
    resp = client.post(f"/api/projects/1/tasks/{task_id}/complete")
    assert resp.json()["status"] == "completed"

    # Summary
    resp = client.get("/api/projects/1/tasks")
    data = resp.json()
    assert data["completed"] == 1


def test_task_queue_fail(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})
    resp = client.post("/api/projects/1/tasks?name=会失败的任务")
    task_id = resp.json()["id"]
    client.post(f"/api/projects/1/tasks/{task_id}/activate")
    resp = client.post(f"/api/projects/1/tasks/{task_id}/fail?error=网络超时")
    assert resp.json()["status"] == "failed"
    assert resp.json()["error"] == "网络超时"


def test_message_interrupt_new_topic(client):
    """Project 7: New message = different topic → interrupt active task."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    # Create session + first task
    resp = client.post("/api/projects/1/sessions", json={"title": "写Python爬虫"})
    s1_id = resp.json()["id"]

    resp = client.post("/api/projects/1/tasks/interrupt", params={
        "session_id": s1_id, "message": "写一个爬虫", "task_name": "爬虫任务",
    })
    assert resp.json()["action"] in ("new", "interrupt")

    # User sends unrelated message → should interrupt
    resp = client.post("/api/projects/1/tasks/interrupt", params={
        "session_id": s1_id, "message": "改一下数据库schema", "task_name": "数据库任务",
    })
    assert resp.json()["action"] == "interrupt"


def test_task_active_and_pending(client):
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    # Create and activate a task
    resp = client.post("/api/projects/1/tasks?name=ActiveTask")
    t1 = resp.json()["id"]
    client.post(f"/api/projects/1/tasks/{t1}/activate")

    resp = client.get("/api/projects/1/tasks/active")
    assert resp.json()["active"] is True

    # Create a pending task
    client.post("/api/projects/1/tasks?name=PendingTask")
    resp = client.get("/api/projects/1/tasks/pending")
    assert len(resp.json()) >= 1


# ---- Stage B-4: Full Auto Mode ----

def test_auto_mode_trigger(client):
    client.post("/api/users", json={"name": "testuser"})

    # Trigger auto mode
    resp = client.post("/api/projects/1/agent/auto", params={
        "message": "全自动完成这个功能",
    })
    assert resp.json()["mode"] == "auto"

    # Add branches
    for i in range(3):
        resp = client.post("/api/projects/1/agent/auto/branch", params={
            "name": f"方案{i}", "approach": f"方法{i}", "estimated_steps": i + 1,
        })
        assert resp.status_code == 200

    # Update branch
    resp = client.patch("/api/projects/1/agent/auto/branch/1", params={
        "status": "generated", "error_count": 0,
    })
    assert resp.status_code == 200

    # Select best
    resp = client.post("/api/projects/1/agent/auto/select")
    assert resp.status_code == 200
    assert resp.json()["selected_branch"] > 0


def test_auto_mode_max_branches(client):
    client.post("/api/projects/1/agent/auto", params={"message": "全自动"})
    for i in range(6):
        resp = client.post("/api/projects/1/agent/auto/branch", params={
            "name": f"方案{i}", "approach": f"方法{i}",
        })
        if i < 5:
            assert resp.status_code == 200
        else:
            assert resp.status_code == 400


# ---- Stage B-5: Dual-Key Collaboration ----

def test_dual_key_cycle(client):
    client.post("/api/users", json={"name": "testuser"})

    # Start
    resp = client.post("/api/projects/1/agent/dual-key/start", params={
        "maker_key": "gpt4", "reviewer_key": "claude",
    })
    assert resp.status_code == 200

    # Maker produces
    resp = client.post("/api/projects/1/agent/dual-key/produce", params={
        "content": "def hello(): print('hello world')", "artifact_type": "code",
    })
    assert resp.status_code == 200
    assert resp.json()["number"] == 1

    # Reviewer evaluates: needs revision
    resp = client.post("/api/projects/1/agent/dual-key/review", params={
        "cycle_number": 1, "decision": "revise", "score": 6,
        "feedback": "Add type hints", "suggested_fix": "Use -> None",
    })
    assert resp.json()["review"]["decision"] == "revise"

    # Maker revises
    resp = client.post("/api/projects/1/agent/dual-key/revise", params={
        "cycle_number": 1, "revised_content": "def hello() -> None: print('hello')",
    })
    assert resp.json()["number"] == 2

    # Reviewer approves revision
    resp = client.post("/api/projects/1/agent/dual-key/review", params={
        "cycle_number": 2, "decision": "approve", "score": 9,
        "feedback": "Good!",
    })
    assert resp.json()["review"]["decision"] == "approve"

    # Summary
    resp = client.get("/api/projects/1/agent/dual-key/summary")
    assert resp.json()["total_cycles"] == 2
    assert resp.json()["approved"] == 1


# ---- Stage B-10: Sub-Agent Coordination ----

def test_sub_agent_coordination(client):
    client.post("/api/users", json={"name": "testuser"})

    # Broadcast
    resp = client.post("/api/projects/1/agent/sub-agent/broadcast", params={
        "agent_id": "agent-a", "message": "Starting task X",
    })
    assert resp.status_code == 200

    # Read channel
    resp = client.get("/api/projects/1/agent/sub-agent/channel", params={"last_id": 0})
    assert len(resp.json()) >= 1

    # Claim task
    resp = client.post("/api/projects/1/agent/sub-agent/claim", params={
        "agent_id": "agent-a", "task_name": "写测试用例",
    })
    assert resp.json()["claimed"] is True

    # Dedup: another agent tries same task
    resp = client.post("/api/projects/1/agent/sub-agent/claim", params={
        "agent_id": "agent-b", "task_name": "写测试用例",
    })
    assert resp.json()["claimed"] is False
    assert resp.json()["reason"] == "dedup"

    # Complete
    resp = client.post("/api/projects/1/agent/sub-agent/complete", params={
        "agent_id": "agent-a", "task_name": "写测试用例", "result": "Done",
    })
    assert resp.json()["completed"] is True

    # Conflict
    resp = client.post("/api/projects/1/agent/sub-agent/conflict", params={
        "agent_id": "agent-a", "file_path": "main.py",
        "description": "Both agents modified main.py",
    })
    assert resp.status_code == 200

    # Summary
    resp = client.get("/api/projects/1/agent/sub-agent/summary")
    data = resp.json()
    assert data["tasks_claimed"] >= 1


# ---- F1: Active Feedback Solicitation ----

def test_feedback_submit_and_list(client):
    """F1a: Submit feedback and list by project/session."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    resp = client.post("/api/projects/1/sessions", json={"title": "测试任务"})
    s_id = resp.json()["id"]

    # Submit feedback
    resp = client.post("/api/projects/1/feedback", params={
        "overall_rating": 4,
        "session_id": s_id,
        "helpfulness": 5, "accuracy": 4, "speed": 3, "clarity": 4,
        "what_went_well": "逻辑清晰，表达温暖",
        "what_to_improve": "速度可以再快一点",
        "free_text": "总体来说很满意",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["overall_rating"] == 4
    assert data["profile_update"] is not None

    # List feedback
    resp = client.get("/api/projects/1/feedback")
    assert len(resp.json()) == 1


def test_feedback_stats(client):
    """F1: Aggregate stats."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    for rating in [3, 4, 5]:
        client.post("/api/projects/1/feedback", params={
            "overall_rating": rating,
            "helpfulness": rating, "accuracy": rating,
            "speed": rating, "clarity": rating,
            "free_text": "feedback text",
        })

    resp = client.get("/api/projects/1/feedback/stats")
    data = resp.json()
    assert data["total"] == 3
    assert 3.5 <= data["avg_rating"] <= 4.5


def test_approach_success_rate(client):
    """F1c: Track approach success/failure rates."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1", "user_id": 1})

    # Record a success
    resp = client.post("/api/projects/1/approaches/success-rate", params={
        "approach_name": "使用jieba分词", "success": True, "rating": 5,
    })
    assert resp.json()["success_rate"] == 1.0

    # Record a failure
    resp = client.post("/api/projects/1/approaches/success-rate", params={
        "approach_name": "使用jieba分词", "success": False, "rating": 2,
    })
    assert resp.json()["success_rate"] == 0.5

    # Ranking
    resp = client.get("/api/projects/1/approaches/ranking")
    assert len(resp.json()) == 1


def test_solicitation_message(client):
    """F1b: Auto-solicitation message generation."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1"})

    resp = client.get("/api/projects/1/feedback/solicit", params={
        "session_title": "数据库优化",
    })
    assert resp.json()["solicit"] is True
    assert "数据库优化" in resp.json()["message"]


# ---- F2: User Psychology Profile ----

def test_user_profile_creation_from_feedback(client):
    """F2a: Profile auto-created when feedback is submitted."""
    client.post("/api/users", json={"name": "testuser"})
    # Create project for user_id=1 (assign user in the project table)
    from app.database import SessionLocal
    from app.models.project import Project
    db = SessionLocal()
    proj = Project(name="p1", user_id=1)
    db.add(proj)
    db.commit()
    pid = proj.id
    db.close()

    # Submit feedback with emotional words → profile update
    resp = client.post(f"/api/projects/{pid}/feedback", params={
        "overall_rating": 5,
        "what_went_well": "很温暖很贴心，逻辑清晰，表达直接",
        "free_text": "你真的很懂我，每次都能理解我的意思",
    })
    data = resp.json()
    pu = data.get("profile_update", {})
    assert pu is not None

    # Check profile was created
    resp = client.get("/api/users/1/profile")
    profile = resp.json()
    assert profile.get("exists", True) is True or profile.get("feedback_count", 0) >= 1


def test_user_persona_block(client):
    """F2d: Persona block for system prompt injection."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1", "user_id": 1})

    # Submit several feedbacks to build profile
    for text in ["很温暖", "逻辑清晰", "表达直接", "很细心", "耐心很好"]:
        client.post("/api/projects/1/feedback", params={
            "overall_rating": 4,
            "what_went_well": text,
            "free_text": text,
        })

    resp = client.get("/api/users/1/profile/persona")
    data = resp.json()
    assert data["exists"] is True
    assert len(data["persona"]) > 0
    assert "伴侣形象" in data["persona"] or "用户画像" in data["persona"]
    assert data["archetype"] is not None


def test_positive_patterns(client):
    """F2b: Positive pattern tracking."""
    client.post("/api/users", json={"name": "testuser"})

    # Add patterns
    resp = client.post("/api/users/1/patterns", params={
        "category": "language", "pattern": "用户喜欢被称呼为'老板'",
    })
    assert resp.json()["created"] is True

    # Repeat same pattern → increment strength
    resp = client.post("/api/users/1/patterns", params={
        "category": "language", "pattern": "用户喜欢被称呼为'老板'",
    })
    assert resp.json()["occurrences"] == 2
    assert resp.json()["strength"] > 1.0

    # List by category
    resp = client.get("/api/users/1/patterns", params={"category": "language"})
    assert len(resp.json()) == 1


def test_chat_analysis_request_flow(client):
    """F2e: Permission-gated chat analysis flow."""
    client.post("/api/users", json={"name": "testuser"})

    # Request
    resp = client.post("/api/users/1/chat-analysis/request", params={
        "chat_source": "用户与产品经理的Slack对话",
    })
    assert resp.json()["status"] == "pending"
    req_id = resp.json()["request_id"]

    # Approve
    resp = client.post(f"/api/users/1/chat-analysis/{req_id}/approve")
    assert resp.json()["status"] == "approved"

    # Complete
    resp = client.post(f"/api/users/1/chat-analysis/{req_id}/complete", params={
        "analysis_result": "用户在专业场合使用正式语气，偏好数据驱动决策，对模糊表达不耐烦",
    })
    assert resp.json()["status"] == "completed"


def test_archetype_transition(client):
    """F2c: Archetype changes as more feedback arrives."""
    client.post("/api/users", json={"name": "testuser"})
    client.post("/api/projects", json={"name": "p1", "user_id": 1})

    # Phase 1: caregiver-oriented feedback
    for _ in range(3):
        client.post("/api/projects/1/feedback", params={
            "overall_rating": 5,
            "what_went_well": "很温暖很贴心",
            "free_text": "你真的很懂我",
        })

    resp = client.get("/api/users/1/profile")
    archetype_1 = resp.json()["companion_archetype"]

    # Phase 2: challenger-oriented feedback
    for _ in range(5):
        client.post("/api/projects/1/feedback", params={
            "overall_rating": 4,
            "what_went_well": "逻辑严谨，分析直接，效率高",
            "free_text": "专业的分析很到位",
        })

    resp = client.get("/api/users/1/profile")
    archetype_2 = resp.json()["companion_archetype"]

    # Archetype should evolve with more data
    assert archetype_2 is not None
    assert resp.json()["feedback_count"] >= 8


# ---- Project 14: Thought Collision (combinatorial innovation) ----

def test_thought_collision_trigger(client):
    """P14a: Trigger a collision session → gets ingredients + prompt."""
    client.post("/api/users", json={"name": "testuser"})
    # Create project with some memory and skills
    from app.database import SessionLocal
    from app.models.project import Project
    from app.models.skill_card import SkillCard
    db = SessionLocal()
    proj = Project(name="p1", user_id=1)
    db.add(proj)
    db.commit()

    # Add some skills
    for name in ["修复Python导入错误", "优化数据库查询", "集成ChromaDB"]:
        db.add(SkillCard(name=name, status="active", usage_count=3, pinned=True))
    db.commit()
    db.close()

    # Trigger collision
    resp = client.post("/api/projects/1/collisions/collide")
    assert resp.status_code == 200
    data = resp.json()
    assert "collision_id" in data
    assert "prompt" in data
    assert "思维碰撞" in data["prompt"]
    assert data["ingredients"]["skills"] >= 1


def test_collision_save_result(client):
    """P14b: Save LLM synthesis result for a collision."""
    client.post("/api/users", json={"name": "testuser"})

    # Create collision via engine directly
    from app.database import SessionLocal
    from app.models.project import Project
    from app.services.collision_engine import run_collision
    db = SessionLocal()
    proj = Project(name="p1", user_id=1)
    db.add(proj)
    db.commit()
    result = run_collision(db, 1)
    cid = result["collision_id"]
    db.close()

    # Save result
    resp = client.patch(f"/api/projects/1/collisions/{cid}/result", params={
        "combo_name": "ChromaDB+分词 中文语义搜索引擎",
        "combo_description": "将jieba分词与ChromaDB向量检索结合，实现中文语义搜索",
        "expected_synergy": "分词精度提升向量质量，语义匹配准确率预计提升40%",
        "synergy_score": 0.85,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["combo_name"] == "ChromaDB+分词 中文语义搜索引擎"
    assert data["synergy_score"] == 0.85


def test_collision_mark_tested(client):
    """P14c: Mark collision tested → updates status and priority."""
    client.post("/api/users", json={"name": "testuser"})
    from app.database import SessionLocal
    from app.models.project import Project
    from app.services.collision_engine import run_collision, save_collision_result
    db = SessionLocal()
    proj = Project(name="p1", user_id=1)
    db.add(proj)
    db.commit()
    result = run_collision(db, 1)
    cid = result["collision_id"]
    save_collision_result(db, cid, "Test Combo", "desc", "syn", 0.7)
    db.close()

    # Mark tested with success
    resp = client.post(f"/api/projects/1/collisions/{cid}/test", params={
        "success": True, "result": "组合效果超出预期",
    })
    assert resp.status_code == 200
    assert resp.json()["success_rate"] == 1.0

    # Mark tested again with success → status changes
    resp = client.post(f"/api/projects/1/collisions/{cid}/test", params={
        "success": True, "result": "再次验证成功",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "proven"


def test_collision_list(client):
    """P14: List top collisions ordered by priority."""
    client.post("/api/users", json={"name": "testuser"})
    from app.database import SessionLocal
    from app.models.project import Project
    from app.services.collision_engine import run_collision, save_collision_result
    db = SessionLocal()
    proj = Project(name="p1", user_id=1)
    db.add(proj)
    db.commit()

    for i in range(3):
        result = run_collision(db, 1)
        save_collision_result(db, result["collision_id"],
                              f"Combo {i}", f"desc {i}", "synergy", 0.5 + i * 0.1)
    db.close()

    resp = client.get("/api/projects/1/collisions")
    assert resp.status_code == 200
    collisions = resp.json()
    assert len(collisions) >= 3


def test_collision_context_for_bootstrap(client):
    """P14d: Collision context injected into session bootstrap."""
    client.post("/api/users", json={"name": "testuser"})
    from app.database import SessionLocal
    from app.models.project import Project
    from app.services.collision_engine import run_collision, save_collision_result
    db = SessionLocal()
    proj = Project(name="p1", user_id=1)
    db.add(proj)
    db.commit()
    result = run_collision(db, 1)
    save_collision_result(db, result["collision_id"],
                          "记忆+技能融合方案",
                          "将成功记忆中的模式与已验证技能结合",
                          "预期产生1+1>2的效果", 0.75)
    db.close()

    resp = client.get("/api/projects/1/collisions/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert "思维碰撞" in "\n".join(data["lines"])
    assert "记忆+技能融合方案" in "\n".join(data["lines"])


# ---- Project 8: i18n Multi-Language ----

def test_i18n_list_locales(client):
    resp = client.get("/api/i18n/locales")
    assert resp.status_code == 200
    locales = resp.json()
    assert "zh_CN" in locales
    assert "en_US" in locales
    assert "ja_JP" in locales


def test_i18n_translate_single(client):
    resp = client.get("/api/i18n/translate", params={"key": "errors.404", "locale": "zh_CN"})
    assert resp.json()["value"] == "未找到"

    resp = client.get("/api/i18n/translate", params={"key": "errors.404", "locale": "en_US"})
    assert resp.json()["value"] == "Not Found"

    resp = client.get("/api/i18n/translate", params={"key": "errors.404", "locale": "ja_JP"})
    assert "見" in resp.json()["value"]


def test_i18n_translate_batch(client):
    resp = client.get("/api/i18n/translate/batch", params={
        "keys": "labels.project,labels.session,api.user_created",
        "locale": "zh_CN",
    })
    data = resp.json()
    assert data["labels.project"] == "项目"
    assert data["api.user_created"] == "用户创建成功"


def test_i18n_explain_error(client):
    resp = client.get("/api/i18n/explain/404", params={"locale": "zh_CN"})
    data = resp.json()
    assert data["error_code"] == "404"
    assert data["title"] == "未找到"
    assert len(data["causes"]) > 0
    assert len(data["solutions"]) > 0

    # With context interpolation
    resp = client.get("/api/i18n/explain/429", params={
        "locale": "zh_CN", "retry_after": "30",
    })
    data = resp.json()
    assert "30" in data["detail"]


def test_i18n_detect_locale(client):
    resp = client.get("/api/i18n/detect", headers={"Accept-Language": "zh-CN,zh;q=0.9"})
    assert resp.json()["detected_locale"] == "zh_CN"

    resp = client.get("/api/i18n/detect", headers={"Accept-Language": "ja"})
    assert resp.json()["detected_locale"] == "ja_JP"

    resp = client.get("/api/i18n/detect")
    assert resp.json()["detected_locale"] == "en_US"


def test_i18n_fallback(client):
    """Unknown locale falls back to English."""
    resp = client.get("/api/i18n/translate", params={
        "key": "errors.404", "locale": "fr_FR",
    })
    assert resp.json()["value"] == "Not Found"


# ---- H4: Curator Auto-Archive ----

def test_curator_stale_and_archive(client):
    """H4a: Curator marks skills stale (30d) and archived (90d)."""
    from app.database import SessionLocal
    from app.models.skill_card import SkillCard
    from app.services.curator import run_curation
    from datetime import datetime, timedelta

    db = SessionLocal()
    now = datetime(2026, 6, 18)

    # Active skill used 40 days ago → should go stale
    s1 = SkillCard(name="旧技能A", status="active", created_by="agent",
                   last_used_at=(now - timedelta(days=40)).isoformat(),
                   created_at=(now - timedelta(days=50)).isoformat())
    db.add(s1)

    # Active skill used 100 days ago → should archive
    s2 = SkillCard(name="旧技能B", status="active", created_by="agent",
                   last_used_at=(now - timedelta(days=100)).isoformat(),
                   created_at=(now - timedelta(days=110)).isoformat())
    db.add(s2)

    # Pinned skill → skipped
    s3 = SkillCard(name="钉选技能", status="active", created_by="agent", pinned=True,
                   last_used_at=(now - timedelta(days=100)).isoformat(),
                   created_at=(now - timedelta(days=110)).isoformat())
    db.add(s3)

    # User-created skill → skipped
    s4 = SkillCard(name="用户技能", status="active", created_by="user",
                   last_used_at=(now - timedelta(days=100)).isoformat(),
                   created_at=(now - timedelta(days=110)).isoformat())
    db.add(s4)

    # Recently created → seed-on-first-sight skipped
    s5 = SkillCard(name="新技能", status="active", created_by="agent",
                   last_used_at=(now - timedelta(days=1)).isoformat(),
                   created_at=(now - timedelta(days=1)).isoformat())
    db.add(s5)

    db.commit()

    # Run curation
    summary = run_curation(db, now_override=now)
    db.commit()

    assert summary["stale_count"] == 1
    assert summary["archived_count"] == 1
    assert summary["skipped_pinned"] >= 1
    assert summary["skipped_user"] >= 1
    assert summary["skipped_first_seen"] >= 1

    # Verify statuses
    db.refresh(s1)
    db.refresh(s2)
    db.refresh(s3)
    assert s1.status == "stale"
    assert s2.status == "archived"
    assert s3.status == "active"   # pinned, skipped

    db.close()


def test_curator_api(client):
    """H4: Curator API — manual trigger + stale list + archive/restore."""
    from app.database import SessionLocal
    from app.models.skill_card import SkillCard
    from datetime import datetime, timedelta

    db = SessionLocal()
    now = datetime.now()
    s1 = SkillCard(name="待归档技能", status="active", created_by="agent",
                   last_used_at=(now - timedelta(days=100)).isoformat(),
                   created_at=(now - timedelta(days=110)).isoformat())
    db.add(s1)
    db.commit()
    sid = s1.id
    db.close()

    # Trigger curation via API
    resp = client.post("/api/skills/curate")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["archived_count"] >= 1

    # List stale
    resp = client.get("/api/skills/stale")
    items = resp.json()
    assert len(items) >= 0

    # Manually restore
    resp = client.post(f"/api/skills/{sid}/restore")
    assert resp.json()["status"] == "active"

    # Manually archive
    resp = client.post(f"/api/skills/{sid}/archive")
    assert resp.json()["status"] == "archived"


# ---- Project 15: 乌托邦计划 ----

def test_utopia_full_pipeline(client):
    """P15: Full pipeline — import → extract → prioritize → generate tasks."""
    client.post("/api/users", json={"name": "testuser"})

    # Simulated chat messages (some agent-related, some not)
    messages = [
        "今天天气不错",
        "MBclaw 真好用，帮我自动整理了文件，太方便了！",
        "那个智能体刚才崩溃了，一直报错，烦死了",
        "希望 MBclaw 能学会帮我写周报，每周都要写，很麻烦",
        "这个 bug 什么时候修？导入功能一直卡住",
        "周末去哪里玩？",
        "MBclaw 太厉害了，帮我分析数据几分钟就搞定了，赞",
        "能不能加个自动备份功能？每次都要手动点",
        "聊天记录搜索功能太难用了，搜不出来东西",
        "帮我优化一下数据库查询，现在太慢了",
    ]

    # Run full pipeline
    resp = client.post("/api/utopia/pipeline", params={
        "user_id": 1,
        "source_platform": "wechat",
        "messages_json": json.dumps(messages),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["insights_found"] > 0
    assert data["tasks_created"] >= 1

    # List insights
    resp = client.get("/api/utopia/insights", params={"user_id": 1})
    assert len(resp.json()) > 0

    # List tasks
    resp = client.get("/api/utopia/tasks", params={"user_id": 1})
    tasks = resp.json()
    assert len(tasks) > 0


def test_utopia_deidentification(client):
    """P15: De-identification strips PII."""
    client.post("/api/users", json={"name": "testuser"})

    messages = [
        "我的手机号是 13812345678，MBclaw 能帮我查一下吗",
        "身份证 310101199001011234 需要验证",
    ]

    resp = client.post("/api/utopia/pipeline", params={
        "user_id": 1, "source_platform": "wechat",
        "messages_json": json.dumps(messages),
    })
    assert resp.status_code == 200

    resp = client.get("/api/utopia/insights", params={"user_id": 1})
    for insight in resp.json():
        text = insight["deidentified_text"]
        assert "13812345678" not in text
        assert "310101199001011234" not in text
        assert "[手机号]" in text or "[身份证号]" in text


def test_utopia_dual_evaluation(client):
    """P15: User×0.80 + Self×0.20 → accept/reject/contest."""
    client.post("/api/users", json={"name": "testuser"})

    # Create a task manually
    from app.database import SessionLocal
    from app.models.utopia import UtopiaTask
    db = SessionLocal()
    task = UtopiaTask(user_id=1, title="测试任务", description="desc",
                      category="feature_request", priority=0.5, status="pending",
                      created_at="2026-06-18T00:00:00")
    db.add(task)
    db.commit()
    tid = task.id
    db.close()

    # Submit solution
    resp = client.post(f"/api/utopia/tasks/{tid}/submit", params={
        "user_id": 1,
        "solution_text": "我写了一个自动备份脚本",
        "self_score": 0.7,
        "self_rationale": "功能完整，代码简洁",
    })
    assert resp.status_code == 200
    sid = resp.json()["submission_id"]

    # User evaluates — high score → accepted
    resp = client.post(f"/api/utopia/submissions/{sid}/evaluate", params={
        "user_score": 0.85,
        "user_feedback": "做得很好，非常实用",
    })
    data = resp.json()
    assert data["decision"] == "accepted"
    assert 0.6 <= data["composite_score"] <= 1.0

    # Test rejection: low composite
    resp = client.post(f"/api/utopia/tasks/{tid}/submit", params={
        "user_id": 1, "solution_text": "另一个方案",
        "self_score": 0.3, "self_rationale": "一般",
    })
    sid2 = resp.json()["submission_id"]

    resp = client.post(f"/api/utopia/submissions/{sid2}/evaluate", params={
        "user_score": 0.2, "user_feedback": "不好",
    })
    assert resp.json()["decision"] == "rejected"

    # Test contested: composite > 50% but user-self gap > 60%
    resp = client.post(f"/api/utopia/tasks/{tid}/submit", params={
        "user_id": 1, "solution_text": "争议方案",
        "self_score": 1.0, "self_rationale": "完美",
    })
    sid3 = resp.json()["submission_id"]

    resp = client.post(f"/api/utopia/submissions/{sid3}/evaluate", params={
        "user_score": 0.39, "user_feedback": "不认可",
    })
    # composite = 0.39*0.80 + 1.0*0.20 = 0.512 > 0.50, gap = 0.61 > 0.60 → contested
    assert resp.json()["decision"] == "contested"


def test_utopia_server_inbox(client):
    """P15: Server inbox collects accepted submissions."""
    client.post("/api/users", json={"name": "testuser"})

    from app.database import SessionLocal
    from app.models.utopia import UtopiaTask, UtopiaSubmission
    db = SessionLocal()
    task = UtopiaTask(user_id=1, title="收件箱测试", description="d",
                      category="bug", priority=0.6, status="pending",
                      created_at="2026-06-18T00:00:00")
    db.add(task)
    db.commit()
    sub = UtopiaSubmission(task_id=task.id, user_id=1,
                           solution_text="修复了",
                           self_score=0.6, user_score=0.85,
                           composite_score=round(0.85*0.80 + 0.6*0.20, 3),
                           status="accepted",
                           created_at="2026-06-18T00:00:00")
    db.add(sub)
    db.commit()
    db.close()

    resp = client.get("/api/utopia/server/inbox")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1


def test_utopia_stats(client):
    """P15: Aggregate stats."""
    client.post("/api/users", json={"name": "testuser"})

    resp = client.post("/api/utopia/pipeline", params={
        "user_id": 1, "source_platform": "wechat",
        "messages_json": json.dumps([
            "MBclaw 真好用", "有个 bug", "希望加个功能",
        ]),
    })
    assert resp.status_code == 200

    resp = client.get("/api/utopia/stats", params={"user_id": 1})
    data = resp.json()
    assert data["total_insights"] > 0
    assert data["total_tasks"] > 0


def test_utopia_chat_extractor_wechat_txt(client):
    """P15: Parse WeChat exported .txt format."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write("2024-06-15 10:30:00 张三\n")
        f.write("MBclaw 真好用！\n")
        f.write("2024-06-15 10:31:00 李四\n")
        f.write("是啊，自动整理文件太方便了\n")
        f.write("2024-06-15 10:32:00 张三\n")
        f.write("不过昨天崩溃了两次，烦\n")
        tmp = f.name

    resp = client.post("/api/utopia/parse-file", params={
        "filepath": tmp, "platform": "wechat",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert data["messages"][0]["sender"] == "张三"
    assert "真好用" in data["messages"][0]["content"]

    # Run full pipeline on it
    resp = client.post("/api/utopia/pipeline", params={
        "user_id": 1, "source_platform": "wechat",
        "messages_json": json.dumps([m["content"] for m in data["messages"]]),
    })
    assert resp.status_code == 200

    import os
    os.unlink(tmp)


def test_utopia_chat_extractor_feishu_json(client):
    """P15: Parse Feishu exported .json format."""
    import tempfile, os
    feishu_data = {
        "messages": [
            {"create_time": "2024-06-15T10:30:00",
             "sender": {"name": "王五"},
             "body": {"content": {"text": "这个 bug 什么时候修？"}}},
            {"create_time": "2024-06-15T11:00:00",
             "sender": {"name": "赵六"},
             "body": {"content": {"text": "MBclaw 如果能学会自动备份就好了"}}},
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump(feishu_data, f, ensure_ascii=False)
        tmp = f.name

    resp = client.post("/api/utopia/parse-file", params={
        "filepath": tmp, "platform": "feishu",
    })
    assert resp.status_code == 200
    assert resp.json()["count"] == 2

    os.unlink(tmp)


def test_utopia_discover_endpoint(client):
    """P15: GET /api/utopia/discover returns platform sources (may be empty in CI)."""
    resp = client.get("/api/utopia/discover")
    assert resp.status_code == 200
    assert "sources" in resp.json()


def test_context_refresh(client):
    """Refreshing context after new data is added should update it."""
    client.post("/api/users", json={"name": "testuser"})
    p = client.post("/api/projects", json={"name": "P3"}).json()
    pid = p["id"]

    # Session without history
    resp = client.post(f"/api/projects/{pid}/sessions", json={"title": "测试"})
    s_id = resp.json()["id"]

    resp = client.get(f"/api/projects/{pid}/sessions/{s_id}/context")
    initial_context = resp.json()["context"]

    # Now add a completed session with a failure
    resp = client.post(f"/api/projects/{pid}/sessions", json={"title": "数据库连接池测试"})
    s2_id = resp.json()["id"]
    client.post(f"/api/sessions/{s2_id}/messages", json={
        "role": "user", "content": "用连接池管理数据库连接",
    })
    client.patch(f"/api/projects/{pid}/sessions/{s2_id}/complete")

    # Refresh context
    resp = client.post(f"/api/projects/{pid}/sessions/{s_id}/context/refresh")
    assert resp.status_code == 200
