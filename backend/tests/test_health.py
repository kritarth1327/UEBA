def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "timestamp" in data
    assert data["version"] == "1.0.0"


def test_system_status(client):
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert "backend_status" in data
    assert "database_status" in data
    assert "dataset_status" in data
    assert "pipeline_status" in data
    assert "model_status" in data
    assert data["database_status"]["status"] == "healthy"
    assert data["backend_status"]["status"] == "healthy"
