from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.schemas.search import SearchResult
from app.services.search_service import search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search_api(
    q: str = Query(..., min_length=1),
    project_id: Optional[int] = Query(None),
    db: DBSession = Depends(get_db),
):
    return search(db, q, project_id)
