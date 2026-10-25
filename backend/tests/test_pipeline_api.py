
import pytest

from app.core.config import settings
from tests.helpers import make_spedia_csv


@pytest.fixture()
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAW_DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "SPEDIA_FILE", tmp_path / "spedia.csv")
    make_spedia_csv(tmp_path / "spedia.csv", days=20)


def test_feature_schema_endpoint(client):
    r = client.get("/api/v1/features/schema").json()
    assert r["schema_version"] and r["features"][0]["name"] == "logon_count"


def test_full_flow_ingest_baseline_score_then_read(client, raw):
    r = client.post("/api/v1/pipeline/ingest", json={"dataset": "spedia"})
    assert r.status_code == 200 and r.json()["user_days"] == 40 and not r.json()["skipped"]
    assert client.post("/api/v1/pipeline/ingest", json={"dataset": "spedia"}).json()["skipped"] is True

    b = client.post("/api/v1/pipeline/baselines/generate", json={}).json()
    assert b["persisted"] == 2 and b["skipped"] == 0
    bl = client.get("/api/v1/users/alice/baseline").json()
    assert bl["has_baseline"] and bl["baseline"]["metrics"]["email_count"]["n"] == 20

    s = client.post("/api/v1/pipeline/score", json={}).json()
    assert s["errors"] == [] and s["predictions_written"] > 0

    risk = client.get("/api/v1/users/alice/risk").json()
    assert risk["latest_prediction"]["config_version"] == "risk-config-provisional-v2-cert-supervised"
    assert risk["latest_prediction"]["ml_threat_score"] is None
    assert set(risk["latest_prediction"]["components"]["unavailable_components"]) == {
        "ml_threat", "ann_anomaly", "cert_supervised"
    }

    beh = client.get("/api/v1/users/alice/behavior").json()
    assert beh["total_days"] == 20 and beh["profiles"][0]["features"]["total_session_duration"] is None

    summ = client.get("/api/v1/pipeline/summary").json()
    assert summ["datasets"]["spedia"]["user_days"] == 40 and summ["active_baselines"] == 2
    assert client.get("/api/v1/pipeline/runs").json()[0]["status"] == "completed"
    assert client.get("/api/v1/alerts").json()["total"] >= 1
    assert client.get("/api/v1/dashboard/overview").json()["assessed_users"] == 2


def test_ingest_errors_are_meaningful(client, raw):
    assert client.post("/api/v1/pipeline/ingest", json={"dataset": "bogus"}).status_code == 422
    assert client.post("/api/v1/pipeline/ingest", json={"dataset": "spedia", "path": "nope.csv"}).status_code == 404
    assert client.post("/api/v1/pipeline/ingest", json={"dataset": "spedia", "path": "/etc/hostname"}).status_code == 400
    assert client.post("/api/v1/pipeline/ingest", json={"dataset": "spedia", "path": "../x.csv"}).status_code in (400, 404)


def test_baseline_and_score_validation(client, raw):
    assert client.post("/api/v1/pipeline/baselines/generate", json={"user_id": "ghost"}).status_code == 404
    assert client.post("/api/v1/pipeline/score", json={"user_id": "ghost"}).status_code == 404
    assert client.post("/api/v1/pipeline/score", json={"start_date": "2025-04-01", "end_date": "2025-03-01"}).status_code == 422
    assert client.post("/api/v1/pipeline/score", json={"start_date": "garbage"}).status_code == 422


def test_risk_evaluate_adhoc(client, raw):
    client.post("/api/v1/pipeline/ingest", json={"dataset": "spedia"})
    client.post("/api/v1/pipeline/baselines/generate", json={})
    quiet = {"logon_count": 1, "email_count": 1, "http_request_count": 3, "file_access_count": 1}
    loud = {**quiet, "email_count": 400, "email_external_count": 300, "removable_device_events": 50}
    lo = client.post("/api/v1/risk/evaluate", json={"user_id": "bob", "date": "2025-04-01", "features": quiet}).json()
    hi = client.post("/api/v1/risk/evaluate", json={"user_id": "bob", "date": "2025-04-01", "features": loud}).json()
    assert lo["assessed"] and hi["assessed"] and hi["hybrid_risk_score"] > lo["hybrid_risk_score"]
    assert hi["baseline"]["baseline_source"] == "persisted"
    assert {c["name"] for c in hi["components"]} == {
        "ml_threat", "ann_anomaly", "baseline_deviation", "cert_supervised"
    }
    # nothing persisted by ad hoc evaluation
    assert client.get("/api/v1/pipeline/summary").json()["predictions"] == 0


def test_risk_evaluate_validation_and_unknown_user(client, raw):
    bad = client.post("/api/v1/risk/evaluate", json={"user_id": "u", "date": "2025-04-01", "features": {"made_up": 1}})
    assert bad.status_code == 422 and "made_up" in bad.json()["detail"]
    assert client.post("/api/v1/risk/evaluate", json={"user_id": "", "date": "2025-04-01", "features": {}}).status_code == 422
    new = client.post("/api/v1/risk/evaluate", json={"user_id": "never-seen", "date": "2025-04-01",
                                                      "features": {"logon_count": 5}}).json()
    assert new["assessed"] is False and "no component" in new["reason"]


def test_risk_config_endpoint_labels_provisional(client):
    c = client.get("/api/v1/risk/config").json()
    assert c["config_provisional"] is True
    assert set(c["weights"]) == {
        "ml_threat", "ann_anomaly", "baseline_deviation", "cert_supervised"
    }


def test_risk_evaluate_uses_cert_model_when_all_cert_features_are_present(client, raw):
    features = {
        "logon_count": 5,
        "after_hours_logons": 1,
        "file_copied_removable": 0,
        "email_count": 10,
        "email_external_count": 2,
        "email_attachment_count": 1,
        "email_total_bytes": 50000,
        "http_request_count": 20,
        "http_after_hours_count": 3,
        "removable_device_events": 0,
        "after_hours_event_count": 4,
    }

    response = client.post(
        "/api/v1/risk/evaluate",
        json={
            "user_id": "cert-integration-user",
            "date": "2025-04-01",
            "features": features,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assessed"] is True
    components = {component["name"]: component for component in body["components"]}
    assert components["cert_supervised"]["status"] == "ok"
    assert "cert_supervised" in body["contributing_components"]
