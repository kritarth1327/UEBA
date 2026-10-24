import json
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import torch
from torch import nn

from app.core.config import settings
from app.core.logging import logger


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


class DenseAutoencoder(nn.Module):
    """Must match the architecture used by scripts/train_autoencoder.py."""

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

    def __init__(self):
        self.model_name = "dense_autoencoder"
        self.version = "1.0.0"

        self.model_path = settings.MODELS_DIR / "dense_autoencoder.pt"
        self.scaler_path = settings.MODELS_DIR / "autoencoder_scaler.joblib"
        self.threshold_path = settings.MODELS_DIR / "autoencoder_threshold.json"
        self.metadata_path = settings.MODELS_DIR / "autoencoder_metadata.json"

        self._model = None
        self._scaler = None
        self._threshold = None
        self._device = torch.device("cpu")
        self._load_model_if_exists()

    def _load_model_if_exists(self) -> None:
        """Load all required artifacts; leave service unavailable on failure."""
        try:
            required_paths = [
                self.model_path,
                self.scaler_path,
                self.threshold_path,
            ]
            missing = [str(path) for path in required_paths if not path.exists()]

            if missing:
                logger.warning(
                    "ANN unavailable; missing artifacts: " + ", ".join(missing)
                )
                return

            with open(self.threshold_path, "r", encoding="utf-8") as file:
                threshold_data = json.load(file)

            threshold = float(threshold_data["threshold"])
            if not np.isfinite(threshold) or threshold < 0:
                raise ValueError("Saved anomaly threshold is invalid.")

            scaler = joblib.load(self.scaler_path)

            if not hasattr(scaler, "n_features_in_"):
                raise ValueError("Saved scaler has no feature-count metadata.")

            if int(scaler.n_features_in_) != len(FEATURES):
                raise ValueError(
                    f"Scaler expects {scaler.n_features_in_} features; "
                    f"service expects {len(FEATURES)}."
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
            self._threshold = threshold

            logger.info(
                "Loaded ANN autoencoder, scaler, and threshold "
                f"({self._threshold:.8f})"
            )

        except Exception as exc:
            self._model = None
            self._scaler = None
            self._threshold = None
            logger.exception(f"Failed to load ANN artifacts: {exc}")

    def is_available(self) -> bool:
        return (
            self._model is not None
            and self._scaler is not None
            and self._threshold is not None
        )

    def predict(self, feature_vector: List[float]) -> Optional[Dict[str, Any]]:
        """
        Score one profile in the same preprocessing space as training.

        Input order must match FEATURES. Values must be raw, nonnegative
        behavior counts/durations, not pre-scaled or log-transformed values.
        """
        if not self.is_available():
            return None

        try:
            values = np.asarray(feature_vector, dtype=np.float64)

            if values.ndim != 1 or values.size != len(FEATURES):
                raise ValueError(
                    f"Expected {len(FEATURES)} features in this order: {FEATURES}"
                )

            if not np.isfinite(values).all():
                raise ValueError("Features must all be finite numbers.")

            if (values < 0).any():
                raise ValueError("Behavior counts and durations must be nonnegative.")

            # Exactly match training: log1p first, then fitted StandardScaler.
            transformed = np.log1p(values.reshape(1, -1))
            scaled = self._scaler.transform(transformed).astype(np.float32)

            tensor_in = torch.from_numpy(scaled)

            with torch.no_grad():
                reconstruction = self._model(tensor_in)
                error = torch.mean((tensor_in - reconstruction) ** 2).item()

            if not np.isfinite(error):
                raise ValueError("Model returned a non-finite reconstruction error.")

            return {
                "model_name": self.model_name,
                "model_version": self.version,
                "ann_anomaly_score": float(error),
                "threshold": float(self._threshold),
                "is_anomaly_candidate": bool(error > self._threshold),
                "features_used": FEATURES.copy(),
                "interpretation": (
                    "Anomaly candidate: reconstruction error exceeds the "
                    "validation threshold. This is not proof of malicious activity."
                    if error > self._threshold
                    else "Reconstruction error is at or below the validation threshold."
                ),
            }

        except (TypeError, ValueError) as exc:
            logger.warning(f"ANN inference input error: {exc}")
            raise
        except Exception as exc:
            logger.exception(f"ANN inference failed: {exc}")
            raise RuntimeError("ANN inference failed.") from exc

    def predict_reconstruction_error(
        self, feature_vector: List[float]
    ) -> Optional[float]:
        """Backward-compatible interface returning only the reconstruction error."""
        result = self.predict(feature_vector)
        return None if result is None else result["ann_anomaly_score"]

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
            "feature_count": len(FEATURES),
            "features": FEATURES.copy(),
            "architecture": (
                "Dense Autoencoder (Input -> 32 -> 16 -> 8 -> 16 -> 32 -> Output)"
            ),
            "preprocessing": ["log1p", "saved StandardScaler"],
            "message": (
                "Autoencoder, scaler, and threshold loaded; inference available."
                if self.is_available()
                else "ANN unavailable. Check model, scaler, and threshold artifacts."
            ),
            "threshold_note": (
                "The threshold is the 99th percentile of validation reconstruction "
                "errors. Above-threshold profiles are anomaly candidates, not "
                "confirmed security incidents."
            ),
        }


ann_anomaly_service = ANNAnomalyService()
