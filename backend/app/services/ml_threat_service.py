import json
import math
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Mapping
from app.core.config import settings
from app.core.logging import logger
from app.pipeline.schema import SCHEMA_VERSION, FEATURE_NAMES, vectorize
from app.services.model_interfaces import ScoreResult


class MLThreatService:
    """Service interface for Supervised Machine Learning Threat Classifiers (XGBoost / Random Forest)."""

    name = "ml_threat"

    def __init__(self, predictor: Optional[Callable[[List[float]], float]] = None,
                 meta: Optional[Dict[str, Any]] = None):
        """`predictor`/`meta` allow tests (or the training owner) to inject a scorer without
        touching disk. In production both come from the artifact files."""
        self.model_name = "xgboost_threat_classifier"
        self.version = "1.0.0"
        self.model_path = settings.MODELS_DIR / "xgboost_threat_classifier.json"
        # Contract sidecar: {"schema_version", "feature_names": [...]} written at training time
        self.meta_path = settings.MODELS_DIR / "xgboost_threat_classifier.meta.json"
        self._model = None
        self._predictor = predictor
        self._meta = meta
        if predictor is None:
            self._load_model_if_exists()
            self._load_meta()

    def _load_meta(self):
        if self.meta_path.exists():
            try:
                self._meta = json.loads(self.meta_path.read_text())
            except Exception as e:
                logger.warning(f"Unreadable ML contract file {self.meta_path}: {e}")
                self._meta = None

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
        return self._model is not None or self._predictor is not None

    def score(self, features: Mapping[str, Optional[float]]) -> ScoreResult:
        """Stable interface: schema-named features in, ScoreResult (probability in [0,1]) out."""
        if not self.is_available():
            return ScoreResult.unavailable("supervised model artifact not found", self.version)
        meta = self._meta
        if not meta or not meta.get("feature_names"):
            return ScoreResult.unavailable("model contract file (.meta.json with feature_names) missing", self.version)
        if meta.get("schema_version") != SCHEMA_VERSION:
            return ScoreResult.error(
                f"schema_version mismatch: model={meta.get('schema_version')} engine={SCHEMA_VERSION}", self.version)
        unknown = [n for n in meta["feature_names"] if n not in FEATURE_NAMES]
        if unknown:
            return ScoreResult.error(f"model expects unknown features: {unknown}", self.version)
        vec = vectorize(features, meta["feature_names"])  # NaN for missing; tree models may handle NaN
        if self._predictor is not None:
            p = float(self._predictor(vec))
        else:
            p = self.predict_threat_score(vec)
        if p is None or not math.isfinite(p):
            return ScoreResult.error("model returned a non-finite prediction", self.version)
        return ScoreResult.ok(p, p, meta.get("model_version", self.version))

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
            "contract_file_present": self.meta_path.exists() or self._meta is not None,
            "message": "Model ready for inference" if self.is_available() else "Supervised ML model artifact not found. Awaiting CERT dataset training."
        }


ml_threat_service = MLThreatService()
