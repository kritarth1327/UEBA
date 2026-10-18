from typing import Optional, Dict, Any, List
from app.services.ml_threat_service import ml_threat_service
from app.services.ann_anomaly_service import ann_anomaly_service


class HybridRiskService:
    """Combines Supervised ML Threat Score, ANN Anomaly Score, and Baseline Deviation Signal."""

    def __init__(self):
        self.model_name = "hybrid_risk_engine"
        self.version = "1.0.0"

    def is_available(self) -> bool:
        """The hybrid risk engine requires both detection models or real evaluated pipelines."""
        return ml_threat_service.is_available() and ann_anomaly_service.is_available()

    def calculate_hybrid_risk(
        self,
        ml_score: Optional[float],
        ann_score: Optional[float],
        baseline_deviation: Optional[float],
        weights: Optional[Dict[str, float]] = None
    ) -> Optional[Dict[str, Any]]:
        """Calculates combined hybrid risk score [0-100] and risk level.
        Returns None if component signals are unavailable.
        """
        if ml_score is None and ann_score is None and baseline_deviation is None:
            return None

        # Calibrated default weights (subject to experimental validation on CERT data)
        w = weights or {
            "ml_threat": 0.45,
            "ann_anomaly": 0.35,
            "baseline_deviation": 0.20
        }

        components = {}
        total_weight = 0.0
        weighted_sum = 0.0

        if ml_score is not None:
            components["ml_threat"] = ml_score
            weighted_sum += ml_score * w["ml_threat"]
            total_weight += w["ml_threat"]

        if ann_score is not None:
            components["ann_anomaly"] = ann_score
            weighted_sum += ann_score * w["ann_anomaly"]
            total_weight += w["ann_anomaly"]

        if baseline_deviation is not None:
            # Normalize deviation z-score to [0, 1] scale using sigmoid or clipped scaling
            norm_baseline = min(1.0, max(0.0, baseline_deviation / 5.0))
            components["baseline_deviation"] = norm_baseline
            weighted_sum += norm_baseline * w["baseline_deviation"]
            total_weight += w["baseline_deviation"]

        if total_weight == 0.0:
            return None

        final_normalized_score = weighted_sum / total_weight
        risk_score = round(final_normalized_score * 100.0, 1)

        # Categorize risk level
        if risk_score >= 70.0:
            risk_level = "HIGH"
        elif risk_score >= 40.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "hybrid_risk_score": risk_score,
            "risk_level": risk_level,
            "components": components,
            "weights_used": w
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "is_available": self.is_available(),
            "fusion_strategy": "Calibrated multi-signal weighted sum (ML Threat + ANN Reconstruction Error + Baseline Deviation)",
            "message": "Hybrid risk engine active" if self.is_available() else "Awaiting model training on CERT dataset."
        }


hybrid_risk_service = HybridRiskService()
