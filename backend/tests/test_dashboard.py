from datetime import date
from app.models.user import User
from app.models.alert import Alert
from app.models.prediction import ModelPrediction


def test_dashboard_empty_state(client):
    """Verifies that an unseeded database returns truthful empty metrics."""
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_users"] == 0
    assert data["assessed_users"] == 0
    assert data["dataset_ready"] is False
    assert data["models_ready"] is False
    assert data["recent_alerts"] == []
    assert data["highest_risk_users"] == []
    assert data["alerts_by_severity"]["critical"] == 0


def test_dashboard_with_persisted_records(client, db_session):
    """Verifies dashboard aggregates when real records are inserted."""
    user = User(
        user_id="ACM2278",
        employee_name="Alice Smith",
        department="Engineering",
        role="Software Engineer"
    )
    db_session.add(user)
    db_session.commit()

    pred = ModelPrediction(
        user_id="ACM2278",
        date=date(2026, 3, 15),
        hybrid_risk_score=85.5,
        risk_level="HIGH"
    )
    alert = Alert(
        user_id="ACM2278",
        date=date(2026, 3, 15),
        severity="HIGH",
        status="OPEN",
        reason="After-hours USB device connection",
        risk_score=85.5
    )
    db_session.add(pred)
    db_session.add(alert)
    db_session.commit()

    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_users"] == 1
    assert data["assessed_users"] == 1
    assert data["dataset_ready"] is True
    assert data["alerts_by_severity"]["high"] == 1
    assert len(data["recent_alerts"]) == 1
    assert data["recent_alerts"][0]["user_id"] == "ACM2278"
    assert len(data["highest_risk_users"]) == 1
    assert data["highest_risk_users"][0]["user_id"] == "ACM2278"
    assert data["highest_risk_users"][0]["hybrid_risk_score"] == 85.5
