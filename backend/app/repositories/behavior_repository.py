import json
from datetime import date
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, desc, asc
from sqlalchemy.orm import Session
from app.models.behavior import DailyBehaviorProfile


class BehaviorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user(
        self,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[dict]:
        stmt = select(DailyBehaviorProfile).where(DailyBehaviorProfile.user_id == user_id)
        if start_date:
            stmt = stmt.where(DailyBehaviorProfile.date >= start_date)
        if end_date:
            stmt = stmt.where(DailyBehaviorProfile.date <= end_date)

        stmt = stmt.order_by(asc(DailyBehaviorProfile.date)).limit(limit)
        results = self.db.scalars(stmt).all()

        profiles = []
        for p in results:
            features, unavailable = None, []
            if p.features_json:
                try:
                    payload = json.loads(p.features_json)
                    # Flat name -> value map; unavailable features are null (never a fabricated 0)
                    features = payload.get("features") if isinstance(payload.get("features"), dict) else payload
                    unavailable = payload.get("unavailable_features", [])
                except Exception:
                    features = None

            profiles.append({
                "id": p.id,
                "user_id": p.user_id,
                "date": p.date,
                "logon_count": p.logon_count,
                "after_hours_logons": p.after_hours_logons,
                "file_access_count": p.file_access_count,
                "file_copied_removable": p.file_copied_removable,
                "email_count": p.email_count,
                "email_external_count": p.email_external_count,
                "email_attachment_count": p.email_attachment_count,
                "http_request_count": p.http_request_count,
                "http_after_hours_count": p.http_after_hours_count,
                "removable_device_events": p.removable_device_events,
                "total_session_duration": p.total_session_duration,
                "features": features,
                "unavailable_features": unavailable,
                "dataset_source": p.dataset_source,
                "created_at": p.created_at,
            })
        return profiles

    def get_by_user_and_date(self, user_id: str, target_date: date) -> Optional[DailyBehaviorProfile]:
        stmt = select(DailyBehaviorProfile).where(
            and_(
                DailyBehaviorProfile.user_id == user_id,
                DailyBehaviorProfile.date == target_date
            )
        )
        return self.db.scalars(stmt).first()

    def create(self, profile: DailyBehaviorProfile) -> DailyBehaviorProfile:
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile
