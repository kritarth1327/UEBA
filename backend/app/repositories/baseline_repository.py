import json
from typing import Optional, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session
from app.models.baseline import PersonalBaseline


class BaselineRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_by_user(self, user_id: str) -> Optional[dict]:
        stmt = (
            select(PersonalBaseline)
            .where(
                and_(
                    PersonalBaseline.user_id == user_id,
                    PersonalBaseline.is_active.is_(True)
                )
            )
            .order_by(desc(PersonalBaseline.calculated_at))
        )
        b = self.db.scalars(stmt).first()
        if not b:
            return None

        metrics = {}
        try:
            metrics = json.loads(b.metrics_json)
        except Exception:
            metrics = {}

        return {
            "id": b.id,
            "user_id": b.user_id,
            "window_start": b.window_start,
            "window_end": b.window_end,
            "metrics": metrics,
            "sample_size": b.sample_size,
            "is_active": b.is_active,
            "calculated_at": b.calculated_at,
        }

    def save(self, baseline: PersonalBaseline) -> PersonalBaseline:
        self.db.add(baseline)
        self.db.commit()
        self.db.refresh(baseline)
        return baseline
