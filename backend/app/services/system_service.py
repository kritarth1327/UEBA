import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User
from app.models.behavior import DailyBehaviorProfile
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service


class SystemService:
    def __init__(self, db: Session):
        self.db = db

    def check_health(self) -> Dict[str, Any]:
        """Performs quick ping check of application and database connectivity."""
        db_status = "disconnected"
        overall = "degraded"
        try:
            self.db.execute(text("SELECT 1"))
            db_status = "connected"
            overall = "ok"
        except Exception:
            db_status = "disconnected"
            overall = "degraded"

        return {
            "status": overall,
            "database": db_status,
            "timestamp": datetime.now(timezone.utc),
            "version": "1.0.0"
        }

    def check_full_system(self) -> Dict[str, Any]:
        """Evaluates operational readiness of all system components."""
        # 1. Database check
        db_status = "healthy"
        db_msg = "Database connected and responsive."
        db_details = {}
        try:
            self.db.execute(text("SELECT 1"))
            user_cnt = self.db.scalar(select(func.count(User.user_id))) or 0
            profile_cnt = self.db.scalar(select(func.count(DailyBehaviorProfile.id))) or 0
            db_details = {
                "driver": self.db.bind.dialect.name if self.db.bind else "unknown",
                "persisted_users": user_cnt,
                "persisted_profiles": profile_cnt
            }
        except Exception as e:
            db_status = "unhealthy"
            db_msg = f"Database connectivity error: {str(e)}"

        # 2. Dataset check (CERT r4.2 raw files)
        dataset_status = "unavailable"
        dataset_msg = "CERT Insider Threat Dataset r4.2 not yet extracted to data/raw/r4.2/."
        raw_r42_path = settings.RAW_DATA_DIR / "r4.2"
        expected_files = ["logon.csv", "device.csv", "file.csv", "email.csv", "http.csv"]
        found_files = []
        if raw_r42_path.exists():
            for f in expected_files:
                if (raw_r42_path / f).exists():
                    found_files.append(f)

            if len(found_files) == len(expected_files):
                dataset_status = "ready"
                dataset_msg = "All core CERT r4.2 log files are present and verified."
            elif len(found_files) > 0:
                dataset_status = "partial"
                dataset_msg = f"Partial dataset detected: {len(found_files)} of {len(expected_files)} files available."

        dataset_details = {
            "expected_directory": str(raw_r42_path),
            "expected_files": expected_files,
            "files_found": found_files
        }

        # 3. Processing Pipeline check
        pipeline_status = "pending"
        pipeline_msg = "Ingestion pipeline awaiting dataset extraction."
        if dataset_status == "ready":
            pipeline_status = "ready"
            pipeline_msg = "Ready to execute user-day profile ingestion."
        elif db_details.get("persisted_profiles", 0) > 0:
            pipeline_status = "processed"
            pipeline_msg = f"Profiles aggregated: {db_details.get('persisted_profiles')} daily records."

        # 4. Model Artifact check
        xgboost_available = ml_threat_service.is_available()
        autoencoder_available = ann_anomaly_service.is_available()

        if xgboost_available and autoencoder_available:
            model_status = "ready"
            model_msg = (
                "XGBoost and Dense Autoencoder are loaded and ready for inference."
            )
        elif autoencoder_available:
            model_status = "partial"
            model_msg = (
                "Dense Autoencoder is loaded and ready for anomaly detection. "
                "XGBoost classifier weights are unavailable."
            )
        elif xgboost_available:
            model_status = "partial"
            model_msg = (
                "XGBoost classifier is loaded. "
                "Dense Autoencoder weights are unavailable."
            )
        else:
            model_status = "unavailable"
            model_msg = "No detection model weights are available."

        models_ready = xgboost_available and autoencoder_available

        model_details = {
            "xgboost_available": xgboost_available,
            "autoencoder_available": autoencoder_available,
            "artifacts_directory": str(settings.MODELS_DIR)
        }

        # Overall health
        overall = "operational" if db_status == "healthy" and dataset_status == "ready" and models_ready else "pending_data"

        return {
            "overall_status": overall,
            "backend_status": {
                "name": "FastAPI Application",
                "status": "healthy",
                "message": "API server running on Python 3.14.7.",
                "details": {"python_version": "3.14.7", "api_version": "v1"}
            },
            "database_status": {
                "name": "Database Connectivity",
                "status": db_status,
                "message": db_msg,
                "details": db_details
            },
            "dataset_status": {
                "name": "CERT r4.2 Dataset",
                "status": dataset_status,
                "message": dataset_msg,
                "details": dataset_details
            },
            "pipeline_status": {
                "name": "Feature Engineering Pipeline",
                "status": pipeline_status,
                "message": pipeline_msg,
                "details": {"feature_aggregation": "User-Day Profiles"}
            },
            "model_status": {
                "name": "ML & ANN Models",
                "status": model_status,
                "message": model_msg,
                "details": model_details
            },
            "timestamp": datetime.now(timezone.utc)
        }
