from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.user import UserPagination, UserDetail
from app.schemas.behavior import UserBehaviorResponse
from app.schemas.prediction import UserRiskHistoryResponse
from app.services.user_service import UserService
from app.repositories.behavior_repository import BehaviorRepository
from app.services.ann_anomaly_service import ann_anomaly_service, FEATURES
from app.services.behavior_service import BehaviorService
from app.services.baseline_service import BaselineService
from app.repositories.prediction_repository import PredictionRepository

router = APIRouter()


@router.get("/users", response_model=UserPagination, summary="List paginated users with risk stats")
def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by ID, name, email, role"),
    department: Optional[str] = Query(None, description="Filter by department"),
    sort_by: str = Query("user_id", description="Sort column (user_id, risk, alerts, department)"),
    sort_dir: str = Query("asc", description="Sort direction (asc, desc)"),
    db: Session = Depends(get_db)
):
    service = UserService(db)
    return service.get_users_page(
        page=page,
        page_size=page_size,
        search=search,
        department=department,
        sort_by=sort_by,
        sort_dir=sort_dir
    )


@router.get("/users/{user_id}", response_model=UserDetail, summary="Get user details")
def get_user_detail(user_id: str, db: Session = Depends(get_db)):
    service = UserService(db)
    user = service.get_user_detail(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with identifier '{user_id}' was not found."
        )
    return user


@router.get("/users/{user_id}/behavior", response_model=UserBehaviorResponse, summary="Get user daily behavioral profiles")
def get_user_behavior(
    user_id: str,
    start_date: Optional[date] = Query(None, description="Filter from start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Filter to end date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500, description="Max daily records to return"),
    db: Session = Depends(get_db)
):
    user_service = UserService(db)
    if not user_service.get_user_detail(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with identifier '{user_id}' was not found."
        )

    behavior_service = BehaviorService(db)
    return behavior_service.get_user_behavior_history(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


@router.get("/users/{user_id}/risk", response_model=UserRiskHistoryResponse, summary="Get user risk assessment history")
def get_user_risk(
    user_id: str,
    start_date: Optional[date] = Query(None, description="Filter from start date"),
    end_date: Optional[date] = Query(None, description="Filter to end date"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    user_service = UserService(db)
    if not user_service.get_user_detail(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with identifier '{user_id}' was not found."
        )

    pred_repo = PredictionRepository(db)
    history = pred_repo.get_by_user(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    latest = pred_repo.get_latest_by_user(user_id)

    # Compute quick summary stats
    scores = [p["hybrid_risk_score"] for p in history if p["hybrid_risk_score"] is not None]
    summary = {
        "total_assessments": len(history),
        "max_risk_score": max(scores) if scores else None,
        "avg_risk_score": round(sum(scores) / len(scores), 1) if scores else None,
        "high_risk_days": sum(1 for p in history if p["risk_level"] == "HIGH")
    }

    return {
        "user_id": user_id,
        "latest_prediction": latest,
        "history": history,
        "summary": summary
    }


@router.get(
    "/users/{user_id}/anomalies",
    summary="Get ANN anomaly scores for a user's daily behavior",
)
def get_user_anomalies(
    user_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Score daily behavior profiles using the trained ANN autoencoder."""

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date.",
        )

    # Verify the user exists.
    user_service = UserService(db)
    if not user_service.get_user_detail(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )

    # Verify that the trained ANN artifacts are available.
    if not ann_anomaly_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ANN unavailable. Check the model, scaler, and threshold artifacts.",
        )

    # Fetch daily profiles from the database.
    behavior_repo = BehaviorRepository(db)
    profiles = behavior_repo.get_by_user(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    results = []

    for profile in profiles:
        # Preserve the exact feature order used during ANN training.
        feature_vector = [float(profile[name]) for name in FEATURES]
        prediction = ann_anomaly_service.predict(feature_vector)

        if prediction is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ANN inference is unavailable.",
            )

        results.append({
            "date": profile["date"],
            "ann_anomaly_score": prediction["ann_anomaly_score"],
            "threshold": prediction["threshold"],
            "is_anomaly_candidate": prediction["is_anomaly_candidate"],
            "interpretation": prediction["interpretation"],
        })

    candidate_count = sum(
        result["is_anomaly_candidate"] for result in results
    )

    return {
        "user_id": user_id,
        "total_profiles_scored": len(results),
        "anomaly_candidates": candidate_count,
        "model_name": ann_anomaly_service.model_name,
        "model_version": ann_anomaly_service.version,
        "threshold": ann_anomaly_service.get_info()["threshold"],
        "features_used": FEATURES,
        "results": results,
        "notice": (
            "Above-threshold profiles are anomaly candidates, "
            "not confirmed malicious activity."
        ),
    }
