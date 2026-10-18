from datetime import date, datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field


AlertSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
AlertStatus = Literal["OPEN", "INVESTIGATING", "RESOLVED", "DISMISSED"]


class AlertBase(BaseModel):
    user_id: str
    date: date
    severity: AlertSeverity
    status: AlertStatus = "OPEN"
    reason: str
    risk_score: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    status: AlertStatus
    notes: Optional[str] = None


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    date: date
    severity: AlertSeverity
    status: AlertStatus
    reason: str
    risk_score: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    detected_at: datetime
    updated_at: datetime


class AlertPagination(BaseModel):
    items: List[AlertRead]
    total: int
    page: int
    page_size: int
    total_pages: int
