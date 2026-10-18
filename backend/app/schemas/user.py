from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    user_id: str
    employee_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    supervisor: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    pass


class UserSummary(UserBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    latest_risk_score: Optional[float] = None
    latest_risk_level: Optional[str] = None
    latest_assessment_date: Optional[date] = None
    alert_count: int = 0


class UserDetail(UserBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime
    latest_risk_score: Optional[float] = None
    latest_risk_level: Optional[str] = None
    latest_assessment_date: Optional[date] = None
    total_profiles_count: int = 0
    total_alerts_count: int = 0


class UserPagination(BaseModel):
    items: List[UserSummary]
    total: int
    page: int
    page_size: int
    total_pages: int
