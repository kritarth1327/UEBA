from datetime import date
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.repositories.behavior_repository import BehaviorRepository


class BehaviorService:
    def __init__(self, db: Session):
        self.repo = BehaviorRepository(db)

    def get_user_behavior_history(
        self,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        profiles = self.repo.get_by_user(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        return {
            "user_id": user_id,
            "total_days": len(profiles),
            "start_date": start_date,
            "end_date": end_date,
            "profiles": profiles
        }
