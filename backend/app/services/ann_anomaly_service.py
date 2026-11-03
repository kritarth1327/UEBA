
from __future__ import annotations

import json
import math
from typing import Any, Callable, Dict, List, Mapping, Optional

import joblib
import numpy as np

try:
    import torch
    from torch import nn
except ImportError:  # ANN remains unavailable without affecting other services.
    torch = None
    nn = None

from app.core.config import settings
from app.core.logging import logger
from app.pipeline.schema import SCHEMA_VERSION, FEATURE_NAMES
from app.services.model_interfaces import ScoreResult


FEATURES = [
    "logon_count",
    "after_hours_logons",
    "file_copied_removable",
    "email_count",
    "email_external_count",
    "email_attachment_count",
    "http_request_count",
    "http_after_hours_count",
    "removable_device_events",
    "total_session_duration",
]
ANN_DURATION_POLICY = "zero"
ANN_DURATION_ASSUMPTION = (
    "Missing total_session_duration is explicitly replaced with zero before "
    "log1p preprocessing; this is a candidate assumption, not historical behavior."
)


if nn is not None:

    class DenseAutoencoder(nn.Module):
        """Autoencoder architecture matching the trained model."""

        def __init__(self, input_dim: int):
            super().__init__()

            self.encoder = nn.Sequential(
                nn.Linear(input_dim, 32),
                nn.ReLU(),
                nn.Linear(32, 16),
                nn.ReLU(),
                nn.Linear(16, 8),
                nn.ReLU(),
            )

            self.decoder = nn.Sequential(
                nn.Linear(8, 16),
                nn.ReLU(),
                nn.Linear(16, 32),
                nn.ReLU(),
                nn.Linear(32, input_dim),
            )

        def forward(self, x):
            return self.decoder(self.encoder(x))


class ANNAnomalyService:
    """Loads a trained autoencoder and scores daily behavior profiles."""

    name = "ann_anomaly"

    def __init__(
        self,
        error_fn: Optional[Callable[[List[float]], float]] = None,
        meta: Optional[Mapping[str, Any]] = None,
    ):
        self.model_name = "dense_autoencoder"
        self.version = "1.0.0"

        self.model_path = settings.MODELS_DIR / "dense_autoencoder.pt"
        self.scaler_path = settings.MODELS_DIR / "autoencoder_scaler.joblib"
        self.threshold_path = settings.MODELS_DIR / "autoencoder_threshold.json"
        self.metadata_path = settings.MODELS_DIR / "autoencoder_metadata.json"

        self._model = None
        self._scaler = None
        self._threshold: Optional[float] = None
        self._error_fn = error_fn
        self._meta = dict(meta or {})
        self._preprocessing = dict(self._meta.get("preprocessing", {}))
        self._features = list(
            self._meta.get("feature_names", self._meta.get("features", FEATURES))
        )

        self.version = str(
            self._meta.get("model_version", self._meta.get("version", self.version))
        )

        if self._meta.get("threshold") is not None:
            try:
                threshold = float(self._meta["threshold"])
                if math.isfinite(threshold) and threshold >= 0:
                    self._threshold = threshold
            except (TypeError, ValueError):
                self._threshold = None

        if self._error_fn is not None:
            return

        self._load_model_if_exists()

    def _load_model_if_exists(self) -> None:
        """Load the trained model, scaler, and threshold."""
        try:
            if torch is None:
                logger.warning(
                    "ANN unavailable; PyTorch is not installed."
                )
                return

            required_paths = [
                self.model_path,
                self.scaler_path,
                self.threshold_path,
                self.metadata_path,
            ]
            missing = [
                str(path) for path in required_paths if not path.is_file()
            ]

            if missing:
                logger.warning(
                    "ANN unavailable; missing artifacts: " + ", ".join(missing)
                )
                return

            with self.metadata_path.open("r", encoding="utf-8") as file:
                artifact_meta = json.load(file)
            artifact_features = artifact_meta.get(
                "feature_names", artifact_meta.get("features")
            )
            if artifact_meta.get("schema_version") not in (None, SCHEMA_VERSION):
                raise ValueError(
                    "ANN artifact schema version does not match the current feature schema."
                )
            if artifact_features != FEATURES:
                raise ValueError(
                    "ANN artifact feature order does not match the inference contract."
                )
            self._meta = artifact_meta
            self._features = list(artifact_features)
            self._preprocessing = dict(artifact_meta.get("preprocessing", {}))
            self.version = str(
                artifact_meta.get("model_version", artifact_meta.get("version", self.version))
            )

            with self.threshold_path.open("r", encoding="utf-8") as file:
                threshold_data = json.load(file)

            threshold = float(threshold_data["threshold"])
            if not math.isfinite(threshold) or threshold < 0:
                raise ValueError("Saved anomaly threshold is invalid.")

            scaler = joblib.load(self.scaler_path)

            if getattr(scaler, "n_features_in_", None) != len(FEATURES):
                raise ValueError(
                    f"Scaler must expect exactly {len(FEATURES)} features."
                )

            model = DenseAutoencoder(input_dim=len(FEATURES))
            state_dict = torch.load(
                str(self.model_path),
                map_location="cpu",
                weights_only=True,
            )
            model.load_state_dict(state_dict)
            model.eval()

            self._model = model
            self._scaler = scaler

            if self._threshold is None:
                self._threshold = threshold

            logger.info(
                "Loaded ANN model, scaler, and threshold "
                f"({self._threshold:.8f})"
            )

        except Exception as exc:
            self._model = None
            self._scaler = None
            self._threshold = None
            logger.exception(f"Failed to load ANN artifacts: {exc}")

    def is_available(self) -> bool:
        if self._error_fn is not None:
            return self._threshold is not None

        return (
            self._model is not None
            and self._scaler is not None
            and self._threshold is not None
        )

    def _validate_schema(self) -> Optional[str]:
        """Validate ANN features against the shared pipeline schema."""
        unknown = [
            name for name in self._features if name not in FEATURE_NAMES
        ]
        if unknown:
            return f"ANN features are outside the shared schema: {unknown}"

        if len(self._features) != len(set(self._features)):
            return "ANN feature list contains duplicate names."

        if self._error_fn is None and len(self._features) != len(FEATURES):
            return "ANN feature count does not match the trained model."
        if self._error_fn is None and self._features != FEATURES:
            return "ANN feature order does not match the trained model."

        metadata_schema = self._meta.get("schema_version")
        if metadata_schema is not None and metadata_schema != SCHEMA_VERSION:
            return (
                f"Schema version mismatch: model={metadata_schema}, "
                f"pipeline={SCHEMA_VERSION}"
            )

        return None

    def _preprocess(self, feature_vector: List[float]) -> np.ndarray:
        """Apply the preprocessing expected by the trained model."""
        values = np.asarray(feature_vector, dtype=np.float64)

        if values.ndim != 1 or values.size != len(self._features):
            raise ValueError(
                f"Expected {len(self._features)} features in this order: "
                f"{self._features}"
            )

        if not np.isfinite(values).all():
            raise ValueError("Features must all be finite numbers.")

        if (values < 0).any():
            raise ValueError(
                "Behavior counts and durations must be nonnegative."
            )

        if self._error_fn is not None:
            transformed = values.copy()

            if self._preprocessing.get("log1p", True):
                transformed = np.log1p(transformed)

            mean = self._preprocessing.get("mean")
            scale = self._preprocessing.get("scale")

            if mean is not None or scale is not None:
                if mean is None or scale is None:
                    raise ValueError(
                        "Both preprocessing mean and scale are required."
                    )

                mean = np.asarray(mean, dtype=np.float64)
                scale = np.asarray(scale, dtype=np.float64)

                if mean.size != values.size or scale.size != values.size:
                    raise ValueError(
                        "Preprocessing dimensions do not match features."
                    )

                if (
                    not np.isfinite(mean).all()
                    or not np.isfinite(scale).all()
                    or (scale == 0).any()
                ):
                    raise ValueError("Preprocessing mean/scale are invalid.")

                transformed = (transformed - mean) / scale

            return transformed

        transformed = np.log1p(values.reshape(1, -1))

        if self._scaler is None:
            raise RuntimeError("ANN scaler is unavailable.")

        return self._scaler.transform(transformed)[0].astype(np.float32)

    def predict(
        self,
        feature_vector: List[float],
    ) -> Optional[Dict[str, Any]]:
        """Return reconstruction error and a bounded anomaly score."""
        if not self.is_available():
            return None

        try:
            transformed = self._preprocess(feature_vector)

            if self._error_fn is not None:
                error = float(self._error_fn(transformed.tolist()))
            else:
                tensor_in = torch.from_numpy(
                    transformed.astype(np.float32)
                ).reshape(1, -1)

                with torch.no_grad():
                    reconstruction = self._model(tensor_in)
                    error = float(
                        torch.mean((tensor_in - reconstruction) ** 2).item()
                    )

            if not math.isfinite(error) or error < 0:
                raise ValueError("Invalid reconstruction error.")

            threshold = float(self._threshold)

            if threshold == 0:
                normalized_score = 1.0 if error > 0 else 0.0
            else:
                normalized_score = error / (error + threshold)

            is_candidate = error > threshold

            return {
                "model_name": self.model_name,
                "model_version": self.version,
                "ann_anomaly_score": error,
                "reconstruction_error": error,
                "normalized_score": float(normalized_score),
                "threshold": threshold,
                "is_anomaly_candidate": is_candidate,
                "features_used": self._features.copy(),
                "interpretation": (
                    "Anomaly candidate; not proof of malicious activity."
                    if is_candidate
                    else (
                        "Reconstruction error is at or below "
                        "the validation threshold."
                    )
                ),
            }

        except (TypeError, ValueError):
            raise
        except Exception as exc:
            logger.exception(f"ANN inference failed: {exc}")
            raise RuntimeError("ANN inference failed.") from exc

    def score(
        self,
        features: Mapping[str, Optional[float]],
    ) -> ScoreResult:
        """Adapt ANN inference to the shared risk-scoring interface."""
        if not self.is_available():
            return ScoreResult.unavailable(
                "ANN model or required artifacts are unavailable.",
                self.version,
            )

        schema_error = self._validate_schema()
        if schema_error:
            return ScoreResult.error(schema_error, self.version)

        try:
            values = []

            for name in self._features:
                value = features.get(name)

                if value is None:
                    if name == "total_session_duration" and ANN_DURATION_POLICY == "zero":
                        value = 0.0
                    else:
                        return ScoreResult.unavailable(
                            f"Required ANN feature is unavailable: {name}",
                            self.version,
                        )

                numeric_value = float(value)

                if (
                    name == "total_session_duration"
                    and math.isnan(numeric_value)
                    and ANN_DURATION_POLICY == "zero"
                ):
                    numeric_value = 0.0

                if not math.isfinite(numeric_value):
                    return ScoreResult.unavailable(
                        f"Required ANN feature is unavailable: {name}",
                        self.version,
                    )

                if numeric_value < 0:
                    return ScoreResult.error(
                        f"ANN feature must be nonnegative: {name}",
                        self.version,
                    )

                values.append(numeric_value)

            result = self.predict(values)

            if result is None:
                return ScoreResult.unavailable(
                    "ANN model is unavailable.",
                    self.version,
                )

            return ScoreResult.ok(
                float(result["normalized_score"]),
                float(result["reconstruction_error"]),
                self.version,
            )

        except (TypeError, ValueError, KeyError) as exc:
            return ScoreResult.error(
                f"{type(exc).__name__}: {exc}",
                self.version,
            )
        except Exception as exc:
            logger.exception("ANN scoring failed")
            return ScoreResult.error(
                f"{type(exc).__name__}: {exc}",
                self.version,
            )

    def predict_reconstruction_error(
        self,
        feature_vector: List[float],
    ) -> Optional[float]:
        """Backward-compatible interface for raw reconstruction error."""
        result = self.predict(feature_vector)
        return None if result is None else result["reconstruction_error"]

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "is_available": self.is_available(),
            "artifact_path": (
                str(self.model_path) if self.model_path.exists() else None
            ),
            "scaler_path": (
                str(self.scaler_path) if self.scaler_path.exists() else None
            ),
            "threshold": self._threshold,
            "feature_count": len(self._features),
            "features": self._features.copy(),
            "architecture": (
                "Dense Autoencoder "
                "(Input -> 32 -> 16 -> 8 -> 16 -> 32 -> Output)"
            ),
            "preprocessing": (
                self._preprocessing
                if self._error_fn is not None
                else {
                    "steps": ["log1p", "saved StandardScaler"],
                    "total_session_duration_policy": ANN_DURATION_POLICY,
                    "total_session_duration_assumption": ANN_DURATION_ASSUMPTION,
                }
            ),
            "message": (
                "Autoencoder, scaler, and threshold loaded; inference available."
                if self.is_available()
                else "ANN unavailable. Check model, scaler, and threshold artifacts."
            ),
            "threshold_note": (
                "Above-threshold profiles are anomaly candidates, "
                "not confirmed incidents."
            ),
        }


ann_anomaly_service = ANNAnomalyService()
