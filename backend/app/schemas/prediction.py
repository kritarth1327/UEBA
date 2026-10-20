from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class ContributingFactor(BaseModel):
    feature: str
    description: str
    observed_value: float
    contribution_weight: float
    baseline_value: Optional[float] = None


class ModelPredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    date: date
    ml_threat_score: Optional[float] = None
    ann_anomaly_score: Optional[float] = None
    baseline_deviation_score: Optional[float] = None
    hybrid_risk_score: Optional[float] = None
    risk_level: str
    contributing_factors: Optional[List[ContributingFactor]] = None
    model_version: str
    evaluated_at: datetime
    # Per-component status/normalised score/effective weight/points; unavailable components are
    # listed with status != "ok" (their score is null, NOT zero).
    components: Optional[Dict[str, Any]] = None
    config_version: Optional[str] = None


class UserRiskHistoryResponse(BaseModel):
    user_id: str
    latest_prediction: Optional[ModelPredictionRead] = None
    history: List[ModelPredictionRead]
    summary: Dict[str, Any]
