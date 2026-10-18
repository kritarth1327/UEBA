from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class ModelMetadataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_name: str
    model_version: str
    is_ready: bool
    artifact_path: Optional[str] = None
    dataset_split: Optional[str] = None
    metrics: Optional[Dict[str, float]] = None
    confusion_matrix: Optional[List[List[int]]] = None
    threshold: Optional[float] = None
    evaluated_at: Optional[datetime] = None
    notes: Optional[str] = None


class ModelStatusResponse(BaseModel):
    models: List[ModelMetadataRead]
    pipeline_ready: bool
    all_models_ready: bool


class ModelEvaluationComparison(BaseModel):
    model_name: str
    version: str
    split: str
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    threshold: Optional[float] = None
    evaluated_at: Optional[datetime] = None
    is_available: bool = False


class EvaluationResponse(BaseModel):
    status: str
    message: str
    evaluations: List[ModelEvaluationComparison]
    last_run_timestamp: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime
    version: str = "1.0.0"


class ComponentStatus(BaseModel):
    name: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SystemStatusResponse(BaseModel):
    overall_status: str
    backend_status: ComponentStatus
    database_status: ComponentStatus
    dataset_status: ComponentStatus
    pipeline_status: ComponentStatus
    model_status: ComponentStatus
    timestamp: datetime
