
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service
from app.services.hybrid_risk_service import hybrid_risk_service


class ModelEvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EvaluationRepository(db)
        self.metrics_path = (
            Path(settings.MODELS_DIR) / "supervised_metrics.json"
        )

    def _load_file_metrics(self) -> Dict[str, Any]:
        if not self.metrics_path.exists():
            return {}

        try:
            with self.metrics_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _map_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "accuracy": metrics.get("accuracy"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "f1_score": metrics.get("f1_score", metrics.get("f1")),
            "roc_auc": metrics.get("roc_auc"),
            "pr_auc": metrics.get("pr_auc"),
        }

    @staticmethod
    def _map_model_metrics(
        metrics: Dict[str, Any], model_key: str
    ) -> Dict[str, Any]:
        model_metrics = metrics.get("models", {}).get(model_key, {})
        result = ModelEvaluationService._map_metrics(model_metrics)
        result["confusion_matrix"] = model_metrics.get(
            "confusion_matrix_labels_0_1",
            model_metrics.get("confusion_matrix"),
        )
        return result

    def get_models_status(self) -> Dict[str, Any]:
        records = self.repo.get_all_models()
        record_map = {record["model_name"]: record for record in records}

        file_metrics = self._load_file_metrics()
        split_info = file_metrics.get("split", {})
        split_name = split_info.get("method", "pending")
        dataset_name = file_metrics.get("dataset", "unknown")
        warning = file_metrics.get(
            "warning",
            "Evaluation provenance has not been verified.",
        )

        definitions = [
            {
                "id": 1,
                "model_name": "Random Forest Baseline",
                "record_key": "Random Forest Baseline",
                "version": "v1.0.0",
                "artifact": "random_forest.joblib",
                "ready": False,
                "metrics_key": "random_forest",
                "notes": "Awaiting validated threat-detection evaluation.",
            },
            {
                "id": 2,
                "model_name": "XGBoost Supervised Threat Classifier",
                "record_key": "XGBoost Supervised Threat Classifier",
                "version": "v1.0.0",
                "artifact": "xgboost_threat_classifier.json",
                "ready": ml_threat_service.is_available(),
                "metrics_key": "xgboost",
                "notes": warning,
            },
            {
                "id": 3,
                "model_name": "Dense Autoencoder Anomaly Detector",
                "record_key": "Dense Autoencoder Anomaly Detector",
                "version": "v1.0.0",
                "artifact": "dense_autoencoder.pt",
                "ready": ann_anomaly_service.is_available(),
                "metrics_key": None,
                "notes": "Requires a trained checkpoint and calibration contract.",
            },
            {
                "id": 4,
                "model_name": "Hybrid Risk Engine",
                "record_key": "Hybrid Risk Engine",
                "version": "v2.0.0",
                "artifact": None,
                "ready": hybrid_risk_service.is_available(),
                "metrics_key": None,
                "notes": "Requires end-to-end evaluation on defensible labels.",
            },
        ]

        models = []
        for definition in definitions:
            record = record_map.get(definition["record_key"], {})
            model_metrics = (
                file_metrics.get("models", {}).get(
                    definition["metrics_key"], {}
                )
                if definition["metrics_key"]
                else {}
            )

            db_metrics = record.get("metrics")
            if db_metrics is not None:
                model_metrics = db_metrics

            confusion_matrix = (
                model_metrics.get("confusion_matrix_labels_0_1")
                or model_metrics.get("confusion_matrix")
                or record.get("confusion_matrix")
            )

            artifact_name = definition["artifact"]
            artifact_path = (
                str(Path(settings.MODELS_DIR) / artifact_name)
                if artifact_name
                and (Path(settings.MODELS_DIR) / artifact_name).exists()
                else record.get("artifact_path")
            )

            models.append(
                {
                    "id": record.get("id", definition["id"]),
                    "model_name": definition["model_name"],
                    "model_version": record.get(
                        "model_version", definition["version"]
                    ),
                    "is_ready": bool(definition["ready"]),
                    "artifact_path": artifact_path,
                    "dataset_split": record.get(
                        "dataset_split", split_name
                    ),
                    "metrics": (
                        self._map_metrics(model_metrics)
                        if model_metrics
                        else None
                    ),
                    "confusion_matrix": confusion_matrix,
                    "threshold": record.get("threshold", 0.5),
                    "evaluated_at": record.get("evaluated_at"),
                    "notes": definition["notes"],
                }
            )

        pipeline_ready = all(model["is_ready"] for model in models)
        return {
            "models": models,
            "pipeline_ready": pipeline_ready,
            "all_models_ready": pipeline_ready,
        }

    def get_evaluation_results(self) -> Dict[str, Any]:
        records = self.repo.get_all_models()
        record_map = {record["model_name"]: record for record in records}
        file_metrics = self._load_file_metrics()

        definitions = [
            ("Random Forest Baseline", "random_forest", False),
            ("XGBoost Classifier", "xgboost", ml_threat_service.is_available()),
            ("Dense Autoencoder", None, ann_anomaly_service.is_available()),
            ("Hybrid Risk Engine", None, hybrid_risk_service.is_available()),
        ]

        evaluations = []
        has_evaluations = False
        timestamps = []

        for model_name, metrics_key, is_available in definitions:
            record = record_map.get(model_name, {})
            metrics = record.get("metrics")

            # File-level metrics alone do not establish a recorded,
            # validated insider-threat evaluation.

            if metrics:
                has_evaluations = True

            mapped = self._map_metrics(metrics or {})
            cm = (
                (metrics or {}).get("confusion_matrix_labels_0_1")
                or (metrics or {}).get("confusion_matrix")
                or record.get("confusion_matrix")
            )

            evaluated_at = record.get("evaluated_at")
            if evaluated_at:
                timestamps.append(evaluated_at)

            evaluations.append(
                {
                    "model_name": model_name,
                    "version": record.get("model_version", "v1.0.0"),
                    "split": record.get(
                        "dataset_split",
                        file_metrics.get("split", {}).get(
                            "method", "pending"
                        ),
                    ),
                    **mapped,
                    "threshold": record.get("threshold", 0.5),
                    "evaluated_at": evaluated_at,
                    "is_available": bool(metrics),
                }
            )

        return {
            "status": "ready" if has_evaluations else "unavailable",
            "message": (
                "Evaluation metrics loaded. SPEDIA metrics represent "
                "source-label prediction, not validated insider-threat detection."
                if has_evaluations
                else "No model evaluation metrics have been recorded or found."
            ),
            "evaluations": evaluations,
            "last_run_timestamp": max(timestamps) if timestamps else None,
        }
