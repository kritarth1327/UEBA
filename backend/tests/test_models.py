def test_models_status_endpoint(client):
    response = client.get("/api/v1/models/status")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) == 5
    model_names = [m["model_name"] for m in data["models"]]
    assert "Random Forest Baseline" in model_names
    assert "XGBoost Supervised Threat Classifier" in model_names
    assert "Dense Autoencoder Anomaly Detector" in model_names
    assert "CERT Supervised Classifier" in model_names
    assert "Hybrid Risk Engine" in model_names


def test_models_evaluation_reports_available_file_metrics(client):
    response = client.get("/api/v1/models/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "evaluations" in data
    assert len(data["evaluations"]) == 5
    xgboost = next(ev for ev in data["evaluations"] if ev["model_name"] == "XGBoost Classifier")
    assert xgboost["is_available"] is True
    assert xgboost["f1_score"] is not None
