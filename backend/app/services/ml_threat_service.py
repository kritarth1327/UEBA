
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.pipeline.schema import SCHEMA_VERSION, FEATURE_NAMES, vectorize
from app.services.model_interfaces import ScoreResult


class MLThreatService:
    """Supervised ML threat-scoring service with a stable ScoreResult interface."""

    name = "ml_threat"

    def __init__(
        self,
        predictor: Optional[Callable[[List[float]], float]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ):
        self.model_name = "xgboost_threat_classifier"
        self.version = "1.0.0"
        self.model_path = (
            settings.MODELS_DIR / "xgboost_threat_classifier.json"
        )
        self.meta_path = (
            settings.MODELS_DIR / "xgboost_threat_classifier.meta.json"
        )

        self._model = None
        self._predictor = predictor
        self._meta = meta

        if predictor is None:
            self._load_model_if_exists()
            self._load_meta()

    def _load_model_if_exists(self) -> None:
        if not self.model_path.exists():
            self._model = None
            return

        try:
            import xgboost as xgb

            model = xgb.Booster()
            model.load_model(str(self.model_path))
            self._model = model
            logger.info("Loaded XGBoost model from %s", self.model_path)
        except Exception as exc:
            self._model = None
            logger.warning("Could not load XGBoost model: %s", exc)

    def _load_meta(self) -> None:
        if not self.meta_path.exists():
            if self._meta is None:
                self._meta = {}
            return

        try:
            with self.meta_path.open("r", encoding="utf-8") as file:
                self._meta = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load model metadata: %s", exc)
            if self._meta is None:
                self._meta = {}

    def is_available(self) -> bool:
        if not self._meta:
            return False

        # Injected predictors are used by tests and explicit integrations.
        if self._predictor is not None:
            return True

        # A previously loaded model is not available if its configured
        # artifact or metadata file is no longer present.
        return (
            self._model is not None
            and self.model_path.is_file()
            and self.meta_path.is_file()
        )

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": (self._meta or {}).get(
                "model_version", self.version
            ),
            "is_available": self.is_available(),
            "artifact_path": (
                str(self.model_path) if self.model_path.exists() else None
            ),
            "framework": "XGBoost",
            "contract_file_present": self.meta_path.exists()
            or bool(self._meta),
            "schema_version": (self._meta or {}).get("schema_version"),
            "feature_names": (self._meta or {}).get("feature_names", []),
            "training_dataset": (self._meta or {}).get("training_dataset"),
            "target": (self._meta or {}).get("target"),
            "target_warning": (self._meta or {}).get("target_warning"),
            "message": (
                "Model artifact loaded; evaluation target must be considered "
                "before interpreting scores."
                if self.is_available()
                else "Model artifact or metadata is unavailable."
            ),
        }

    def score(
        self, features: Mapping[str, Optional[float]]
    ) -> ScoreResult:
        """Return a normalized risk score through the shared ScoreResult API."""
        if not self.is_available():
            return ScoreResult.unavailable(
                "Supervised ML model or metadata is unavailable.",
                self.version,
            )

        meta = self._meta or {}

        if meta.get("schema_version") != SCHEMA_VERSION:
            return ScoreResult.error(
                "Model schema version does not match the current feature schema.",
                self.version,
            )

        feature_names = meta.get("feature_names", [])
        if not feature_names:
            return ScoreResult.error(
                "Model metadata does not contain feature_names.",
                self.version,
            )

        unknown = [
            name for name in feature_names if name not in FEATURE_NAMES
        ]
        if unknown:
            return ScoreResult.error(
                f"Model metadata contains unknown features: {unknown}",
                self.version,
            )

        try:
            vector = vectorize(features, feature_names)
            values = np.asarray(vector, dtype=np.float32)

            if np.isinf(values).any():
                return ScoreResult.error(
                    "Feature vector contains infinite values.",
                    self.version,
                )

            # XGBoost tree models support NaN as a missing-value marker.
            if self._predictor is not None:
                probability = float(self._predictor(vector))
            else:
                probability = self.predict_threat_score(vector)

            if not math.isfinite(probability):
                return ScoreResult.error(
                    "Model returned a non-finite prediction.",
                    self.version,
                )

            if not 0.0 <= probability <= 1.0:
                return ScoreResult.error(
                    "Model prediction is outside the expected [0, 1] range.",
                    self.version,
                )

            model_version = meta.get("model_version", self.version)
            return ScoreResult.ok(
                probability,
                probability,
                model_version,
            )

        except Exception as exc:
            logger.exception("XGBoost scoring failed")
            return ScoreResult.error(
                f"{type(exc).__name__}: {exc}",
                self.version,
            )

    def predict_threat_score(
        self, feature_vector: List[float]
    ) -> Optional[float]:
        """Run XGBoost inference, preserving native missing-value support."""
        if self._model is None:
            return None

        import xgboost as xgb

        values = np.asarray(
            feature_vector, dtype=np.float32
        ).reshape(1, -1)

        data = xgb.DMatrix(
            values,
            feature_names=self._meta["feature_names"],
        )
        prediction = self._model.predict(data)

        if len(prediction) == 0:
            return None

        return float(prediction[0])


ml_threat_service = MLThreatService()
