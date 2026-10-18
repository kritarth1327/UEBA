def test_models_status_endpoint(client):
    response = client.get("/api/v1/models/status")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) == 4
    model_names = [m["model_name"] for m in data["models"]]
    assert "Random Forest Baseline" in model_names
    assert "XGBoost Supervised Threat Classifier" in model_names
    assert "Dense Autoencoder Anomaly Detector" in model_names
    assert "Hybrid Risk Engine" in model_names


def test_models_evaluation_empty_state(client):
    """Verifies that evaluation returns honest unavailable state when models haven't been evaluated."""
    response = client.get("/api/v1/models/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert "evaluations" in data
    assert len(data["evaluations"]) == 4
    for ev in data["evaluations"]:
        assert ev["is_available"] is False
        assert ev["f1_score"] is None
