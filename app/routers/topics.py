from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.project import Project
from app.models.classification_node import ClassificationNode
from app.schemas.classification import ClassificationNodeOut, ContextSearchRequest
from app.services.classification_service import get_failed_approaches
from app.services.layered_search import prefetch_context
from app.services.vector_store import search_similar

router = APIRouter(prefix="/api/projects/{project_id}/topics", tags=["topics"])


@router.get("/failed")
def list_failed(project_id: int, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"failed_approaches": get_failed_approaches(db, project_id)}


@router.post("/prefetch")
def prefetch(project_id: int, req: ContextSearchRequest, db: DBSession = Depends(get_db)):
    """Real-time memory prefetch: L1→L2→L3 search with token budget."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return prefetch_context(db, project_id, req.query_text, req.max_tokens)


@router.post("/context-search")
def context_search(project_id: int, req: ContextSearchRequest, db: DBSession = Depends(get_db)):
    """L2+L3: semantic search + return relevant context chunks."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        results = search_similar("classification_nodes", req.query_text, top_k=5)
    except Exception:
        results = []

    enriched = []
    for r in results:
        node_id = r["id"].replace("node_", "")
        node = db.query(ClassificationNode).filter(ClassificationNode.id == int(node_id)).first()
        if node:
            item = {
                "category": node.category_name,
                "summary_short": node.summary_short,
                "summary_detailed": node.summary_detailed[:500],
                "distance": r["distance"],
            }
            if req.include_failed and node.failed_approaches:
                item["failed_approaches"] = node.failed_approaches
            enriched.append(item)

    # Token budget: trim total response
    total_chars = 0
    trimmed = []
    for item in enriched:
        chars = len(item.get("summary_detailed", "")) + len(item.get("summary_short", ""))
        if total_chars > req.max_tokens * 2:
            break
        total_chars += chars
        trimmed.append(item)

    return {"results": trimmed}


@router.get("", response_model=list[ClassificationNodeOut])
def list_topics(project_id: int, level: int = None, parent_id: int = None, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    q = db.query(ClassificationNode).filter(ClassificationNode.project_id == project_id)
    if level is not None:
        q = q.filter(ClassificationNode.level == level)
    if parent_id is not None:
        q = q.filter(ClassificationNode.parent_id == parent_id)
    return q.order_by(ClassificationNode.id).all()


@router.get("/{node_id}", response_model=ClassificationNodeOut)
def get_topic(project_id: int, node_id: int, db: DBSession = Depends(get_db)):
    node = (
        db.query(ClassificationNode)
        .filter(ClassificationNode.id == node_id, ClassificationNode.project_id == project_id)
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="话题节点不存在")
    return node
