from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.user import UserPagination, UserDetail
from app.schemas.behavior import UserBehaviorResponse
from app.schemas.baseline import UserBaselineResponse
from app.schemas.prediction import UserRiskHistoryResponse
from app.services.user_service import UserService
from app.services.behavior_service import BehaviorService
from app.services.baseline_service import BaselineService
from app.repositories.prediction_repository import PredictionRepository
from app.services.profile_store import features_of, load_user_history
from app.repositories.behavior_repository import BehaviorRepository

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


@router.get("/users/{user_id}/baseline", response_model=UserBaselineResponse, summary="Get a user's active personal baseline")
def get_user_baseline(user_id: str, db: Session = Depends(get_db)):
    if not UserService(db).get_user_detail(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with identifier '{user_id}' was not found."
        )

    baseline = BaselineService(db).get_user_baseline(user_id)
    return {"has_baseline": baseline is not None, "baseline": baseline}


@router.get("/users/{user_id}/baseline/deviation", summary="Compare one observed day with its point-in-time baseline")
def get_user_baseline_deviation(
    user_id: str,
    on: date = Query(..., description="Observed date to compare against prior history"),
    db: Session = Depends(get_db),
):
    if not UserService(db).get_user_detail(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with identifier '{user_id}' was not found."
        )

    profile = BehaviorRepository(db).get_by_user_and_date(user_id, on)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No behavioral profile was found for '{user_id}' on {on}."
        )

    features = features_of(profile)
    result = BaselineService(db).evaluate(
        user_id,
        on,
        features,
        load_user_history(db, user_id),
    )
    return {
        "user_id": user_id,
        "date": on,
        "observed": features,
        **result,
    }


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
