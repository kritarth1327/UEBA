from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/dashboard/overview", response_model=DashboardOverviewResponse, summary="Aggregated dashboard overview")
def get_dashboard_overview(db: Session = Depends(get_db)):
    service = DashboardService(db)
    return service.get_overview()
