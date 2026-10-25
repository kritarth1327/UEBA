from app.services.cert_supervised_service import CERTSupervisedService
from app.services.model_interfaces import ScoreStatus


class FakeModel:
    def predict_proba(self, values):
        assert values.shape == (1, 11)
        import numpy as np
        return np.array([[0.2, 0.8]])


def valid_features():
    return {
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


def test_returns_score_result():
    service = CERTSupervisedService()
    service.model = FakeModel()

    result = service.score(valid_features())

    assert result.status == ScoreStatus.OK
    assert result.score == 0.8
    assert result.raw == 0.8


def test_missing_feature_returns_error():
    service = CERTSupervisedService()
    service.model = FakeModel()
    features = valid_features()
    del features["email_count"]

    result = service.score(features)

    assert result.status == ScoreStatus.ERROR
    assert "email_count" in result.detail


def test_unavailable_model_returns_unavailable():
    service = CERTSupervisedService()
    service.model = None

    result = service.score(valid_features())

    assert result.status == ScoreStatus.UNAVAILABLE


def test_repository_cert_artifact_is_available_and_uses_training_order():
    service = CERTSupervisedService()

    assert service.model_path.is_file()
    assert service.is_available()
    assert service.metadata["metrics"]["xgboost"]["features"] == service.FEATURE_NAMES


def test_missing_ann_feature_is_not_fabricated():
    from app.services.ann_anomaly_service import ANNAnomalyService

    service = ANNAnomalyService(
        error_fn=lambda values: 0.1,
        meta={
            "schema_version": "1.0.0",
            "feature_names": [
                "logon_count",
                "after_hours_logons",
                "file_copied_removable",
                "email_count",
                "email_external_count",
                "email_attachment_count",
                "http_request_count",
                "http_after_hours_count",
                "removable_device_events",
                "total_session_duration",
            ],
            "threshold": 0.2,
        },
    )

    result = service.score(valid_features())

    assert result.status == ScoreStatus.ERROR
    assert "total_session_duration" in result.detail
