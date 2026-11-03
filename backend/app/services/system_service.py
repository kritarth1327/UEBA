import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User
from app.models.behavior import DailyBehaviorProfile
from app.models.ingestion import IngestionRun
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service
from app.services.cert_supervised_service import cert_supervised_service
from app.services.hybrid_risk_service import hybrid_risk_service


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

        # 2. Dataset check: source diagnostics are separate from persisted readiness.
        raw_r42_path = settings.CERT_R42_DIR
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

        spedia_file = settings.SPEDIA_FILE
        completed_runs = list(self.db.scalars(select(IngestionRun).where(
            IngestionRun.status == "completed"
        ).order_by(IngestionRun.id.desc())))
        persisted_profiles = db_details.get("persisted_profiles", 0)
        active_datasets = sorted({
            source for source in self.db.scalars(select(DailyBehaviorProfile.dataset_source).distinct())
            if source
        })
        if completed_runs and persisted_profiles > 0:
            dataset_status = "processed"
            dataset_msg = (
                f"Persisted behavioral data is available from "
                f"{', '.join(active_datasets) or 'a supported dataset'}."
            )
        elif persisted_profiles > 0:
            dataset_status = "processed"
            dataset_msg = "Persisted behavioral profiles are available."
        elif raw_r42_path.exists() or spedia_file.exists():
            dataset_status = "available"
            dataset_msg = "A supported dataset source is available but has not been ingested."
        else:
            dataset_status = "unavailable"
            dataset_msg = "No supported dataset source has been ingested or located."
        dataset_details = {
            "expected_directory": str(raw_r42_path),
            "expected_files": expected_files,
            "files_found": found_files,
            # Second supported source (see docs/dataset_selection.md); CERT fields above are unchanged
            "spedia": {"expected_file": spedia_file.name, "present": spedia_file.exists()},
            "active_datasets": active_datasets,
            "completed_ingestion_runs": len(completed_runs),
        }

        # 3. Processing Pipeline check
        pipeline_status = "pending"
        pipeline_msg = "Ingestion pipeline awaiting dataset extraction."
        if db_details.get("persisted_profiles", 0) > 0:
            pipeline_status = "processed"
            pipeline_msg = f"Profiles aggregated: {db_details.get('persisted_profiles')} daily records."
        elif dataset_status == "available":
            pipeline_status = "ready"
            pipeline_msg = "Ready to execute user-day profile ingestion."

        # 4. Model Artifact check
        ml_available = ml_threat_service.is_available()
        ann_available = ann_anomaly_service.is_available()
        cert_available = cert_supervised_service.is_available()
        models_ready = ml_available or cert_available
        model_status = (
            "ready"
            if ml_available and ann_available and cert_available
            else "partial"
            if models_ready
            else "unavailable"
        )
        model_msg = (
            "All inference components loaded and ready."
            if model_status == "ready"
            else "Partial inference available; unavailable components are reported per assessment."
            if model_status == "partial"
            else "No inference model components are available."
        )
        model_details = {
            "xgboost_available": ml_available,
            "autoencoder_available": ann_available,
            "cert_supervised_available": cert_available,
            "hybrid_available": hybrid_risk_service.is_available(),
            "artifacts_directory": str(settings.MODELS_DIR)
        }

        # Overall health
        overall = (
            "operational"
            if db_status == "healthy" and dataset_status == "processed" and models_ready
            else "pending_data"
        )

        return {
            "overall_status": overall,
            "backend_status": {
                "name": "FastAPI Application",
                "status": "healthy",
                "message": f"API server running on Python {platform.python_version()}.",
                "details": {"python_version": platform.python_version(), "api_version": "v1"}
            },
            "database_status": {
                "name": "Database Connectivity",
                "status": db_status,
                "message": db_msg,
                "details": db_details
            },
            "dataset_status": {
                "name": "Supported Dataset Sources",
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
