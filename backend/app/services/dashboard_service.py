from datetime import datetime, timezone, timedelta, date
from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.behavior import DailyBehaviorProfile
from app.models.alert import Alert
from app.models.prediction import ModelPrediction
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.alert_repository import AlertRepository
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.pred_repo = PredictionRepository(db)
        self.alert_repo = AlertRepository(db)

    def get_overview(self) -> Dict[str, Any]:
        """Calculates real dashboard metrics derived exclusively from database records."""
        # 1. Total users
        total_users = self.db.scalar(select(func.count(User.user_id))) or 0

        # 2. Assessed users
        assessed_users = (
            self.db.scalar(
                select(func.count(func.distinct(ModelPrediction.user_id)))
            )
            or 0
        )

        # 3. Alerts by severity
        alerts_by_sev = self.alert_repo.get_severity_counts()

        # 4. Risk distribution
        risk_dist = self.pred_repo.get_risk_distribution()

        # 5. Activity trends (last 14 observed dates or empty if none)
        trend_stmt = (
            select(
                DailyBehaviorProfile.date,
                func.count(DailyBehaviorProfile.id).label("total_profiles"),
                func.sum(DailyBehaviorProfile.after_hours_logons + DailyBehaviorProfile.removable_device_events).label("anomalous_signals")
            )
            .group_by(DailyBehaviorProfile.date)
            .order_by(DailyBehaviorProfile.date.desc())
            .limit(14)
        )
        trend_rows = self.db.execute(trend_stmt).all()
        activity_trends = []
        for r in reversed(trend_rows):
            activity_trends.append({
                "date": r[0],
                "total_events": int(r[1] or 0),
                "anomalous_events": int(r[2] or 0)
            })

        # 6. Recent alerts
        recent_alerts = self.alert_repo.get_recent(limit=5)

        # 7. Highest risk users
        highest_risk_users = self.pred_repo.get_highest_risk_users(limit=5)

        # 8. Readiness flags
        models_ready = ml_threat_service.is_available() and ann_anomaly_service.is_available()
        dataset_ready = total_users > 0

        # 9. Latest evaluation timestamp
        last_eval = self.db.scalar(select(func.max(ModelPrediction.evaluated_at)))

        return {
            "total_users": total_users,
            "assessed_users": assessed_users,
            "alerts_by_severity": alerts_by_sev,
            "risk_distribution": risk_dist,
            "activity_trends": activity_trends,
            "recent_alerts": recent_alerts,
            "highest_risk_users": highest_risk_users,
            "dataset_ready": dataset_ready,
            "models_ready": models_ready,
            "last_evaluated_at": last_eval
        }
