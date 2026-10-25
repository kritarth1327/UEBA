from datetime import date, datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class SeverityCount(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class RiskDistribution(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    unassessed: int = 0


class RecentAlertItem(BaseModel):
    id: int
    user_id: str
    employee_name: Optional[str] = None
    severity: str
    status: str
    reason: str
    risk_score: Optional[float] = None
    detected_at: datetime


class HighRiskUserItem(BaseModel):
    user_id: str
    employee_name: Optional[str] = None
    department: Optional[str] = None
    hybrid_risk_score: float
    risk_level: str
    assessment_date: date
    alert_count: int


class ActivityTrendItem(BaseModel):
    date: date
    total_events: int
    anomalous_events: int


class DashboardOverviewResponse(BaseModel):
    total_users: int
    assessed_users: int
    alerts_by_severity: SeverityCount
    risk_distribution: RiskDistribution
    activity_trends: List[ActivityTrendItem]
    recent_alerts: List[RecentAlertItem]
    highest_risk_users: List[HighRiskUserItem]
    dataset_ready: bool
    models_ready: bool
    model_status: str = "unavailable"
    last_evaluated_at: Optional[datetime] = None
