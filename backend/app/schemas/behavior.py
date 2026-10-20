from datetime import date, datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class DailyBehaviorProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    date: date
    logon_count: int
    after_hours_logons: int
    file_access_count: int
    file_copied_removable: int
    email_count: int
    email_external_count: int
    email_attachment_count: int
    http_request_count: int
    http_after_hours_count: int
    removable_device_events: int
    total_session_duration: float
    # Schema-named feature map; null = unavailable for this source (distinct from a real 0)
    features: Optional[Dict[str, Any]] = None
    unavailable_features: List[str] = []
    dataset_source: Optional[str] = None
    created_at: datetime


class UserBehaviorResponse(BaseModel):
    user_id: str
    total_days: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    profiles: List[DailyBehaviorProfileRead]
