import json
from datetime import date
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.user import User


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, alert_id: int) -> Optional[dict]:
        stmt = (
            select(Alert, User.employee_name, User.department)
            .outerjoin(User, Alert.user_id == User.user_id)
            .where(Alert.id == alert_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None

        alert, emp_name, dept = row
        evidence = None
        if alert.evidence_json:
            try:
                evidence = json.loads(alert.evidence_json)
            except Exception:
                evidence = None

        return {
            "id": alert.id,
            "user_id": alert.user_id,
            "employee_name": emp_name,
            "department": dept,
            "date": alert.date,
            "severity": alert.severity,
            "status": alert.status,
            "reason": alert.reason,
            "risk_score": alert.risk_score,
            "evidence": evidence,
            "notes": alert.notes,
            "detected_at": alert.detected_at,
            "updated_at": alert.updated_at,
        }

    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Tuple[List[dict], int]:
        base_query = (
            select(Alert, User.employee_name, User.department)
            .outerjoin(User, Alert.user_id == User.user_id)
        )

        filters = []
        if severity:
            filters.append(Alert.severity == severity.upper())
        if status:
            filters.append(Alert.status == status.upper())
        if user_id:
            filters.append(Alert.user_id == user_id)
        if start_date:
            filters.append(Alert.date >= start_date)
        if end_date:
            filters.append(Alert.date <= end_date)
        if search:
            search_filter = f"%{search}%"
            filters.append(
                or_(
                    Alert.user_id.ilike(search_filter),
                    Alert.reason.ilike(search_filter),
                    User.employee_name.ilike(search_filter),
                )
            )

        if filters:
            base_query = base_query.where(and_(*filters))

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.scalar(count_query) or 0

        # Sort descending by detected_at
        paginated_query = (
            base_query.order_by(desc(Alert.detected_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        rows = self.db.execute(paginated_query).all()
        items = []
        for alert, emp_name, dept in rows:
            evidence = None
            if alert.evidence_json:
                try:
                    evidence = json.loads(alert.evidence_json)
                except Exception:
                    evidence = None

            items.append({
                "id": alert.id,
                "user_id": alert.user_id,
                "employee_name": emp_name,
                "department": dept,
                "date": alert.date,
                "severity": alert.severity,
                "status": alert.status,
                "reason": alert.reason,
                "risk_score": alert.risk_score,
                "evidence": evidence,
                "notes": alert.notes,
                "detected_at": alert.detected_at,
                "updated_at": alert.updated_at,
            })

        return items, total

    def update_status(self, alert_id: int, status: str, notes: Optional[str] = None) -> Optional[dict]:
        alert = self.db.scalar(select(Alert).where(Alert.id == alert_id))
        if not alert:
            return None

        alert.status = status.upper()
        if notes is not None:
            alert.notes = notes

        self.db.commit()
        self.db.refresh(alert)
        return self.get_by_id(alert_id)

    def get_severity_counts(self) -> Dict[str, int]:
        stmt = select(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)
        rows = self.db.execute(stmt).all()

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for severity, count in rows:
            sev_key = severity.lower()
            if sev_key in counts:
                counts[sev_key] = count
        return counts

    def get_recent(self, limit: int = 5) -> List[dict]:
        stmt = (
            select(Alert, User.employee_name)
            .outerjoin(User, Alert.user_id == User.user_id)
            .order_by(desc(Alert.detected_at))
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        items = []
        for alert, emp_name in rows:
            items.append({
                "id": alert.id,
                "user_id": alert.user_id,
                "employee_name": emp_name,
                "severity": alert.severity,
                "status": alert.status,
                "reason": alert.reason,
                "risk_score": alert.risk_score,
                "detected_at": alert.detected_at,
            })
        return items

    def create(self, alert: Alert) -> Alert:
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert
