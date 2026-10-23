from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.cert_supervised_service import cert_supervised_service
from app.services.model_interfaces import ScoreStatus

router = APIRouter()


class CERTScoreRequest(BaseModel):
    features: Dict[str, Optional[float]] = Field(
        ...,
        description="CERT r4.2 daily feature values using the 11-feature model schema.",
    )


class CERTScoreResponse(BaseModel):
    status: str
    score: Optional[float] = None
    version: Optional[str] = None
    message: Optional[str] = None


@router.get("/models/cert-supervised/status")
def get_cert_supervised_status():
    return cert_supervised_service.get_info()


@router.post(
    "/models/cert-supervised/score",
    response_model=CERTScoreResponse,
)
def score_cert_features(request: CERTScoreRequest):
    result = cert_supervised_service.score(request.features)

    if result.status == ScoreStatus.ERROR:
        raise HTTPException(status_code=422, detail=result.detail)

    if result.status == ScoreStatus.UNAVAILABLE:
        raise HTTPException(status_code=503, detail=result.detail)

    return CERTScoreResponse(
        status=result.status.value,
        score=result.score,
        version=result.model_version,
        message=result.detail,
    )
