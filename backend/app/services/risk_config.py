
"""Configurable risk weights/thresholds. ALL DEFAULTS ARE PROVISIONAL (not validated)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

COMPONENTS = (
    "ml_threat",
    "ann_anomaly",
    "baseline_deviation",
    "cert_supervised",
)


@dataclass(frozen=True)
class RiskConfig:
    version: str = "risk-config-provisional-v2-cert-supervised"
    provisional: bool = True
    weights: Dict[str, float] = field(default_factory=lambda: {
        "ml_threat": 0.3825,
        "ann_anomaly": 0.2975,
        "baseline_deviation": 0.17,
        "cert_supervised": 0.15,
    })
    medium_threshold: float = 40.0
    high_threshold: float = 70.0
    critical_threshold: float = 90.0
    baseline_saturation_z: float = 5.0
    # Baseline-only evidence is capped below HIGH until calibrated.
    baseline_only_cap: float = 69.0
    alert_min_level: str = "MEDIUM"

    def validate(self) -> "RiskConfig":
        if (
            set(self.weights) != set(COMPONENTS)
            or any(w < 0 for w in self.weights.values())
            or sum(self.weights.values()) <= 0
        ):
            raise ValueError(
                f"weights must cover {COMPONENTS}, be >= 0 and not all zero"
            )

        if not (
            0 < self.medium_threshold
            < self.high_threshold
            <= self.critical_threshold
            <= 100
        ):
            raise ValueError(
                "thresholds must satisfy 0 < medium < high <= critical <= 100"
            )

        if self.baseline_saturation_z <= 0:
            raise ValueError("baseline_saturation_z must be > 0")

        if self.alert_min_level not in ("MEDIUM", "HIGH"):
            raise ValueError("alert_min_level must be MEDIUM or HIGH")

        return self

    def as_dict(self) -> Dict:
        return asdict(self)


def load_risk_config(path: Optional[str] = None) -> RiskConfig:
    """Load provisional defaults, optionally overridden by a JSON file."""
    if not path:
        return RiskConfig().validate()

    data = json.loads(Path(path).read_text())
    base = RiskConfig()
    merged = {**asdict(base), **data}
    merged["weights"] = {
        **base.weights,
        **data.get("weights", {}),
    }

    return RiskConfig(**merged).validate()
