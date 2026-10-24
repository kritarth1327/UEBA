
"""Hybrid risk engine: fuses ML, ANN, CERT supervised and personal-baseline signals.

Every weight / threshold is PROVISIONAL until evaluated on labelled
data. See docs/risk_engine.md for normalisation, missing-component and
double-counting rules.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from app.services.model_interfaces import (
    ScoreResult,
    ScoreStatus,
    Scorer,
    safe_score,
)
from app.services.risk_config import RiskConfig, load_risk_config
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service
from app.services.cert_supervised_service import cert_supervised_service
from app.core.config import settings


def _component(
    name: str,
    status: str,
    normalized: Optional[float] = None,
    raw: Optional[float] = None,
    detail: Optional[str] = None,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "raw": raw,
        "normalized": normalized,
        "detail": detail,
        "model_version": version,
        "nominal_weight": None,
        "effective_weight": 0.0,
        "points": 0.0,
    }


class HybridRiskService:
    def __init__(self, config: Optional[RiskConfig] = None):
        self.model_name = "hybrid_risk_engine"
        self.version = "2.1.0"
        self._config = config

    @property
    def config(self) -> RiskConfig:
        if self._config is None:
            self._config = load_risk_config(settings.RISK_CONFIG_PATH)
        return self._config

    # ---- availability -----------------------------------------------------

    def is_available(self) -> bool:
        """True when all three model artifacts are available.

        Baseline scoring is data-dependent, not an artifact.
        This describes full model availability, not whether partial
        hybrid scoring can run.
        """
        return (
            ml_threat_service.is_available()
            and ann_anomaly_service.is_available()
            and cert_supervised_service.is_available()
        )

    def level_for(self, score: float) -> str:
        c = self.config
        return (
            "HIGH"
            if score >= c.high_threshold
            else "MEDIUM"
            if score >= c.medium_threshold
            else "LOW"
        )

    def severity_for(self, score: float) -> str:
        return (
            "CRITICAL"
            if score >= self.config.critical_threshold
            else self.level_for(score)
        )

    # ---- core fusion ------------------------------------------------------

    def fuse(
        self,
        components: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Fuse available normalized component scores using configured weights."""
        c = self.config

        # Reject unexpected component names rather than silently assigning
        # them a weight or ignoring a configuration error.
        unknown = {x["name"] for x in components} - set(c.weights)
        if unknown:
            raise ValueError(f"Unknown risk components: {sorted(unknown)}")

        ok = [
            x for x in components
            if x["status"] == "ok" and x["normalized"] is not None
        ]

        if not ok:
            return None

        total_w = sum(c.weights[x["name"]] for x in ok)
        if total_w <= 0:
            return None

        score = 0.0

        for component in components:
            component["nominal_weight"] = c.weights[component["name"]]

        for component in ok:
            effective_weight = c.weights[component["name"]] / total_w
            component["effective_weight"] = round(effective_weight, 4)
            component["points"] = round(
                100.0 * effective_weight * component["normalized"],
                2,
            )
            score += 100.0 * effective_weight * component["normalized"]

        capped = False

        # Preserve the existing protection when only baseline evidence exists.
        if (
            {x["name"] for x in ok} == {"baseline_deviation"}
            and score > c.baseline_only_cap
        ):
            score = c.baseline_only_cap
            capped = True

        score = round(min(100.0, max(0.0, score)), 1)

        return {
            "hybrid_risk_score": score,
            "risk_level": self.level_for(score),
            "components": components,
            "contributing_components": [x["name"] for x in ok],
            "unavailable_components": [
                x["name"] for x in components
                if x["status"] != "ok"
            ],
            "baseline_only_cap_applied": capped,
            "config_version": c.version,
            "config_provisional": c.provisional,
        }

    # ---- full assessment from features -----------------------------------

    def assess(
        self,
        features: Mapping[str, Optional[float]],
        baseline_result: Optional[Dict[str, Any]],
        ml_scorer: Optional[Scorer] = None,
        ann_scorer: Optional[Scorer] = None,
        cert_scorer: Optional[Scorer] = None,
    ) -> Optional[Dict[str, Any]]:
        """Assess feature data using ML, ANN, CERT and baseline signals."""
        c = self.config
        components: List[Dict[str, Any]] = []
        results: Dict[str, ScoreResult] = {}

        scorers = (
            ("ml_threat", ml_scorer or ml_threat_service),
            ("ann_anomaly", ann_scorer or ann_anomaly_service),
            ("cert_supervised", cert_scorer or cert_supervised_service),
        )

        for key, scorer in scorers:
            result = safe_score(scorer, features)
            results[key] = result
            components.append(
                _component(
                    key,
                    result.status.value,
                    result.score,
                    result.raw,
                    result.detail,
                    result.model_version,
                )
            )

        if baseline_result and baseline_result.get("status") == "ok":
            aggregate = baseline_result["aggregate_score"]
            components.append(
                _component(
                    "baseline_deviation",
                    "ok",
                    min(
                        1.0,
                        max(0.0, aggregate / c.baseline_saturation_z),
                    ),
                    aggregate,
                    (
                        f"top-{len(baseline_result['features'])} "
                        "robust z aggregate"
                    ),
                )
            )
        else:
            status = (baseline_result or {}).get(
                "status",
                "no_baseline",
            )
            components.append(
                _component(
                    "baseline_deviation",
                    "unavailable",
                    detail=status,
                )
            )

        fused = self.fuse(components)
        if fused is None:
            return None

        fused["contributing_factors"] = self._factors(
            features,
            baseline_result,
            results,
            components,
        )
        return fused

    def _factors(
        self,
        features,
        baseline_result,
        results,
        components,
    ) -> List[Dict[str, Any]]:
        """Deduplicate contributing features across available scoring sources."""
        by_feature: Dict[str, Dict[str, Any]] = {}

        baseline_weight = next(
            (
                x["effective_weight"]
                for x in components
                if x["name"] == "baseline_deviation"
            ),
            0.0,
        )

        if baseline_result and baseline_result.get("status") == "ok":
            for feature in baseline_result["features"]:
                if feature["z_score"] <= 0 or not feature["is_deviant"]:
                    continue

                by_feature[feature["feature"]] = {
                    "feature": feature["feature"],
                    "description": (
                        f"{feature['feature']} is "
                        f"{feature['z_score']:.1f} robust deviations "
                        "above this user's own baseline"
                    ),
                    "observed_value": feature["observed"],
                    "baseline_value": feature["baseline_center"],
                    "contribution_weight": round(
                        min(
                            1.0,
                            feature["z_score"] / self.config.baseline_saturation_z,
                        )
                        * baseline_weight,
                        4,
                    ),
                    "sources": ["baseline_deviation"],
                }

        for key, result in results.items():
            if result.status != ScoreStatus.OK:
                continue

            weight = next(
                x["effective_weight"]
                for x in components
                if x["name"] == key
            )

            for feature_name, share in result.contributions.items():
                entry = by_feature.setdefault(
                    feature_name,
                    {
                        "feature": feature_name,
                        "description": (
                            f"{feature_name} contributes to the {key} score"
                        ),
                        "observed_value": float(
                            features.get(feature_name) or 0.0
                        ),
                        "baseline_value": None,
                        "contribution_weight": 0.0,
                        "sources": [],
                    },
                )
                entry["contribution_weight"] = round(
                    entry["contribution_weight"] + share * weight,
                    4,
                )
                entry["sources"].append(key)

        return sorted(
            by_feature.values(),
            key=lambda entry: entry["contribution_weight"],
            reverse=True,
        )[:8]

    # ---- legacy entry point (kept for existing callers/tests) --------------

    def calculate_hybrid_risk(
        self,
        ml_score: Optional[float],
        ann_score: Optional[float],
        baseline_deviation: Optional[float],
        weights: Optional[Dict[str, float]] = None,
        cert_supervised_score: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Calculate risk from normalized scores and an aggregate baseline z.

        ML, ANN and CERT supervised scores must be in [0, 1].
        baseline_deviation is an aggregate robust z score.
        """
        config = self.config

        if weights:
            from dataclasses import replace

            config = replace(
                config,
                weights={**config.weights, **weights},
            ).validate()

        service = HybridRiskService(config)
        components = []

        for key, value in (
            ("ml_threat", ml_score),
            ("ann_anomaly", ann_score),
            ("cert_supervised", cert_supervised_score),
        ):
            components.append(
                _component(
                    key,
                    "ok",
                    min(1.0, max(0.0, value)),
                    value,
                )
                if value is not None
                else _component(key, "unavailable")
            )

        components.append(
            _component(
                "baseline_deviation",
                "ok",
                min(
                    1.0,
                    max(
                        0.0,
                        baseline_deviation / config.baseline_saturation_z,
                    ),
                ),
                baseline_deviation,
            )
            if baseline_deviation is not None
            else _component("baseline_deviation", "unavailable")
        )

        fused = service.fuse(components)
        if fused is None:
            return None

        fused["components"] = {
            component["name"]: component["normalized"]
            for component in components
            if component["status"] == "ok"
        }
        fused["component_details"] = components
        fused["weights_used"] = config.weights
        return fused

    def get_info(self) -> Dict[str, Any]:
        config = self.config
        all_models_available = self.is_available()

        return {
            "model_name": self.model_name,
            "version": self.version,
            "is_available": all_models_available,
            "fusion_strategy": (
                "Weighted mean of available normalized components, with "
                "weights re-normalized over available components; "
                "baseline-only evidence capped below HIGH"
            ),
            "config_version": config.version,
            "config_provisional": config.provisional,
            "weights": config.weights,
            "thresholds": {
                "medium": config.medium_threshold,
                "high": config.high_threshold,
                "critical": config.critical_threshold,
            },
            "message": (
                "All model components available"
                if all_models_available
                else (
                    "Partial scoring may be possible; one or more model "
                    "artifacts are unavailable."
                )
            ),
        }


hybrid_risk_service = HybridRiskService()
