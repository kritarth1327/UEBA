import json
import pytest

from app.pipeline.schema import SCHEMA_VERSION
from app.services.ann_anomaly_service import ANNAnomalyService
from app.services.hybrid_risk_service import HybridRiskService
from app.services.ml_threat_service import MLThreatService
from app.services.model_interfaces import ScoreResult, ScoreStatus, safe_score
from app.services.risk_config import RiskConfig, load_risk_config

# ---- TEMPORARY STUBS: stand-ins for Rhythm's classifier and Waasif's autoencoder (not yet delivered).
# They test the integration contract only; they say nothing about model quality.


class StubScorer:
    def __init__(self, name, result=None, exc=None):
        self.name, self._r, self._e = name, result, exc

    def score(self, features):
        if self._e:
            raise self._e
        return self._r


def ok(score): return ScoreResult.ok(score, score, "stub-0")
def na(): return ScoreResult.unavailable("not trained")
BASE_OK = {"status": "ok", "aggregate_score": 2.5, "features": [
    {"feature": "email_count", "observed": 90.0, "baseline_center": 10.0, "baseline_scale": 5.0, "z_score": 4.0,
     "is_deviant": True, "scale_floored": False}]}
engine = HybridRiskService(RiskConfig())


def comp(res, name): return next(c for c in res["components"] if c["name"] == name)


def test_all_components_weighted_and_points_sum_to_score():
    r = engine.assess({"email_count": 90.0}, BASE_OK, StubScorer("ml", ok(0.9)), StubScorer("ann", ok(0.5)))
    assert r["hybrid_risk_score"] == pytest.approx(0.45 * 90 + 0.35 * 50 + 0.2 * 50, abs=0.1)
    assert sum(c["points"] for c in r["components"]) == pytest.approx(r["hybrid_risk_score"], abs=0.2)
    assert r["contributing_components"] == ["ml_threat", "ann_anomaly", "baseline_deviation"]
    assert r["config_provisional"] is True


def test_missing_components_renormalise_and_are_listed():
    r = engine.assess({}, BASE_OK, StubScorer("ml", ok(0.8)), StubScorer("ann", na()))
    assert r["unavailable_components"] == ["ann_anomaly"]
    assert comp(r, "ann_anomaly")["effective_weight"] == 0.0 and comp(r, "ann_anomaly")["normalized"] is None
    assert comp(r, "ml_threat")["effective_weight"] == pytest.approx(0.45 / 0.65, abs=1e-3)


def test_inference_error_is_isolated_and_explicit():
    r = engine.assess({}, BASE_OK, StubScorer("ml", exc=RuntimeError("boom")), StubScorer("ann", ok(0.4)))
    c = comp(r, "ml_threat")
    assert c["status"] == "error" and "boom" in c["detail"] and r["hybrid_risk_score"] is not None


def test_out_of_range_model_score_is_rejected():
    assert ScoreResult.ok(1.7, 1.7, "v").status == ScoreStatus.ERROR
    assert ScoreResult.ok(float("nan"), 0, "v").status == ScoreStatus.ERROR
    assert safe_score(StubScorer("x", result="not a ScoreResult"), {}).status == ScoreStatus.ERROR


def test_baseline_only_cannot_reach_high():
    huge = {**BASE_OK, "aggregate_score": 50.0}
    r = engine.assess({}, huge, StubScorer("ml", na()), StubScorer("ann", na()))
    assert r["baseline_only_cap_applied"] and r["hybrid_risk_score"] == 69.0 and r["risk_level"] == "MEDIUM"


def test_no_signal_returns_none():
    assert engine.assess({}, None, StubScorer("ml", na()), StubScorer("ann", na())) is None
    assert engine.assess({}, {"status": "no_baseline"}, StubScorer("ml", na()), StubScorer("ann", na())) is None


def test_levels_follow_configurable_thresholds():
    strict = HybridRiskService(RiskConfig(medium_threshold=10, high_threshold=20, critical_threshold=30).validate())
    r = strict.assess({}, None, StubScorer("ml", ok(0.25)), StubScorer("ann", na()))
    assert r["risk_level"] == "HIGH" and strict.severity_for(95) == "CRITICAL"


def test_factors_are_deduplicated_across_sources():
    ml = ScoreResult.ok(0.8, 0.8, "s", contributions={"email_count": 0.6, "logon_count": 0.4})
    r = engine.assess({"email_count": 90.0, "logon_count": 3.0}, BASE_OK, StubScorer("ml", ml), StubScorer("ann", na()))
    names = [f["feature"] for f in r["contributing_factors"]]
    assert names.count("email_count") == 1
    f = next(f for f in r["contributing_factors"] if f["feature"] == "email_count")
    assert set(f["sources"]) == {"baseline_deviation", "ml_threat"}


def test_config_validation_and_file_override(tmp_path):
    with pytest.raises(ValueError): RiskConfig(medium_threshold=80, high_threshold=70).validate()
    with pytest.raises(ValueError): RiskConfig(weights={"ml_threat": 0, "ann_anomaly": 0, "baseline_deviation": 0}).validate()
    p = tmp_path / "r.json"; p.write_text(json.dumps({"version": "tuned-1", "provisional": False, "weights": {"ml_threat": 0.7}}))
    c = load_risk_config(str(p))
    assert c.version == "tuned-1" and not c.provisional and c.weights["ann_anomaly"] == 0.35 and c.weights["ml_threat"] == 0.7


def test_legacy_interface_still_works():
    r = HybridRiskService().calculate_hybrid_risk(0.9, None, 4.5)
    assert r["risk_level"] == "HIGH" and set(r["components"]) == {"ml_threat", "baseline_deviation"}
    assert HybridRiskService().calculate_hybrid_risk(None, None, None) is None


# ---- model service contracts -------------------------------------------------------------------
META = {"schema_version": SCHEMA_VERSION, "feature_names": ["logon_count", "email_count"], "model_version": "stub-1"}


def test_ml_service_unavailable_without_artifacts():
    s = MLThreatService(); s.model_path = s.model_path.parent / "nope.json"
    assert s.score({}).status in (ScoreStatus.UNAVAILABLE,)


def test_ml_service_orders_features_by_contract_and_passes_nan():
    seen = {}
    svc = MLThreatService(predictor=lambda v: seen.setdefault("v", v) and 0.25, meta=META)
    r = svc.score({"email_count": 7.0, "logon_count": None})
    assert r.status == ScoreStatus.OK and r.score == 0.25
    assert seen["v"][1] == 7.0 and seen["v"][0] != seen["v"][0]      # [nan, 7.0]


def test_ml_service_rejects_schema_mismatch_and_missing_contract():
    assert MLThreatService(predictor=lambda v: 0.5, meta={**META, "schema_version": "0.0.1"}).score({}).status == ScoreStatus.ERROR
    assert MLThreatService(predictor=lambda v: 0.5, meta=None).score({}).status == ScoreStatus.UNAVAILABLE
    assert MLThreatService(predictor=lambda v: 1.5, meta=META).score({}).status == ScoreStatus.ERROR


def test_ann_service_calibration_and_preprocessing():
    meta = {**META, "threshold": 0.2, "preprocessing": {"log1p": False, "mean": [1.0, 1.0], "scale": [2.0, 2.0]}}
    seen = {}
    svc = ANNAnomalyService(error_fn=lambda v: seen.setdefault("v", v) and 0.2, meta=meta)
    r = svc.score({"logon_count": 3.0, "email_count": 5.0})
    assert r.status == ScoreStatus.OK and r.score == pytest.approx(0.5) and r.raw == 0.2   # err == threshold -> 0.5
    assert seen["v"] == [1.0, 2.0]
    assert ANNAnomalyService(error_fn=lambda v: 9.9, meta=meta).score({"logon_count": 3.0}).status == ScoreStatus.ERROR  # NaN input
    assert ANNAnomalyService(error_fn=lambda v: 0.1, meta={**meta, "threshold": None}).score({}).status == ScoreStatus.UNAVAILABLE
