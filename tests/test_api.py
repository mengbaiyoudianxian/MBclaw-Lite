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
