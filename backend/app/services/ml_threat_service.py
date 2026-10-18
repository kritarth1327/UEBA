import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging import logger


class MLThreatService:
    """Service interface for Supervised Machine Learning Threat Classifiers (XGBoost / Random Forest)."""

    def __init__(self):
        self.model_name = "xgboost_threat_classifier"
        self.version = "1.0.0"
        self.model_path = settings.MODELS_DIR / "xgboost_threat_classifier.json"
        self._model = None
        self._load_model_if_exists()

    def _load_model_if_exists(self):
        if self.model_path.exists():
            try:
                import xgboost as xgb
                self._model = xgb.Booster()
                self._model.load_model(str(self.model_path))
                logger.info(f"Loaded ML threat model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Found model file at {self.model_path} but failed to load: {e}")
                self._model = None
        else:
            self._model = None

    def is_available(self) -> bool:
        """Indicates whether real model weights and inference pipeline are ready."""
        return self._model is not None

    def predict_threat_score(self, feature_vector: List[float]) -> Optional[float]:
        """Runs inference if trained model artifact exists. Returns None if unavailable."""
        if not self.is_available():
            return None

        import xgboost as xgb
        import numpy as np

        data = xgb.DMatrix(np.array([feature_vector]))
        pred = self._model.predict(data)
        return float(pred[0])

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "is_available": self.is_available(),
            "artifact_path": str(self.model_path) if self.model_path.exists() else None,
            "framework": "XGBoost",
            "message": "Model ready for inference" if self.is_available() else "Supervised ML model artifact not found. Awaiting CERT dataset training."
        }


ml_threat_service = MLThreatService()
