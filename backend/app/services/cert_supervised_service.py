"""CERT r4.2 supervised inference adapter.

Uses the separately trained CERT XGBoost model and the existing ScoreResult
contract. This service is intentionally separate from MLThreatService.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from app.core.logging import logger
from app.services.model_interfaces import ScoreResult


class CERTSupervisedService:
    name = "cert_supervised"

    FEATURE_NAMES = [
        "logon_count",
        "after_hours_logons",
        "file_copied_removable",
        "email_count",
        "email_external_count",
        "email_attachment_count",
        "email_total_bytes",
        "http_request_count",
        "http_after_hours_count",
        "removable_device_events",
        "after_hours_event_count",
    ]

    def __init__(self, artifact_dir: Optional[Path] = None):
        self.artifact_dir = artifact_dir or (
            Path(__file__).resolve().parents[2]
            / "artifacts"
            / "cert_supervised"
        )
        self.model_path = self.artifact_dir / "xgboost.joblib"
        self.metrics_path = self.artifact_dir / "metrics.json"
        self.model = None
        self.metadata = {}
        self.version = "cert-r42-xgboost-v1"

        self._load()

    def _load(self) -> None:
        if not self.model_path.is_file():
            logger.warning("CERT supervised artifact not found: %s", self.model_path)
            return

        try:
            import joblib

            model = joblib.load(self.model_path)
            if not hasattr(model, "predict_proba"):
                raise TypeError("CERT artifact does not expose predict_proba")

            metadata = {}
            if self.metrics_path.is_file():
                metadata = json.loads(
                    self.metrics_path.read_text(encoding="utf-8")
                )
            model_features = (
                metadata.get("metrics", {})
                .get("xgboost", {})
                .get("features", [])
            )
            if model_features and model_features != self.FEATURE_NAMES:
                raise ValueError(
                    "CERT artifact feature order does not match the inference contract"
                )

            self.model = model
            self.metadata = metadata
            logger.info("Loaded CERT supervised model from %s", self.model_path)
        except (OSError, TypeError, ValueError, ImportError, json.JSONDecodeError) as exc:
            self.model = None
            self.metadata = {}
            logger.exception("Could not load CERT supervised model: %s", exc)

    def is_available(self) -> bool:
        return self.model is not None

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "model_type": "XGBoost",
            "model_path": str(self.model_path),
            "available": self.is_available(),
            "feature_names": list(self.FEATURE_NAMES),
            "version": self.version,
            "label_caveat": (
                "CERT incident-window proxy labels; outside-window rows "
                "are provisional negatives, not verified benign activity."
            ),
        }

    def score(
        self, features: Mapping[str, Optional[float]]
    ) -> ScoreResult:
        if not self.is_available():
            return ScoreResult.unavailable(
                f"CERT XGBoost artifact not available: {self.model_path}",
                self.version,
            )

        try:
            values = []
            for name in self.FEATURE_NAMES:
                value = features.get(name)

                if value is None:
                    return ScoreResult.error(
                        f"Required CERT feature is missing: {name}",
                        self.version,
                    )

                number = float(value)
                if not math.isfinite(number):
                    return ScoreResult.error(
                        f"Feature {name} must be finite",
                        self.version,
                    )

                values.append(number)

            vector = pd.DataFrame([values], columns=self.FEATURE_NAMES, dtype=np.float32)
            probability = float(self.model.predict_proba(vector)[0, 1])

            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                return ScoreResult.error(
                    f"Invalid model probability: {probability!r}",
                    self.version,
                )

            return ScoreResult.ok(
                score=probability,
                raw=probability,
                version=self.version,
            )

        except Exception as exc:
            return ScoreResult.error(
                f"{type(exc).__name__}: {exc}",
                self.version,
            )


cert_supervised_service = CERTSupervisedService()
