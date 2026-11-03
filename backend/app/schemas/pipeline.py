from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    dataset: Literal["spedia", "cert_r42"]
    path: Optional[str] = Field(None, description="File/dir relative to the raw data directory; defaults to configured location")
    force: bool = Field(False, description="Re-ingest even if this exact source+configuration was already ingested")
    cert_file_is_removable_copy: bool = Field(False, description="CERT only: treat file.csv rows as removable-media copies (verify first)")


class IngestionReport(BaseModel):
    dataset: str
    schema_version: str
    skipped: bool
    run_id: Optional[int] = None
    reason: Optional[str] = None
    rows_read: Optional[int] = None
    rows_accepted: Optional[int] = None
    rows_rejected: Optional[int] = None
    rejected_by_reason: Dict[str, int] = {}
    missing_sources: List[str] = []
    users: Optional[int] = None
    user_days: Optional[int] = None
    date_range: Optional[List[str]] = None
    unavailable_features: List[str] = []
    users_created: Optional[int] = None
    profiles_inserted: Optional[int] = None
    profiles_updated: Optional[int] = None
    profiles_conflicting_dataset: Optional[int] = None
    users_below_baseline_min_days: List[str] = []
    label_summary: Optional[Dict[str, int]] = None
    users_with_only_labelled_anomalous_events: List[str] = []


class BaselineGenerateRequest(BaseModel):
    user_id: Optional[str] = None
    as_of: Optional[date] = Field(None, description="Baseline uses days strictly before this date; default = day after last observation")


class BaselineGenerateItem(BaseModel):
    user_id: str
    status: str
    persisted: bool
    as_of: Optional[date] = None
    sample_size: int = 0
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    unusable_features: List[str] = []


class BaselineGenerateResponse(BaseModel):
    results: List[BaselineGenerateItem]
    persisted: int
    skipped: int


class ScoreRequest(BaseModel):
    user_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ScoreResponse(BaseModel):
    users_processed: int
    days_scored: int
    days_without_signal: int
    predictions_written: int
    alerts_upserted: int
    errors: List[Dict[str, str]]


class RiskEvaluateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    date: date
    features: Dict[str, Optional[float]] = Field(description="Names from GET /features/schema; null = unavailable")


class RiskEvaluateResponse(BaseModel):
    assessed: bool
    reason: Optional[str] = None
    hybrid_risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    components: List[Dict[str, Any]] = []
    contributing_components: List[str] = []
    unavailable_components: List[str] = []
    contributing_factors: List[Dict[str, Any]] = []
    baseline_only_cap_applied: bool = False
    baseline: Optional[Dict[str, Any]] = None
    config_version: Optional[str] = None
    config_provisional: Optional[bool] = None


class IngestionRunRead(BaseModel):
    id: int
    dataset: str
    status: str
    source_path: str
    schema_version: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    report: Optional[Dict[str, Any]] = None


class PipelineSummary(BaseModel):
    datasets: Dict[str, Dict[str, Any]]
    users: int
    predictions: int
    alerts: int
    active_baselines: int
    last_ingestion: Optional[IngestionRunRead] = None
