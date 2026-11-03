import json
from pathlib import Path

from app.pipeline.schema import FEATURE_NAMES
from app.services.ann_anomaly_service import ann_anomaly_service
from app.services.model_interfaces import ScoreStatus
from app.services.scoring_service import ScoringService
from app.services.spedia_ann_anomaly_service import (
    FEATURES,
    SpediaANNAnomalyService,
    spedia_ann_anomaly_service,
)


def _features():
    return {name: 1.0 for name in FEATURES}


def test_spedia_artifact_contract_and_inference():
    service = SpediaANNAnomalyService()
    assert service.is_available()
    assert service._features == FEATURES
    assert len(FEATURES) == 14
    assert service.model_name == "spedia_dense_autoencoder"
    result = service.score(_features())
    assert result.status == ScoreStatus.OK
    assert result.model_version == "spedia-experimental-1"


def test_spedia_missing_or_invalid_features_are_unavailable():
    service = SpediaANNAnomalyService()
    missing = _features()
    missing.pop(FEATURES[0])
    assert service.score(missing).status == ScoreStatus.UNAVAILABLE

    invalid = _features()
    invalid[FEATURES[1]] = float("nan")
    assert service.score(invalid).status == ScoreStatus.UNAVAILABLE

    negative = _features()
    negative[FEATURES[2]] = -1
    assert service.score(negative).status == ScoreStatus.UNAVAILABLE


def test_spedia_artifact_failure_is_error(tmp_path: Path):
    service = SpediaANNAnomalyService(artifact_dir=tmp_path / "missing")
    result = service.score(_features())
    assert result.status == ScoreStatus.ERROR


def test_dataset_specific_ann_selection():
    service = ScoringService.__new__(ScoringService)
    service.ann = None
    service._cert_ann = ann_anomaly_service
    assert service._ann_for_dataset("spedia") is spedia_ann_anomaly_service
    assert service._ann_for_dataset("cert_r42") is ann_anomaly_service
    assert service._ann_for_dataset(None) is ann_anomaly_service
    assert service._ann_for_dataset("unknown").score(_features()).status == ScoreStatus.UNAVAILABLE


def test_spedia_feature_contract_does_not_replace_shared_schema():
    assert FEATURES != list(FEATURE_NAMES)
    assert set(FEATURES).issubset(set(FEATURE_NAMES))


def test_metadata_records_dataset_and_feature_order():
    path = Path(__file__).resolve().parents[1] / "artifacts" / "spedia_dense_autoencoder" / "autoencoder_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    assert metadata["dataset"] == "spedia"
    assert metadata["feature_names"] == FEATURES
