from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.external_integration import ExternalIntegration
from app.schemas.integration import IntegrationCreate, IntegrationOut
from app.services.integration_service import register_integration, test_connectivity, PROVIDER_TYPES

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("", response_model=list[IntegrationOut])
def list_integrations(db: DBSession = Depends(get_db)):
    return db.query(ExternalIntegration).all()


@router.post("", response_model=IntegrationOut, status_code=201)
def create_integration(data: IntegrationCreate, db: DBSession = Depends(get_db)):
    if data.provider not in PROVIDER_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的 provider: {data.provider}")
    return register_integration(db, data.model_dump())


@router.get("/{integration_id}", response_model=IntegrationOut)
def get_integration(integration_id: int, db: DBSession = Depends(get_db)):
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.id == integration_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="集成不存在")
    return integration


@router.patch("/{integration_id}", response_model=IntegrationOut)
def update_integration(integration_id: int, data: IntegrationCreate,
                       db: DBSession = Depends(get_db)):
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.id == integration_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="集成不存在")
    for k, v in data.model_dump().items():
        setattr(integration, k, v)
    db.commit()
    db.refresh(integration)
    return integration


@router.delete("/{integration_id}", status_code=204)
def delete_integration(integration_id: int, db: DBSession = Depends(get_db)):
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.id == integration_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="集成不存在")
    db.delete(integration)
    db.commit()


@router.post("/{integration_id}/test")
def test_integration(integration_id: int, db: DBSession = Depends(get_db)):
    """Test connectivity of an integration."""
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.id == integration_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="集成不存在")
    return test_connectivity(db, integration_id)
