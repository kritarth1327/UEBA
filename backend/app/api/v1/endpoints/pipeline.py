from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.pipeline.schema import FEATURE_NAMES, schema_description
from app.schemas.pipeline import (
    BaselineGenerateRequest, BaselineGenerateResponse, IngestRequest, IngestionReport, IngestionRunRead,
    PipelineSummary, RiskEvaluateRequest, RiskEvaluateResponse, ScoreRequest, ScoreResponse)
from app.services.baseline_service import BaselineService
from app.services.hybrid_risk_service import hybrid_risk_service
from app.services.ingestion_service import IngestionError, IngestionService
from app.services.pipeline_service import PipelineService
from app.services.scoring_service import ScoringService

router = APIRouter()


@router.get("/features/schema", summary="Shared behavioural feature contract (names, order, units)")
def get_feature_schema():
    return schema_description()


@router.post("/pipeline/ingest", response_model=IngestionReport, summary="Ingest a dataset (admin operation; use the CLI for very large files)")
def ingest(req: IngestRequest, db: Session = Depends(get_db)):
    try:
        return IngestionService(db).ingest(req.dataset, req.path, req.force,
                                           cert_file_is_removable_copy=req.cert_file_is_removable_copy)
    except IngestionError as e:
        code = status.HTTP_404_NOT_FOUND if "not found" in str(e) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/pipeline/baselines/generate", response_model=BaselineGenerateResponse, summary="Generate and persist personal baselines")
def generate_baselines(req: BaselineGenerateRequest, db: Session = Depends(get_db)):
    svc = BaselineService(db)
    if req.user_id:
        if not db.get(User, req.user_id):
            raise HTTPException(status_code=404, detail=f"User '{req.user_id}' was not found.")
        results = [svc.generate_for_user(req.user_id, req.as_of)]
    else:
        results = svc.generate_all(req.as_of)
    persisted = sum(1 for r in results if r["persisted"])
    return {"results": results, "persisted": persisted, "skipped": len(results) - persisted}


@router.post("/pipeline/score", response_model=ScoreResponse, summary="Score stored user-days with the hybrid engine; persist predictions and alerts")
def score(req: ScoreRequest, db: Session = Depends(get_db)):
    if req.start_date and req.end_date and req.start_date > req.end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    if req.user_id and not db.get(User, req.user_id):
        raise HTTPException(status_code=404, detail=f"User '{req.user_id}' was not found.")
    return ScoringService(db).score_range(req.user_id, req.start_date, req.end_date)


@router.post("/risk/evaluate", response_model=RiskEvaluateResponse, summary="Assess one feature vector; nothing is persisted")
def evaluate_risk(req: RiskEvaluateRequest, db: Session = Depends(get_db)):
    unknown = sorted(set(req.features) - set(FEATURE_NAMES))
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown feature(s): {unknown}; see GET /features/schema")
    result = ScoringService(db).assess_features(req.user_id, req.date, dict(req.features))
    if result is None:
        return {"assessed": False, "reason": "no component produced a usable signal "
                "(no personal baseline for this user and no trained model available)"}
    return {"assessed": True, **result}


@router.get("/risk/config", summary="Active hybrid-engine configuration (weights are provisional unless stated)")
def risk_config():
    return hybrid_risk_service.get_info()


@router.get("/pipeline/runs", response_model=List[IngestionRunRead], summary="Recent ingestion runs")
def list_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return PipelineService(db).list_runs(limit)


@router.get("/pipeline/summary", response_model=PipelineSummary, summary="Persisted data coverage and pipeline counts")
def pipeline_summary(db: Session = Depends(get_db)):
    return PipelineService(db).summary()
