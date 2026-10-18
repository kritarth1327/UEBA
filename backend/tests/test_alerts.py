from datetime import date
from app.models.user import User
from app.models.alert import Alert


def test_alerts_empty_state(client):
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_alerts_list_and_filter(client, db_session):
    user = User(user_id="ACM2278", employee_name="Alice Smith", department="IT")
    db_session.add(user)
    db_session.commit()

    alert1 = Alert(
        user_id="ACM2278",
        date=date(2026, 4, 1),
        severity="CRITICAL",
        status="OPEN",
        reason="Multiple after-hours exfiltrations detected",
        risk_score=92.0
    )
    alert2 = Alert(
        user_id="ACM2278",
        date=date(2026, 4, 2),
        severity="LOW",
        status="RESOLVED",
        reason="Minor deviation in logon timing",
        risk_score=25.0
    )
    db_session.add_all([alert1, alert2])
    db_session.commit()

    # List all
    res = client.get("/api/v1/alerts")
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # Filter by severity
    res_crit = client.get("/api/v1/alerts?severity=CRITICAL")
    assert res_crit.status_code == 200
    assert res_crit.json()["total"] == 1
    assert res_crit.json()["items"][0]["severity"] == "CRITICAL"

    # Filter by status
    res_res = client.get("/api/v1/alerts?status=RESOLVED")
    assert res_res.status_code == 200
    assert res_res.json()["total"] == 1
    assert res_res.json()["items"][0]["status"] == "RESOLVED"


def test_patch_alert_status_persistence(client, db_session):
    user = User(user_id="ACM2278", employee_name="Alice Smith")
    db_session.add(user)
    db_session.commit()

    alert = Alert(
        user_id="ACM2278",
        date=date(2026, 4, 5),
        severity="HIGH",
        status="OPEN",
        reason="Suspicious USB mass transfer",
        risk_score=88.0
    )
    db_session.add(alert)
    db_session.commit()
    alert_id = alert.id

    # Update status to INVESTIGATING with notes
    patch_resp = client.patch(
        f"/api/v1/alerts/{alert_id}",
        json={"status": "INVESTIGATING", "notes": "SOC analyst triaging incident"}
    )
    assert patch_resp.status_code == 200
    updated_data = patch_resp.json()
    assert updated_data["status"] == "INVESTIGATING"
    assert updated_data["notes"] == "SOC analyst triaging incident"

    # Verify persistent change in subsequent GET
    get_resp = client.get(f"/api/v1/alerts/{alert_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "INVESTIGATING"
    assert get_resp.json()["notes"] == "SOC analyst triaging incident"


def test_patch_alert_not_found(client):
    patch_resp = client.patch(
        "/api/v1/alerts/99999",
        json={"status": "RESOLVED"}
    )
    assert patch_resp.status_code == 404
