import json
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.baseline import PersonalBaseline
from app.models.behavior import DailyBehaviorProfile
from app.models.ingestion import IngestionRun
from app.models.prediction import ModelPrediction
from app.models.user import User


def run_to_dict(r: IngestionRun) -> Dict[str, Any]:
    return {"id": r.id, "dataset": r.dataset, "status": r.status, "source_path": r.source_path,
            "schema_version": r.schema_version, "started_at": r.started_at, "finished_at": r.finished_at,
            "error": r.error, "report": json.loads(r.report_json) if r.report_json else None}


class PipelineService:
    def __init__(self, db: Session):
        self.db = db

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        q = select(IngestionRun).order_by(IngestionRun.id.desc()).limit(limit)
        return [run_to_dict(r) for r in self.db.scalars(q)]

    def summary(self) -> Dict[str, Any]:
        d = DailyBehaviorProfile
        rows = self.db.execute(select(
            d.dataset_source, func.count(d.id), func.count(func.distinct(d.user_id)),
            func.min(d.date), func.max(d.date), func.sum(d.event_count), func.sum(d.anomalous_event_count)
        ).group_by(d.dataset_source)).all()
        datasets = {
            (src or "unknown"): {"user_days": n, "users": u, "first_date": lo, "last_date": hi,
                                 "events": ev, "labelled_anomalous_events": an}
            for src, n, u, lo, hi, ev, an in rows}
        last = self.db.scalars(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(1)).first()
        count = lambda col: self.db.scalar(select(func.count(col))) or 0  # noqa: E731
        return {
            "datasets": datasets, "users": count(User.user_id), "predictions": count(ModelPrediction.id),
            "alerts": count(Alert.id),
            "active_baselines": self.db.scalar(select(func.count(PersonalBaseline.id)).where(
                PersonalBaseline.is_active.is_(True))) or 0,
            "last_ingestion": run_to_dict(last) if last else None,
        }
