from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.system import SystemStatusResponse
from app.services.system_service import SystemService

router = APIRouter()


@router.get("/system/status", response_model=SystemStatusResponse, summary="System readiness and environment diagnostics")
def get_system_status(db: Session = Depends(get_db)):
    service = SystemService(db)
    return service.check_full_system()
