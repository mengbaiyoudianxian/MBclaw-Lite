import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.tool import ToolRegistry
from app.schemas.tool import ToolCreate, ToolUpdate, ToolOut, ToolSearchRequest, ToolSelectRequest
from app.services.tool_service import register_tool, get_summaries, get_by_tag, get_full, vector_search, select_for_task

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/summaries")
def list_summaries(db: DBSession = Depends(get_db)):
    """L1: All tools with 100-char summaries."""
    return get_summaries(db)


@router.get("/by-tag")
def list_by_tag(tag: str, db: DBSession = Depends(get_db)):
    """L2: Tools filtered by tag."""
    return get_by_tag(db, tag)


@router.get("/{tool_id}")
def get_tool(tool_id: int, db: DBSession = Depends(get_db)):
    """L3: Full tool details."""
    result = get_full(db, tool_id)
    if not result:
        raise HTTPException(status_code=404, detail="工具不存在")
    return result


@router.post("", response_model=ToolOut, status_code=201)
def create_tool(data: ToolCreate, db: DBSession = Depends(get_db)):
    existing = db.query(ToolRegistry).filter(ToolRegistry.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="工具名称已存在")
    return register_tool(db, data.model_dump())


@router.patch("/{tool_id}", response_model=ToolOut)
def update_tool(tool_id: int, data: ToolUpdate, db: DBSession = Depends(get_db)):
    tool = db.query(ToolRegistry).filter(ToolRegistry.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    updates = data.model_dump(exclude_unset=True)
    if "tags" in updates:
        updates["tags"] = json.dumps(updates["tags"], ensure_ascii=False)
    if "usage_examples" in updates:
        updates["usage_examples"] = json.dumps(updates["usage_examples"], ensure_ascii=False)
    if "compatible_models" in updates:
        updates["compatible_models"] = json.dumps(updates["compatible_models"], ensure_ascii=False)
    updates["updated_at"] = datetime.now().isoformat()

    for k, v in updates.items():
        setattr(tool, k, v)
    db.commit()
    db.refresh(tool)
    return tool


@router.delete("/{tool_id}", status_code=204)
def delete_tool(tool_id: int, db: DBSession = Depends(get_db)):
    tool = db.query(ToolRegistry).filter(ToolRegistry.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    db.delete(tool)
    db.commit()


@router.post("/search")
def search_tools(req: ToolSearchRequest, db: DBSession = Depends(get_db)):
    """Vector semantic search for tools."""
    return vector_search(db, req.query, req.max_results)


@router.post("/select")
def select_tools(req: ToolSelectRequest, db: DBSession = Depends(get_db)):
    """Token-budget-aware tool selection for a task."""
    return select_for_task(db, req.task_description, req.budget_tokens, req.required_tags)
