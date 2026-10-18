from app.services.hybrid_risk_service import HybridRiskService
from app.services.baseline_service import BaselineService
from app.models.baseline import PersonalBaseline
from app.models.user import User
import json


def test_hybrid_risk_calculation():
    service = HybridRiskService()
    # High risk signals
    result_high = service.calculate_hybrid_risk(
        ml_score=0.9,
        ann_score=0.8,
        baseline_deviation=4.5
    )
    assert result_high is not None
    assert result_high["risk_level"] == "HIGH"
    assert result_high["hybrid_risk_score"] >= 70.0

    # Low risk signals
    result_low = service.calculate_hybrid_risk(
        ml_score=0.05,
        ann_score=0.02,
        baseline_deviation=0.1
    )
    assert result_low is not None
    assert result_low["risk_level"] == "LOW"
    assert result_low["hybrid_risk_score"] < 40.0

    # None if all inputs are None
    assert service.calculate_hybrid_risk(None, None, None) is None


def test_baseline_deviation_calculation(db_session):
    user = User(user_id="ACM2278")
    db_session.add(user)

    metrics_payload = {
        "logon_count": {"mean": 2.0, "std": 0.5},
        "removable_device_events": {"mean": 0.0, "std": 0.1}
    }
    baseline = PersonalBaseline(
        user_id="ACM2278",
        metrics_json=json.dumps(metrics_payload),
        sample_size=30,
        is_active=True
    )
    db_session.add(baseline)
    db_session.commit()

    service = BaselineService(db_session)
    comparisons = service.compare_observed_to_baseline(
        user_id="ACM2278",
        observed={"logon_count": 2.0, "removable_device_events": 3.0}
    )

    assert comparisons is not None
    assert len(comparisons) == 2

    # Normal logon count: observed 2.0 vs mean 2.0 -> z-score 0
    logon_comp = next(c for c in comparisons if c["metric_name"] == "logon_count")
    assert logon_comp["z_score"] == 0.0
    assert logon_comp["is_deviant"] is False

    # Anomalous USB event: observed 3.0 vs mean 0.0 -> high z-score
    usb_comp = next(c for c in comparisons if c["metric_name"] == "removable_device_events")
    assert usb_comp["z_score"] >= 2.5
    assert usb_comp["is_deviant"] is True
