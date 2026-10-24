
import json
from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.alert import Alert
from app.models.baseline import PersonalBaseline
from app.models.behavior import DailyBehaviorProfile
from app.models.ingestion import IngestionRun
from app.models.prediction import ModelPrediction
from app.models.user import User
from app.services.baseline_service import BaselineService
from app.services.ingestion_service import IngestionError, IngestionService
from app.services.scoring_service import ScoringService
from tests.helpers import SECRET, make_spedia_csv, spedia_row, write_csv
from datetime import datetime

count = lambda db, model: db.scalar(select(func.count()).select_from(model))  # noqa: E731
LAST = date(2025, 3, 3).toordinal() + 19


@pytest.fixture()
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAW_DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "SPEDIA_FILE", tmp_path / "spedia.csv")
    make_spedia_csv(tmp_path / "spedia.csv", days=20)
    return tmp_path


def test_ingest_persists_profiles_and_is_idempotent(db_session, raw_dir):
    svc = IngestionService(db_session)
    r1 = svc.ingest("spedia")
    assert r1["skipped"] is False and r1["users"] == 2 and r1["user_days"] == 40
    assert r1["profiles_inserted"] == 40 and "total_session_duration" in r1["unavailable_features"]
    assert r1["label_summary"] == {"events": 40 * 7 + 30, "anomalous_events": 30}
    assert count(db_session, DailyBehaviorProfile) == 40 and count(db_session, User) == 2

    r2 = svc.ingest("spedia")                       # identical source + config
    assert r2["skipped"] is True and count(db_session, DailyBehaviorProfile) == 40
    r3 = svc.ingest("spedia", force=True)           # forced re-ingest updates, never duplicates
    assert r3["profiles_inserted"] == 0 and r3["profiles_updated"] == 40
    assert count(db_session, DailyBehaviorProfile) == 40 and count(db_session, IngestionRun) == 2


def test_unavailable_features_stay_null_and_no_raw_content_is_stored(db_session, raw_dir):
    IngestionService(db_session).ingest("spedia")
    p = db_session.scalars(select(DailyBehaviorProfile)).first()
    payload = json.loads(p.features_json)
    assert payload["features"]["total_session_duration"] is None and p.total_session_duration == 0.0
    assert "total_session_duration" in payload["unavailable_features"]
    assert p.dataset_source == "spedia" and p.event_count and p.anomalous_event_count is not None
    dump = json.dumps([p.features_json for p in db_session.scalars(select(DailyBehaviorProfile))])
    assert SECRET not in dump and "secret.example" not in dump


def test_label_counts_are_stored_but_not_in_feature_payload(db_session, raw_dir):
    IngestionService(db_session).ingest("spedia")
    feats = json.loads(db_session.scalars(select(DailyBehaviorProfile)).first().features_json)["features"]
    assert "anomalous_event_count" not in feats and "event_count" not in feats


def test_path_outside_raw_dir_rejected_and_missing_file(db_session, raw_dir, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere") / "x.csv"; outside.write_text("a")
    with pytest.raises(IngestionError, match="inside"):
        IngestionService(db_session).ingest("spedia", str(outside))
    with pytest.raises(IngestionError, match="not found"):
        IngestionService(db_session).ingest("spedia", "missing.csv")
    with pytest.raises(IngestionError, match="inside"):
        IngestionService(db_session).ingest("spedia", "../../etc/passwd")
    with pytest.raises(IngestionError, match="unsupported"):
        IngestionService(db_session).ingest("nope")


def test_failed_run_is_recorded_and_rolled_back(db_session, raw_dir):
    bad = write_csv(raw_dir / "bad.csv", [spedia_row(1, "", datetime(2025, 3, 4), "http", "URL accedida")])
    with pytest.raises(IngestionError):
        IngestionService(db_session).ingest("spedia", "bad.csv")
    run = db_session.scalars(select(IngestionRun)).one()
    assert run.status == "failed" and "no valid events" in run.error
    assert count(db_session, DailyBehaviorProfile) == 0


def test_dataset_conflicts_never_overwrite(db_session, raw_dir):
    IngestionService(db_session).ingest("spedia")
    p = db_session.scalars(select(DailyBehaviorProfile)).first()
    p.dataset_source = "cert_r42"; db_session.commit()
    r = IngestionService(db_session).ingest("spedia", force=True)
    assert r["profiles_conflicting_dataset"] == 1 and p.dataset_source == "cert_r42"


def test_baseline_generation_persists_one_active_row_per_user(db_session, raw_dir):
    IngestionService(db_session).ingest("spedia")
    svc = BaselineService(db_session)
    res = svc.generate_all()
    assert all(r["persisted"] for r in res)
    active = db_session.scalars(select(PersonalBaseline).where(PersonalBaseline.is_active.is_(True))).all()
    assert len(active) == 2
    svc.generate_all()                               # regenerate: old deactivated, still one active
    assert count(db_session, PersonalBaseline) == 4
    assert len(db_session.scalars(select(PersonalBaseline).where(PersonalBaseline.is_active.is_(True))).all()) == 2
    b = svc.get_user_baseline("alice")
    assert b["sample_size"] == 20 and b["config"]["version"] == "baseline-v1-provisional"


def test_new_user_with_short_history_gets_no_baseline(db_session, raw_dir):
    rows = [spedia_row(i, "newbie", datetime(2025, 3, 3 + i, 9), "http", "URL accedida") for i in range(3)]
    write_csv(raw_dir / "n.csv", rows)
    IngestionService(db_session).ingest("spedia", "n.csv")
    out = BaselineService(db_session).generate_for_user("newbie")
    assert out["status"] == "insufficient_history" and out["persisted"] is False
    assert BaselineService(db_session).get_user_baseline("newbie") is None


def test_scoring_is_point_in_time_and_flags_the_spike(db_session, raw_dir):
    IngestionService(db_session).ingest("spedia")
    s = ScoringService(db_session).score_range()
    assert s["errors"] == [] and s["days_scored"] == 40 and s["predictions_written"] > 0
    # first min_samples days have no baseline => no prediction (not a fabricated 0)
    first = db_session.scalars(select(ModelPrediction).where(ModelPrediction.date == date(2025, 3, 3))).all()
    assert first == []
    spike = db_session.scalars(select(ModelPrediction).where(
        ModelPrediction.user_id == "alice", ModelPrediction.date == date(2025, 3, 22))).one()
    calm = db_session.scalars(select(ModelPrediction).where(
        ModelPrediction.user_id == "bob", ModelPrediction.date == date(2025, 3, 22))).one()
    assert spike.hybrid_risk_score > calm.hybrid_risk_score and spike.risk_level == "MEDIUM"
    assert spike.ml_threat_score is None and spike.ann_anomaly_score is None     # unavailable, not 0
    comps = json.loads(spike.components_json)
    assert set(comps["unavailable_components"]) == {
        "ml_threat", "ann_anomaly", "cert_supervised"
    }
    assert comps["baseline_only_cap_applied"]
    factors = json.loads(spike.contributing_factors_json)
    assert any(f["feature"] in ("email_external_count", "removable_device_events") for f in factors)


def test_rescoring_does_not_duplicate_and_preserves_analyst_status(db_session, raw_dir):
    IngestionService(db_session).ingest("spedia")
    ScoringService(db_session).score_range()
    n_pred, n_alert = count(db_session, ModelPrediction), count(db_session, Alert)
    assert n_alert >= 1
    a = db_session.scalars(select(Alert)).first(); a.status = "INVESTIGATING"; a.notes = "looking"; db_session.commit()
    ScoringService(db_session).score_range()
    assert (count(db_session, ModelPrediction), count(db_session, Alert)) == (n_pred, n_alert)
    db_session.refresh(a); assert a.status == "INVESTIGATING" and a.notes == "looking"


def test_models_plug_in_through_stable_interface(db_session, raw_dir):
    from app.services.model_interfaces import ScoreResult
    class Stub:                                       # TEMPORARY STUB for Rhythm's model
        name = "ml_threat"
        def score(self, f): return ScoreResult.ok(0.9, 0.9, "stub")
    IngestionService(db_session).ingest("spedia")
    ScoringService(db_session, ml_scorer=Stub()).score_range(user_id="bob")
    p = db_session.scalars(select(ModelPrediction).where(ModelPrediction.user_id == "bob")).first()
    assert p.ml_threat_score == 0.9 and "ml_threat" in json.loads(p.components_json)["contributing_components"]


def test_scoring_isolates_per_user_failures(db_session, raw_dir, monkeypatch):
    IngestionService(db_session).ingest("spedia")
    svc = ScoringService(db_session)
    real = svc._score_user
    def flaky(uid, *a):
        if uid == "alice": raise RuntimeError("boom")
        return real(uid, *a)
    monkeypatch.setattr(svc, "_score_user", flaky)
    s = svc.score_range()
    assert s["users_processed"] == 1 and s["errors"][0]["user_id"] == "alice"
    assert db_session.scalars(select(ModelPrediction).where(ModelPrediction.user_id == "alice")).first() is None
