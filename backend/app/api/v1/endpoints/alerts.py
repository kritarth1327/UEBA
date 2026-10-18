from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.alert import AlertPagination, AlertRead, AlertUpdate
from app.services.alert_service import AlertService

router = APIRouter()


@router.get("/alerts", response_model=AlertPagination, summary="List paginated alerts")
def get_alerts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (OPEN, INVESTIGATING, RESOLVED, DISMISSED)"),
    search: Optional[str] = Query(None, description="Search user ID, employee name, reason"),
    user_id: Optional[str] = Query(None, description="Filter by specific user"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    db: Session = Depends(get_db)
):
    service = AlertService(db)
    return service.get_alerts_page(
        page=page,
        page_size=page_size,
        severity=severity,
        status=status_filter,
        search=search,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/alerts/{alert_id}", response_model=AlertRead, summary="Get alert details")
def get_alert_detail(alert_id: int, db: Session = Depends(get_db)):
    service = AlertService(db)
    alert = service.get_alert_detail(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with identifier '{alert_id}' was not found."
        )
    return alert


@router.patch("/alerts/{alert_id}", response_model=AlertRead, summary="Update alert triage status")
def update_alert(alert_id: int, update_data: AlertUpdate, db: Session = Depends(get_db)):
    service = AlertService(db)
    updated = service.update_alert_status(
        alert_id=alert_id,
        status=update_data.status,
        notes=update_data.notes
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with identifier '{alert_id}' was not found."
        )
    return updated
