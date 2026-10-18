from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.system import HealthResponse
from app.services.system_service import SystemService

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Application and database health check")
def get_health(db: Session = Depends(get_db)):
    service = SystemService(db)
    return service.check_health()
