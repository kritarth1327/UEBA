from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.system import ModelStatusResponse, EvaluationResponse
from app.services.model_evaluation_service import ModelEvaluationService

router = APIRouter()


@router.get("/models/status", response_model=ModelStatusResponse, summary="Detection models readiness and version status")
def get_models_status(db: Session = Depends(get_db)):
    service = ModelEvaluationService(db)
    return service.get_models_status()


@router.get("/models/evaluation", response_model=EvaluationResponse, summary="Experimental evaluation results")
def get_models_evaluation(db: Session = Depends(get_db)):
    service = ModelEvaluationService(db)
    return service.get_evaluation_results()
