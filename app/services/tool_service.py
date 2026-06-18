import json
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.tool import ToolRegistry
from app.services.vector_store import index_text, search_similar

TOOL_COLLECTION = "tool_registry"


def _as_list(v) -> list[str]:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def register_tool(db: DBSession, data: dict) -> ToolRegistry:
    tool = ToolRegistry(
        name=data["name"],
        summary_100=data.get("summary_100", ""),
        tags=json.dumps(data.get("tags", []), ensure_ascii=False),
        full_description=data.get("full_description", ""),
        usage_examples=json.dumps(data.get("usage_examples", []), ensure_ascii=False),
        compatible_models=json.dumps(data.get("compatible_models", []), ensure_ascii=False),
        classification_node_id=data.get("classification_node_id"),
        embedding_text=f"{data.get('name')} {data.get('summary_100', '')} {data.get('full_description', '')[:500]}",
        created_at=datetime.now().isoformat(),
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)

    # Index into ChromaDB
    try:
        index_text(TOOL_COLLECTION, f"tool_{tool.id}", tool.embedding_text,
                   {"name": tool.name, "tags": tool.tags})
    except Exception:
        pass

    return tool


def get_summaries(db: DBSession) -> list[dict]:
    """L1: 100-character summaries for all tools."""
    tools = db.query(ToolRegistry).order_by(ToolRegistry.usage_count.desc()).all()
    return [{
        "id": t.id, "name": t.name, "summary_100": t.summary_100,
        "tags": _as_list(t.tags), "rating": t.rating,
    } for t in tools]


def get_by_tag(db: DBSession, tag: str) -> list[dict]:
    """L2: Filter tools by tag."""
    tools = db.query(ToolRegistry).all()
    results = []
    for t in tools:
        tags = _as_list(t.tags)
        if any(tag.lower() in tl.lower() for tl in tags):
            results.append({
                "id": t.id, "name": t.name, "summary_100": t.summary_100,
                "tags": tags, "full_description": t.full_description[:500],
            })
    return results


def get_full(db: DBSession, tool_id: int) -> dict | None:
    """L3: Full tool description."""
    tool = db.query(ToolRegistry).filter(ToolRegistry.id == tool_id).first()
    if not tool:
        return None
    return {
        "id": tool.id, "name": tool.name,
        "summary_100": tool.summary_100,
        "tags": _as_list(tool.tags),
        "full_description": tool.full_description,
        "usage_examples": _as_list(tool.usage_examples),
        "compatible_models": _as_list(tool.compatible_models),
        "rating": tool.rating, "usage_count": tool.usage_count,
    }


def vector_search(db: DBSession, query: str, max_results: int = 10) -> list[dict]:
    """Semantic search via ChromaDB + SQL augmentation."""
    try:
        results = search_similar(TOOL_COLLECTION, query, top_k=max_results)
    except Exception:
        results = []

    enriched = []
    for r in results:
        tool = db.query(ToolRegistry).filter(ToolRegistry.id == int(r["id"].replace("tool_", ""))).first()
        if tool:
            enriched.append({
                "id": tool.id, "name": tool.name,
                "summary_100": tool.summary_100,
                "tags": _as_list(tool.tags),
                "distance": r["distance"],
            })
    return enriched


def select_for_task(db: DBSession, task_description: str, budget_tokens: int = 2000,
                    required_tags: list[str] | None = None) -> list[dict]:
    """Token-budget-aware tool selection for a task."""
    required_tags = required_tags or []
    try:
        results = search_similar(TOOL_COLLECTION, task_description, top_k=15)
    except Exception:
        results = []

    # Filter by required tags
    filtered = []
    for r in results:
        tool = db.query(ToolRegistry).filter(ToolRegistry.id == int(r["id"].replace("tool_", ""))).first()
        if not tool:
            continue
        tags = _as_list(tool.tags)
        if required_tags and not any(rt.lower() in " ".join(tags).lower() for rt in required_tags):
            continue
        filtered.append({
            "id": tool.id, "name": tool.name,
            "summary_100": tool.summary_100,
            "full_description": tool.full_description,
            "distance": r["distance"],
        })

    # Token budget trim
    total_chars = 0
    selected = []
    for item in sorted(filtered, key=lambda x: x["distance"]):
        chars = len(item["summary_100"]) + len(item["full_description"])
        if total_chars + chars > budget_tokens * 2:
            break
        total_chars += chars
        selected.append(item)
    return selected
