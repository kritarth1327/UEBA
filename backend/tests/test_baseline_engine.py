from datetime import date, timedelta
import pytest

from app.pipeline.baseline_engine import BaselineConfig, compute_baseline, score_deviation

D0 = date(2025, 3, 1)
CFG = BaselineConfig(min_samples=5, max_window_days=None)


def hist(values, name="f", start=D0):
    return {start + timedelta(days=i): {name: v} for i, v in enumerate(values)}


def test_baseline_uses_only_strictly_earlier_days():
    h = hist([10, 10, 11, 9, 10, 10, 500])       # day 7 is the day being judged
    as_of = D0 + timedelta(days=6)
    b = compute_baseline(h, as_of, CFG)
    assert b["status"] == "ok" and b["window_end"] == as_of - timedelta(days=1)
    assert b["metrics"]["f"]["max"] == 11         # the 500 never enters its own baseline


def test_current_observation_cannot_change_its_baseline():
    base = hist([10, 10, 11, 9, 10, 10])
    as_of = D0 + timedelta(days=6)
    a = compute_baseline({**base, as_of: {"f": 1}}, as_of, CFG)
    b = compute_baseline({**base, as_of: {"f": 99999}}, as_of, CFG)
    assert a["metrics"] == b["metrics"]


def test_insufficient_and_no_history():
    assert compute_baseline({}, D0, CFG)["status"] == "no_history"
    r = compute_baseline(hist([1, 2, 3]), D0 + timedelta(days=3), CFG)
    assert r["status"] == "insufficient_history" and r["metrics"] == {} and r["unusable_features"]
    assert score_deviation({"f": 5}, r["metrics"], CFG)["status"] == "no_baseline"


def test_missing_values_are_skipped_not_zero_filled():
    h = hist([4, None, 6, 5, 5, None, 5, 5])
    b = compute_baseline(h, D0 + timedelta(days=8), CFG)
    m = b["metrics"]["f"]
    assert m["n"] == 6 and m["median"] == 5.0
    assert compute_baseline(hist([None] * 10), D0 + timedelta(days=10), CFG)["metrics"] == {}


def test_zero_variance_uses_scale_floor():
    m = compute_baseline(hist([0] * 6), D0 + timedelta(days=6), CFG)["metrics"]
    r = score_deviation({"f": 3}, m, CFG)
    f = r["features"][0]
    assert f["scale_floored"] and f["baseline_scale"] == CFG.scale_floor and f["z_score"] == 3.0 and f["is_deviant"]


def test_mad_scale_and_robustness_to_one_outlier_day():
    m = compute_baseline(hist([10, 12, 11, 9, 10, 11, 10, 300]), D0 + timedelta(days=8), CFG)["metrics"]
    assert m["f"]["median"] == 10.5 and m["f"]["std"] > 50      # std is blown up by the outlier
    z = score_deviation({"f": 20}, m, CFG)["features"][0]
    assert z["z_score"] > 5                                     # MAD-based scale keeps sensitivity


def test_unobserved_and_unbaselined_features_skipped():
    m = compute_baseline(hist([1, 2, 3, 2, 1, 2]), D0 + timedelta(days=6), CFG)["metrics"]
    r = score_deviation({"f": None, "other": 5}, m, CFG)
    assert r["status"] == "no_comparable_features" and r["skipped"] == ["f"]


def test_only_increases_raise_aggregate():
    m = compute_baseline(hist([10, 11, 9, 10, 10, 11]), D0 + timedelta(days=6), CFG)["metrics"]
    assert score_deviation({"f": 0}, m, CFG)["aggregate_score"] == 0.0
    assert score_deviation({"f": 40}, m, CFG)["aggregate_score"] > 5


def test_z_is_capped():
    m = compute_baseline(hist([1, 1, 1, 1, 1, 1]), D0 + timedelta(days=6), CFG)["metrics"]
    assert score_deviation({"f": 1e9}, m, CFG)["features"][0]["z_score"] == CFG.z_cap


def test_trailing_window_limits_history():
    cfg = BaselineConfig(min_samples=3, max_window_days=5)
    b = compute_baseline(hist(range(30)), D0 + timedelta(days=30), cfg)
    assert b["sample_size"] == 5 and b["window_start"] == D0 + timedelta(days=25)


def test_top_k_aggregate():
    cfg = BaselineConfig(min_samples=3, max_window_days=None, top_k=2)
    h = {D0 + timedelta(days=i): {"a": 1, "b": 1, "c": 1} for i in range(4)}
    m = compute_baseline(h, D0 + timedelta(days=4), cfg)["metrics"]
    r = score_deviation({"a": 4, "b": 6, "c": 1}, m, cfg)       # z = 3, 5, 0
    assert r["aggregate_score"] == 4.0
