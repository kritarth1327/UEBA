from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service
from app.services.hybrid_risk_service import hybrid_risk_service


class ModelEvaluationService:
    def __init__(self, db: Session):
        self.repo = EvaluationRepository(db)

    def get_models_status(self) -> Dict[str, Any]:
        """Returns readiness and version info for all detection components."""
        db_records = self.repo.get_all_models()
        record_map = {r["model_name"]: r for r in db_records}

        components = [
            {
                "id": 1,
                "model_name": "Random Forest Baseline",
                "model_version": "v1.0.0",
                "is_ready": record_map.get("random_forest", {}).get("is_ready", False),
                "artifact_path": record_map.get("random_forest", {}).get("artifact_path"),
                "dataset_split": record_map.get("random_forest", {}).get("dataset_split"),
                "metrics": record_map.get("random_forest", {}).get("metrics"),
                "confusion_matrix": record_map.get("random_forest", {}).get("confusion_matrix"),
                "threshold": record_map.get("random_forest", {}).get("threshold"),
                "evaluated_at": record_map.get("random_forest", {}).get("evaluated_at"),
                "notes": record_map.get("random_forest", {}).get("notes", "Awaiting CERT r4.2 training split.")
            },
            {
                "id": 2,
                "model_name": "XGBoost Supervised Threat Classifier",
                "model_version": "v1.0.0",
                "is_ready": ml_threat_service.is_available() or record_map.get("xgboost", {}).get("is_ready", False),
                "artifact_path": str(ml_threat_service.model_path) if ml_threat_service.model_path.exists() else None,
                "dataset_split": record_map.get("xgboost", {}).get("dataset_split"),
                "metrics": record_map.get("xgboost", {}).get("metrics"),
                "confusion_matrix": record_map.get("xgboost", {}).get("confusion_matrix"),
                "threshold": record_map.get("xgboost", {}).get("threshold"),
                "evaluated_at": record_map.get("xgboost", {}).get("evaluated_at"),
                "notes": record_map.get("xgboost", {}).get("notes", "Awaiting CERT r4.2 training split.")
            },
            {
                "id": 3,
                "model_name": "Dense Autoencoder Anomaly Detector",
                "model_version": "v1.0.0",
                "is_ready": ann_anomaly_service.is_available() or record_map.get("dense_autoencoder", {}).get("is_ready", False),
                "artifact_path": str(ann_anomaly_service.model_path) if ann_anomaly_service.model_path.exists() else None,
                "dataset_split": record_map.get("dense_autoencoder", {}).get("dataset_split"),
                "metrics": record_map.get("dense_autoencoder", {}).get("metrics"),
                "confusion_matrix": record_map.get("dense_autoencoder", {}).get("confusion_matrix"),
                "threshold": record_map.get("dense_autoencoder", {}).get("threshold"),
                "evaluated_at": record_map.get("dense_autoencoder", {}).get("evaluated_at"),
                "notes": record_map.get("dense_autoencoder", {}).get("notes", "Awaiting normal profile training on CERT data.")
            },
            {
                "id": 4,
                "model_name": "Hybrid Risk Engine",
                "model_version": "v1.0.0",
                "is_ready": hybrid_risk_service.is_available() or record_map.get("hybrid_risk_engine", {}).get("is_ready", False),
                "artifact_path": None,
                "dataset_split": record_map.get("hybrid_risk_engine", {}).get("dataset_split"),
                "metrics": record_map.get("hybrid_risk_engine", {}).get("metrics"),
                "confusion_matrix": record_map.get("hybrid_risk_engine", {}).get("confusion_matrix"),
                "threshold": 70.0,
                "evaluated_at": record_map.get("hybrid_risk_engine", {}).get("evaluated_at"),
                "notes": record_map.get("hybrid_risk_engine", {}).get("notes", "Multi-signal fusion of ML threat score, ANN anomaly score, and baseline deviation.")
            }
        ]

        all_ready = all(m["is_ready"] for m in components)
        return {
            "models": components,
            "pipeline_ready": all_ready,
            "all_models_ready": all_ready
        }

    def get_evaluation_results(self) -> Dict[str, Any]:
        """Returns genuine evaluation results if available in database or an honest unavailable state."""
        db_records = self.repo.get_all_models()
        has_evaluations = any(r.get("metrics") is not None for r in db_records)

        evaluations = []
        for model_key, display_name in [
            ("random_forest", "Random Forest Baseline"),
            ("xgboost", "XGBoost Classifier"),
            ("dense_autoencoder", "Dense Autoencoder"),
            ("hybrid_risk_engine", "Hybrid Risk Engine")
        ]:
            rec = next((r for r in db_records if r["model_name"] == model_key), None)
            if rec and rec.get("metrics"):
                metrics = rec["metrics"]
                evaluations.append({
                    "model_name": display_name,
                    "version": rec.get("model_version", "v1.0.0"),
                    "split": rec.get("dataset_split", "test"),
                    "accuracy": metrics.get("accuracy"),
                    "precision": metrics.get("precision"),
                    "recall": metrics.get("recall"),
                    "f1_score": metrics.get("f1_score"),
                    "roc_auc": metrics.get("roc_auc"),
                    "pr_auc": metrics.get("pr_auc"),
                    "threshold": rec.get("threshold"),
                    "evaluated_at": rec.get("evaluated_at"),
                    "is_available": True
                })
            else:
                evaluations.append({
                    "model_name": display_name,
                    "version": "v1.0.0",
                    "split": "pending",
                    "accuracy": None,
                    "precision": None,
                    "recall": None,
                    "f1_score": None,
                    "roc_auc": None,
                    "pr_auc": None,
                    "threshold": None,
                    "evaluated_at": None,
                    "is_available": False
                })

        return {
            "status": "ready" if has_evaluations else "unavailable",
            "message": "Evaluation metrics loaded from experiment records." if has_evaluations else "No model evaluations have been recorded yet. The CERT dataset r4.2 is pending ingestion and model training.",
            "evaluations": evaluations,
            "last_run_timestamp": None
        }
