import json
import math
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Mapping
from app.core.config import settings
from app.core.logging import logger
from app.pipeline.schema import SCHEMA_VERSION, FEATURE_NAMES, vectorize
from app.services.model_interfaces import ScoreResult


class ANNAnomalyService:
    """Service interface for Neural Network Anomaly Detection (Dense Autoencoder)."""

    name = "ann_anomaly"

    def __init__(self, error_fn: Optional[Callable[[List[float]], float]] = None,
                 meta: Optional[Dict[str, Any]] = None):
        """`error_fn` maps a PREPROCESSED vector to reconstruction error (test/owner injection)."""
        self.model_name = "dense_autoencoder"
        self.version = "1.0.0"
        self.model_path = settings.MODELS_DIR / "dense_autoencoder.pt"
        # Contract + calibration sidecar, e.g.
        # {"schema_version","feature_names","preprocessing":{"log1p":bool,"mean":[..],"scale":[..]},
        #  "threshold": <reconstruction error at the calibration percentile>, "calibration": "p95 of validation error"}
        self.threshold_path = settings.MODELS_DIR / "autoencoder_threshold.json"
        self._model = None
        self._threshold = None
        self._error_fn = error_fn
        self._meta = meta
        if error_fn is None:
            self._load_model_if_exists()
            if self.threshold_path.exists():
                try:
                    self._meta = json.loads(self.threshold_path.read_text())
                except Exception as e:
                    logger.warning(f"Unreadable ANN contract file {self.threshold_path}: {e}")

    def _load_model_if_exists(self):
        if self.model_path.exists():
            try:
                import torch
                self._model = torch.load(str(self.model_path), weights_only=True)
                self._model.eval()
                logger.info(f"Loaded ANN Autoencoder model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Found model file at {self.model_path} but failed to load: {e}")
                self._model = None
        else:
            self._model = None

    def is_available(self) -> bool:
        return self._model is not None or self._error_fn is not None

    def score(self, features: Mapping[str, Optional[float]]) -> ScoreResult:
        """Stable interface. Anomaly score = err / (err + threshold) in [0, 1): 0.5 exactly at the
        calibrated threshold (PROVISIONAL mapping; the threshold comes from the training owner)."""
        if not self.is_available():
            return ScoreResult.unavailable("ANN artifact not found", self.version)
        meta = self._meta or {}
        names, thr = meta.get("feature_names"), meta.get("threshold")
        if not names or not thr or thr <= 0:
            return ScoreResult.unavailable("ANN contract file (feature_names, threshold) missing", self.version)
        if meta.get("schema_version") != SCHEMA_VERSION:
            return ScoreResult.error(
                f"schema_version mismatch: model={meta.get('schema_version')} engine={SCHEMA_VERSION}", self.version)
        if any(n not in FEATURE_NAMES for n in names):
            return ScoreResult.error("model expects features outside the shared schema", self.version)
        vec = vectorize(features, names)
        if any(math.isnan(v) for v in vec):
            missing = [n for n, v in zip(names, vec) if math.isnan(v)]
            return ScoreResult.error(f"required features missing/unavailable: {missing}", self.version)
        pre = meta.get("preprocessing") or {}
        if pre.get("log1p"):
            vec = [math.log1p(max(v, 0.0)) for v in vec]
        if pre.get("mean") and pre.get("scale"):
            vec = [(v - m) / (sc if sc else 1.0) for v, m, sc in zip(vec, pre["mean"], pre["scale"])]
        err = self._error_fn(vec) if self._error_fn is not None else self.predict_reconstruction_error(vec)
        if err is None or not math.isfinite(err) or err < 0:
            return ScoreResult.error("invalid reconstruction error", self.version)
        return ScoreResult.ok(err / (err + thr), err, meta.get("model_version", self.version))

    def predict_reconstruction_error(self, feature_vector: List[float]) -> Optional[float]:
        """Runs autoencoder forward pass and calculates MSE reconstruction error."""
        if not self.is_available():
            return None

        import torch
        import numpy as np

        with torch.no_grad():
            tensor_in = torch.tensor([feature_vector], dtype=torch.float32)
            reconstruction = self._model(tensor_in)
            loss = torch.mean((tensor_in - reconstruction) ** 2).item()
            return float(loss)

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "is_available": self.is_available(),
            "artifact_path": str(self.model_path) if self.model_path.exists() else None,
            "contract_file_present": self.threshold_path.exists() or self._meta is not None,
            "architecture": "Dense Autoencoder (Input -> 32 -> 16 -> 8 -> 16 -> 32 -> Output)",
            "message": "Autoencoder ready for inference" if self.is_available() else "ANN Autoencoder artifact not found. Awaiting CERT dataset training."
        }


ann_anomaly_service = ANNAnomalyService()
