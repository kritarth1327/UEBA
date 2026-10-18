import json
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session
from app.models.model_metadata import ModelMetadata


class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_models(self) -> List[dict]:
        stmt = select(ModelMetadata).order_by(ModelMetadata.id)
        records = self.db.scalars(stmt).all()
        results = []
        for r in records:
            metrics = None
            cm = None
            if r.metrics_json:
                try:
                    metrics = json.loads(r.metrics_json)
                except Exception:
                    metrics = None
            if r.confusion_matrix_json:
                try:
                    cm = json.loads(r.confusion_matrix_json)
                except Exception:
                    cm = None

            results.append({
                "id": r.id,
                "model_name": r.model_name,
                "model_version": r.model_version,
                "is_ready": r.is_ready,
                "artifact_path": r.artifact_path,
                "dataset_split": r.dataset_split,
                "metrics": metrics,
                "confusion_matrix": cm,
                "threshold": r.threshold,
                "evaluated_at": r.evaluated_at,
                "notes": r.notes,
            })
        return results

    def get_by_name(self, model_name: str) -> Optional[dict]:
        stmt = select(ModelMetadata).where(ModelMetadata.model_name == model_name)
        r = self.db.scalars(stmt).first()
        if not r:
            return None

        metrics = None
        cm = None
        if r.metrics_json:
            try:
                metrics = json.loads(r.metrics_json)
            except Exception:
                metrics = None
        if r.confusion_matrix_json:
            try:
                cm = json.loads(r.confusion_matrix_json)
            except Exception:
                cm = None

        return {
            "id": r.id,
            "model_name": r.model_name,
            "model_version": r.model_version,
            "is_ready": r.is_ready,
            "artifact_path": r.artifact_path,
            "dataset_split": r.dataset_split,
            "metrics": metrics,
            "confusion_matrix": cm,
            "threshold": r.threshold,
            "evaluated_at": r.evaluated_at,
            "notes": r.notes,
        }

    def save(self, metadata: ModelMetadata) -> ModelMetadata:
        self.db.add(metadata)
        self.db.commit()
        self.db.refresh(metadata)
        return metadata
