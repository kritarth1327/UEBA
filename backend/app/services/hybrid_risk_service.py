"""Hybrid risk engine: fuses ML, ANN and personal-baseline signals.

Every weight / threshold comes from RiskConfig and is PROVISIONAL until evaluated on labelled
data. See docs/risk_engine.md for normalisation, missing-component and double-counting rules.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from app.services.model_interfaces import ScoreResult, ScoreStatus, Scorer, safe_score
from app.services.risk_config import RiskConfig, load_risk_config
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service
from app.core.config import settings


def _component(name: str, status: str, normalized: Optional[float] = None, raw: Optional[float] = None,
               detail: Optional[str] = None, version: Optional[str] = None) -> Dict[str, Any]:
    return {"name": name, "status": status, "raw": raw, "normalized": normalized,
            "detail": detail, "model_version": version,
            "nominal_weight": None, "effective_weight": 0.0, "points": 0.0}


class HybridRiskService:
    def __init__(self, config: Optional[RiskConfig] = None):
        self.model_name = "hybrid_risk_engine"
        self.version = "2.0.0"
        self._config = config

    @property
    def config(self) -> RiskConfig:
        if self._config is None:
            self._config = load_risk_config(settings.RISK_CONFIG_PATH)
        return self._config

    # ---- availability -------------------------------------------------------------
    def is_available(self) -> bool:
        """Both trained models loaded (the baseline is data-dependent, not an artifact)."""
        return ml_threat_service.is_available() and ann_anomaly_service.is_available()

    def level_for(self, score: float) -> str:
        c = self.config
        return "HIGH" if score >= c.high_threshold else "MEDIUM" if score >= c.medium_threshold else "LOW"

    def severity_for(self, score: float) -> str:
        return "CRITICAL" if score >= self.config.critical_threshold else self.level_for(score)

    # ---- core fusion ----------------------------------------------------------------
    def fuse(self, components: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """components: dicts from `_component`. Returns None when no component produced a signal."""
        c = self.config
        ok = [x for x in components if x["status"] == "ok" and x["normalized"] is not None]
        if not ok:
            return None
        total_w = sum(c.weights[x["name"]] for x in ok)
        if total_w <= 0:
            return None
        score = 0.0
        for x in components:
            x["nominal_weight"] = c.weights[x["name"]]
        for x in ok:
            x["effective_weight"] = round(c.weights[x["name"]] / total_w, 4)
            x["points"] = round(100.0 * x["effective_weight"] * x["normalized"], 2)
            score += 100.0 * x["effective_weight"] * x["normalized"]
        capped = False
        if {x["name"] for x in ok} == {"baseline_deviation"} and score > c.baseline_only_cap:
            score, capped = c.baseline_only_cap, True
        score = round(min(100.0, max(0.0, score)), 1)
        return {
            "hybrid_risk_score": score,
            "risk_level": self.level_for(score),
            "components": components,
            "contributing_components": [x["name"] for x in ok],
            "unavailable_components": [x["name"] for x in components if x["status"] != "ok"],
            "baseline_only_cap_applied": capped,
            "config_version": c.version,
            "config_provisional": c.provisional,
        }

    # ---- full assessment from features ------------------------------------------------
    def assess(
        self,
        features: Mapping[str, Optional[float]],
        baseline_result: Optional[Dict[str, Any]],
        ml_scorer: Optional[Scorer] = None,
        ann_scorer: Optional[Scorer] = None,
    ) -> Optional[Dict[str, Any]]:
        """baseline_result: output of baseline_engine.score_deviation (or None)."""
        c = self.config
        comps: List[Dict[str, Any]] = []
        results: Dict[str, ScoreResult] = {}
        for key, scorer in (("ml_threat", ml_scorer or ml_threat_service),
                            ("ann_anomaly", ann_scorer or ann_anomaly_service)):
            r = safe_score(scorer, features)
            results[key] = r
            comps.append(_component(key, r.status.value, r.score, r.raw, r.detail, r.model_version))

        if baseline_result and baseline_result.get("status") == "ok":
            agg = baseline_result["aggregate_score"]
            comps.append(_component("baseline_deviation", "ok",
                                    min(1.0, max(0.0, agg / c.baseline_saturation_z)), agg,
                                    f"top-{len(baseline_result['features'])} robust z aggregate"))
        else:
            st = (baseline_result or {}).get("status", "no_baseline")
            comps.append(_component("baseline_deviation", "unavailable", detail=st))

        fused = self.fuse(comps)
        if fused is None:
            return None
        fused["contributing_factors"] = self._factors(features, baseline_result, results, comps)
        return fused

    def _factors(self, features, baseline_result, results, comps) -> List[Dict[str, Any]]:
        """One entry per feature (deduplicated across sources) so correlated signals that point at the
        same feature are listed once with every source that flagged it."""
        by_feature: Dict[str, Dict[str, Any]] = {}
        w_base = next((x["effective_weight"] for x in comps if x["name"] == "baseline_deviation"), 0.0)
        if baseline_result and baseline_result.get("status") == "ok":
            for f in baseline_result["features"]:
                if f["z_score"] <= 0 or not f["is_deviant"]:
                    continue
                by_feature[f["feature"]] = {
                    "feature": f["feature"],
                    "description": f"{f['feature']} is {f['z_score']:.1f} robust deviations above this user's own baseline",
                    "observed_value": f["observed"], "baseline_value": f["baseline_center"],
                    "contribution_weight": round(min(1.0, f["z_score"] / self.config.baseline_saturation_z) * w_base, 4),
                    "sources": ["baseline_deviation"],
                }
        for key, r in results.items():
            if r.status != ScoreStatus.OK:
                continue
            w = next(x["effective_weight"] for x in comps if x["name"] == key)
            for feat, share in r.contributions.items():
                entry = by_feature.setdefault(feat, {
                    "feature": feat, "description": f"{feat} contributes to the {key} score",
                    "observed_value": float(features.get(feat) or 0.0), "baseline_value": None,
                    "contribution_weight": 0.0, "sources": []})
                entry["contribution_weight"] = round(entry["contribution_weight"] + share * w, 4)
                entry["sources"].append(key)
        return sorted(by_feature.values(), key=lambda e: e["contribution_weight"], reverse=True)[:8]

    # ---- legacy entry point (kept for existing callers/tests) ---------------------------
    def calculate_hybrid_risk(
        self,
        ml_score: Optional[float],
        ann_score: Optional[float],
        baseline_deviation: Optional[float],
        weights: Optional[Dict[str, float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """ml_score / ann_score already in [0,1]; baseline_deviation is an aggregate robust z."""
        cfg = self.config
        if weights:
            from dataclasses import replace
            cfg = replace(cfg, weights={**cfg.weights, **weights}).validate()
        svc = HybridRiskService(cfg)
        comps = []
        for key, v in (("ml_threat", ml_score), ("ann_anomaly", ann_score)):
            comps.append(_component(key, "ok", min(1.0, max(0.0, v)), v) if v is not None
                         else _component(key, "unavailable"))
        comps.append(_component("baseline_deviation", "ok",
                                min(1.0, max(0.0, baseline_deviation / cfg.baseline_saturation_z)), baseline_deviation)
                     if baseline_deviation is not None else _component("baseline_deviation", "unavailable"))
        fused = svc.fuse(comps)
        if fused is None:
            return None
        fused["components"] = {x["name"]: x["normalized"] for x in comps if x["status"] == "ok"}
        fused["component_details"] = comps
        fused["weights_used"] = cfg.weights
        return fused

    def get_info(self) -> Dict[str, Any]:
        c = self.config
        return {
            "model_name": self.model_name,
            "version": self.version,
            "is_available": self.is_available(),
            "fusion_strategy": "Weighted mean of available normalised components, weights re-normalised over "
                               "available components; baseline-only evidence capped below HIGH",
            "config_version": c.version,
            "config_provisional": c.provisional,
            "weights": c.weights,
            "thresholds": {"medium": c.medium_threshold, "high": c.high_threshold, "critical": c.critical_threshold},
            "message": ("Hybrid risk engine active (all components)" if self.is_available()
                        else "Hybrid engine running on available components only; trained models not yet delivered."),
        }


hybrid_risk_service = HybridRiskService()
