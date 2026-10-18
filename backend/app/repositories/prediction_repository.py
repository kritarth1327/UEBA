import json
from datetime import date
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, desc, asc, func
from sqlalchemy.orm import Session
from app.models.prediction import ModelPrediction
from app.models.user import User
from app.models.alert import Alert


class PredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user(
        self,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[dict]:
        stmt = select(ModelPrediction).where(ModelPrediction.user_id == user_id)
        if start_date:
            stmt = stmt.where(ModelPrediction.date >= start_date)
        if end_date:
            stmt = stmt.where(ModelPrediction.date <= end_date)

        stmt = stmt.order_by(asc(ModelPrediction.date)).limit(limit)
        results = self.db.scalars(stmt).all()

        predictions = []
        for p in results:
            factors = []
            if p.contributing_factors_json:
                try:
                    factors = json.loads(p.contributing_factors_json)
                except Exception:
                    factors = []

            predictions.append({
                "id": p.id,
                "user_id": p.user_id,
                "date": p.date,
                "ml_threat_score": p.ml_threat_score,
                "ann_anomaly_score": p.ann_anomaly_score,
                "baseline_deviation_score": p.baseline_deviation_score,
                "hybrid_risk_score": p.hybrid_risk_score,
                "risk_level": p.risk_level,
                "contributing_factors": factors,
                "model_version": p.model_version,
                "evaluated_at": p.evaluated_at,
            })
        return predictions

    def get_latest_by_user(self, user_id: str) -> Optional[dict]:
        stmt = (
            select(ModelPrediction)
            .where(ModelPrediction.user_id == user_id)
            .order_by(desc(ModelPrediction.date))
        )
        p = self.db.scalars(stmt).first()
        if not p:
            return None

        factors = []
        if p.contributing_factors_json:
            try:
                factors = json.loads(p.contributing_factors_json)
            except Exception:
                factors = []

        return {
            "id": p.id,
            "user_id": p.user_id,
            "date": p.date,
            "ml_threat_score": p.ml_threat_score,
            "ann_anomaly_score": p.ann_anomaly_score,
            "baseline_deviation_score": p.baseline_deviation_score,
            "hybrid_risk_score": p.hybrid_risk_score,
            "risk_level": p.risk_level,
            "contributing_factors": factors,
            "model_version": p.model_version,
            "evaluated_at": p.evaluated_at,
        }

    def get_highest_risk_users(self, limit: int = 5) -> List[dict]:
        """Get users with highest latest risk scores."""
        subq = (
            select(
                ModelPrediction.user_id,
                ModelPrediction.hybrid_risk_score,
                ModelPrediction.risk_level,
                ModelPrediction.date.label("assessment_date"),
                func.row_number().over(
                    partition_by=ModelPrediction.user_id,
                    order_by=desc(ModelPrediction.date)
                ).label("rn")
            )
            .subquery()
        )

        alert_subq = (
            select(
                Alert.user_id,
                func.count(Alert.id).label("alert_count")
            )
            .group_by(Alert.user_id)
            .subquery()
        )

        query = (
            select(
                User.user_id,
                User.employee_name,
                User.department,
                subq.c.hybrid_risk_score,
                subq.c.risk_level,
                subq.c.assessment_date,
                func.coalesce(alert_subq.c.alert_count, 0).label("alert_count")
            )
            .join(subq, and_(User.user_id == subq.c.user_id, subq.c.rn == 1))
            .outerjoin(alert_subq, User.user_id == alert_subq.c.user_id)
            .where(subq.c.hybrid_risk_score.isnot(None))
            .order_by(desc(subq.c.hybrid_risk_score))
            .limit(limit)
        )

        results = self.db.execute(query).all()
        items = []
        for r in results:
            items.append({
                "user_id": r[0],
                "employee_name": r[1],
                "department": r[2],
                "hybrid_risk_score": float(r[3]),
                "risk_level": r[4],
                "assessment_date": r[5],
                "alert_count": int(r[6]),
            })
        return items

    def get_risk_distribution(self) -> Dict[str, int]:
        subq = (
            select(
                ModelPrediction.user_id,
                ModelPrediction.risk_level,
                func.row_number().over(
                    partition_by=ModelPrediction.user_id,
                    order_by=desc(ModelPrediction.date)
                ).label("rn")
            )
            .subquery()
        )

        query = (
            select(
                subq.c.risk_level,
                func.count()
            )
            .where(subq.c.rn == 1)
            .group_by(subq.c.risk_level)
        )

        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for level, count in self.db.execute(query).all():
            if level in counts:
                counts[level] = count

        total_users = self.db.scalar(select(func.count(User.user_id))) or 0
        assessed_users = sum(counts.values())
        unassessed = max(0, total_users - assessed_users)

        return {
            "high": counts["HIGH"],
            "medium": counts["MEDIUM"],
            "low": counts["LOW"],
            "unassessed": unassessed,
        }

    def save(self, prediction: ModelPrediction) -> ModelPrediction:
        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        return prediction
