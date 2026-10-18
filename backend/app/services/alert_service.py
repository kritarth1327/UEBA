from datetime import date
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.repositories.alert_repository import AlertRepository


class AlertService:
    def __init__(self, db: Session):
        self.repo = AlertRepository(db)

    def get_alerts_page(
        self,
        page: int = 1,
        page_size: int = 20,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        items, total = self.repo.get_paginated(
            page=page,
            page_size=page_size,
            severity=severity,
            status=status,
            search=search,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_alert_detail(self, alert_id: int) -> Optional[dict]:
        return self.repo.get_by_id(alert_id)

    def update_alert_status(self, alert_id: int, status: str, notes: Optional[str] = None) -> Optional[dict]:
        return self.repo.update_status(alert_id, status=status, notes=notes)
