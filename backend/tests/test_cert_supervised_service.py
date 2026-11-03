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
