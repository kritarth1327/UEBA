"""Inference service for the isolated experimental SPEDIA autoencoder."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional

import joblib
import numpy as np

try:
    import torch
    from torch import nn
except ImportError:  # pragma: no cover - availability is reported at runtime.
    torch = None
    nn = None

from app.core.logging import logger
from app.core.config import settings
from app.pipeline.schema import FEATURE_NAMES, SCHEMA_VERSION
from app.services.model_interfaces import ScoreResult


FEATURES = [
    "logon_count",
    "after_hours_logons",
    "failed_logon_count",
    "file_access_count",
    "file_integrity_event_count",
    "email_count",
    "email_external_count",
    "email_attachment_count",
    "email_total_bytes",
    "http_request_count",
    "http_after_hours_count",
    "removable_device_events",
    "command_exec_count",
    "after_hours_event_count",
]


if nn is not None:

    class SpediaAutoencoder(nn.Module):
        def __init__(self, input_dim: int = len(FEATURES)):
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, 8),
                nn.ReLU(),
                nn.Linear(8, 4),
                nn.ReLU(),
            )
            self.decoder = nn.Sequential(
                nn.Linear(4, 8),
                nn.ReLU(),
                nn.Linear(8, input_dim),
            )

        def forward(self, x):
            return self.decoder(self.encoder(x))


class SpediaANNAnomalyService:
    """Loads and scores the separate SPEDIA ANN artifact bundle."""

    name = "spedia_ann_anomaly"

    def __init__(self, artifact_dir: Optional[Path] = None):
        self.artifact_dir = artifact_dir or (
            settings.MODELS_DIR / "spedia_dense_autoencoder"
        )
        self.model_name = "spedia_dense_autoencoder"
        self.version = "spedia-experimental-1"
        self.model_path = self.artifact_dir / "dense_autoencoder.pt"
        self.scaler_path = self.artifact_dir / "autoencoder_scaler.joblib"
        self.threshold_path = self.artifact_dir / "autoencoder_threshold.json"
        self.metadata_path = self.artifact_dir / "autoencoder_metadata.json"
        self._model = None
        self._scaler = None
        self._threshold: Optional[float] = None
        self._features = list(FEATURES)
        self._load_error: Optional[str] = None
        self._load()

    def _fail_load(self, message: str, exc: Optional[Exception] = None) -> None:
        self._model = None
        self._scaler = None
        self._threshold = None
        self._load_error = message
        if exc is None:
            logger.error(message)
        else:
            logger.exception(message)

    def _load(self) -> None:
        required = (
            self.model_path,
            self.scaler_path,
            self.threshold_path,
            self.metadata_path,
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            self._fail_load(
                "SPEDIA ANN artifacts are missing: " + ", ".join(missing)
            )
            return
        if torch is None or nn is None:
            self._fail_load("SPEDIA ANN unavailable; PyTorch is not installed.")
            return

        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            features = metadata.get("feature_names")
            if features != FEATURES:
                raise ValueError(
                    "SPEDIA ANN metadata feature order does not match the 14-feature contract."
                )
            if metadata.get("schema_version") not in (None, SCHEMA_VERSION):
                raise ValueError("SPEDIA ANN schema version does not match the pipeline.")
            if metadata.get("dataset") != "spedia":
                raise ValueError("SPEDIA ANN metadata dataset must be 'spedia'.")
            if metadata.get("architecture") != [14, 8, 4, 8, 14]:
                raise ValueError("SPEDIA ANN architecture does not match the trained model.")
            preprocessing = metadata.get("preprocessing", {})
            if preprocessing.get("transformation") != "numpy.log1p":
                raise ValueError("SPEDIA ANN preprocessing must use numpy.log1p.")
            if preprocessing.get("scaler") != "StandardScaler":
                raise ValueError("SPEDIA ANN preprocessing must use StandardScaler.")

            threshold_data = json.loads(
                self.threshold_path.read_text(encoding="utf-8")
            )
            threshold = float(threshold_data["threshold"])
            if not math.isfinite(threshold) or threshold < 0:
                raise ValueError("SPEDIA ANN threshold is invalid.")

            scaler = joblib.load(self.scaler_path)
            if getattr(scaler, "n_features_in_", None) != len(FEATURES):
                raise ValueError("SPEDIA ANN scaler must expect exactly 14 features.")

            model = SpediaAutoencoder()
            state_dict = torch.load(
                str(self.model_path), map_location="cpu", weights_only=True
            )
            model.load_state_dict(state_dict)
            model.eval()

            self._model = model
            self._scaler = scaler
            self._threshold = threshold
            self._features = list(features)
            self.version = str(
                metadata.get("model_version", self.version)
            )
        except Exception as exc:
            self._fail_load(f"Failed to load SPEDIA ANN artifacts: {exc}", exc)

    def is_available(self) -> bool:
        return (
            self._model is not None
            and self._scaler is not None
            and self._threshold is not None
        )

    def _invalid_features(self, features: Mapping[str, Optional[float]]) -> Optional[str]:
        for name in self._features:
            value = features.get(name)
            if value is None:
                return f"Required SPEDIA ANN feature is unavailable: {name}"
            try:
                number = float(value)
            except (TypeError, ValueError):
                return f"Required SPEDIA ANN feature is invalid: {name}"
            if not math.isfinite(number) or number < 0:
                return f"Required SPEDIA ANN feature is invalid: {name}"
        return None

    def score(self, features: Mapping[str, Optional[float]]) -> ScoreResult:
        invalid = self._invalid_features(features)
        if invalid:
            return ScoreResult.unavailable(invalid, self.version)
        if self._load_error is not None:
            return ScoreResult.error(self._load_error, self.version)
        if not self.is_available():
            return ScoreResult.error("SPEDIA ANN is unavailable after loading.", self.version)

        try:
            values = np.asarray(
                [float(features[name]) for name in self._features],
                dtype=np.float64,
            )
            transformed = self._scaler.transform(
                np.log1p(values.reshape(1, -1))
            ).astype(np.float32)
            tensor = torch.from_numpy(transformed)
            with torch.no_grad():
                reconstruction = self._model(tensor)
                error = float(torch.mean((tensor - reconstruction) ** 2).item())
            if not math.isfinite(error) or error < 0:
                return ScoreResult.error(
                    "SPEDIA ANN produced an invalid reconstruction error.",
                    self.version,
                )
            threshold = float(self._threshold)
            normalized = (
                1.0 if threshold == 0 and error > 0
                else 0.0 if threshold == 0
                else error / (error + threshold)
            )
            return ScoreResult.ok(
                normalized,
                error,
                self.version,
            )
        except Exception as exc:
            logger.exception("SPEDIA ANN inference failed: %s", exc)
            return ScoreResult.error(
                f"{type(exc).__name__}: {exc}",
                self.version,
            )


spedia_ann_anomaly_service = SpediaANNAnomalyService()
