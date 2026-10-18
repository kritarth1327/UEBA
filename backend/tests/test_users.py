from datetime import date
from app.models.user import User
from app.models.behavior import DailyBehaviorProfile
from app.models.prediction import ModelPrediction


def test_users_empty(client):
    response = client.get("/api/v1/users")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


def test_users_list_and_pagination(client, db_session):
    for i in range(15):
        user = User(
            user_id=f"USR{i:03d}",
            employee_name=f"Employee {i}",
            department="Finance" if i % 2 == 0 else "HR",
            role="Analyst"
        )
        db_session.add(user)
    db_session.commit()

    # Page 1 with page_size 10
    response = client.get("/api/v1/users?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] == 15
    assert data["total_pages"] == 2

    # Filter by department
    resp_filtered = client.get("/api/v1/users?department=Finance")
    assert resp_filtered.status_code == 200
    data_filtered = resp_filtered.json()
    assert data_filtered["total"] == 8

    # Search by keyword
    resp_search = client.get("/api/v1/users?search=USR005")
    assert resp_search.status_code == 200
    assert resp_search.json()["total"] == 1


def test_user_detail_and_404(client, db_session):
    # Nonexistent user
    res_404 = client.get("/api/v1/users/NONEXISTENT")
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()

    # Existing user
    user = User(
        user_id="ACM2278",
        employee_name="Alice Smith",
        email="asmith@dtaa.com",
        department="Engineering",
        role="Lead Engineer"
    )
    db_session.add(user)
    db_session.commit()

    res_found = client.get("/api/v1/users/ACM2278")
    assert res_found.status_code == 200
    data = res_found.json()
    assert data["user_id"] == "ACM2278"
    assert data["employee_name"] == "Alice Smith"
    assert data["department"] == "Engineering"


def test_user_behavior_and_risk(client, db_session):
    user = User(user_id="ACM2278", employee_name="Alice Smith")
    profile = DailyBehaviorProfile(
        user_id="ACM2278",
        date=date(2026, 3, 10),
        logon_count=3,
        after_hours_logons=1,
        removable_device_events=2,
        email_count=14
    )
    pred = ModelPrediction(
        user_id="ACM2278",
        date=date(2026, 3, 10),
        ml_threat_score=0.78,
        ann_anomaly_score=0.12,
        baseline_deviation_score=2.8,
        hybrid_risk_score=76.4,
        risk_level="HIGH"
    )
    db_session.add_all([user, profile, pred])
    db_session.commit()

    # Behavior endpoint
    res_b = client.get("/api/v1/users/ACM2278/behavior")
    assert res_b.status_code == 200
    b_data = res_b.json()
    assert b_data["total_days"] == 1
    assert b_data["profiles"][0]["logon_count"] == 3
    assert b_data["profiles"][0]["removable_device_events"] == 2

    # Risk endpoint
    res_r = client.get("/api/v1/users/ACM2278/risk")
    assert res_r.status_code == 200
    r_data = res_r.json()
    assert len(r_data["history"]) == 1
    assert r_data["latest_prediction"]["hybrid_risk_score"] == 76.4
    assert r_data["summary"]["max_risk_score"] == 76.4
