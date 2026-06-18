from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.model_profile import ModelProfile
from app.schemas.model_profile import ModelProfileCreate, ModelRecommendRequest, ModelProfileOut
from app.services.model_service import register_model, recommend_models

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelProfileOut])
def list_models(db: DBSession = Depends(get_db)):
    return db.query(ModelProfile).all()


@router.post("", response_model=ModelProfileOut, status_code=201)
def create_model(data: ModelProfileCreate, db: DBSession = Depends(get_db)):
    existing = db.query(ModelProfile).filter(ModelProfile.key_alias == data.key_alias).first()
    if existing:
        raise HTTPException(status_code=400, detail="模型别名已存在")
    return register_model(db, data.model_dump())


@router.delete("/{model_id}", status_code=204)
def delete_model(model_id: int, db: DBSession = Depends(get_db)):
    model = db.query(ModelProfile).filter(ModelProfile.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    db.delete(model)
    db.commit()


@router.post("/recommend")
def recommend(req: ModelRecommendRequest, db: DBSession = Depends(get_db)):
    return recommend_models(db, req.task_type, req.task_complexity, req.budget, req.required_tools)
