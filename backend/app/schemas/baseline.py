from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class BaselineMetric(BaseModel):
    mean: float
    std: float
    median: Optional[float] = None
    q25: Optional[float] = None
    q75: Optional[float] = None


class PersonalBaselineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    metrics: Dict[str, BaselineMetric]
    sample_size: int
    is_active: bool
    calculated_at: datetime


class BaselineComparisonItem(BaseModel):
    metric_name: str
    observed_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    is_deviant: bool


class UserBaselineResponse(BaseModel):
    user_id: str
    has_baseline: bool
    baseline: Optional[PersonalBaselineRead] = None
    message: str

