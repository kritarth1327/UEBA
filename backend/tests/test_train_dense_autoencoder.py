from pathlib import Path

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from scripts.train_dense_autoencoder import (  # noqa: E402
    FEATURE_NAMES,
    DenseAutoencoder,
    Split,
    calibrate_threshold,
    load_features,
    split_rows,
    transform_splits,
    train_model,
    validate_feature_order,
    validate_output_dir,
    validate_checkpoint,
)
from app.services.ann_anomaly_service import ANNAnomalyService


def _frame() -> pd.DataFrame:
    rows = []
    for day in ("2020-01-01", "2020-01-02", "2020-01-03"):
        row = {name: 1.0 for name in FEATURE_NAMES}
        row["date"] = day
        rows.append(row)
    return pd.DataFrame(rows)


def test_duration_policy_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "features.csv"
    frame = _frame()
    frame.loc[0, "total_session_duration"] = np.nan
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="total_session_duration"):
        load_features(path, "reject", 0.0)

    loaded = load_features(path, "zero", 0.0)
    assert loaded.loc[0, "total_session_duration"] == 0.0


def test_feature_order_is_checked() -> None:
    with pytest.raises(ValueError, match="Feature order mismatch"):
        validate_feature_order(list(reversed(FEATURE_NAMES)))


def test_source_columns_are_validated_before_selection(tmp_path: Path) -> None:
    path = tmp_path / "features.csv"
    frame = _frame()
    frame = pd.concat([frame, frame[["logon_count"]]], axis=1)
    frame.columns = list(frame.columns[:-1]) + ["logon_count"]
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate feature columns"):
        load_features(path, "zero", 0.0)


def test_split_is_chronological_and_complete() -> None:
    splits = split_rows(
        _frame(),
        [
            Split("train", "2020-01-01", "2020-01-01"),
            Split("validation", "2020-01-02", "2020-01-02"),
            Split("test", "2020-01-03", "2020-01-03"),
        ],
    )
    assert [len(splits[name]) for name in ("train", "validation", "test")] == [1, 1, 1]


def test_split_rejects_empty_and_non_chronological_boundaries() -> None:
    with pytest.raises(ValueError, match="Split train is empty"):
        split_rows(
            _frame(),
            [
                Split("train", "2019-01-01", "2019-01-02"),
                Split("validation", "2020-01-01", "2020-01-02"),
                Split("test", "2020-01-03", "2020-01-03"),
            ],
        )
    with pytest.raises(ValueError, match="start date"):
        split_rows(
            _frame(),
            [
                Split("train", "2020-01-01", "2019-12-31"),
                Split("validation", "2020-01-02", "2020-01-02"),
                Split("test", "2020-01-03", "2020-01-03"),
            ],
        )
    with pytest.raises(ValueError, match="not chronological"):
        split_rows(
            _frame(),
            [
                Split("train", "2020-01-01", "2020-01-02"),
                Split("validation", "2020-01-02", "2020-01-02"),
                Split("test", "2020-01-03", "2020-01-03"),
            ],
        )


def test_scaler_is_fit_on_training_rows_only() -> None:
    frame = _frame()
    frame.loc[0, "logon_count"] = 1.0
    frame.loc[1, "logon_count"] = 3.0
    frame.loc[2, "logon_count"] = 1000.0
    splits = {
        "train": frame.iloc[:2].copy(),
        "validation": frame.iloc[2:].copy(),
        "test": frame.iloc[2:].copy(),
    }
    transformed, scaler = transform_splits(splits)
    assert scaler.mean_[0] == pytest.approx(np.log1p([1.0, 3.0]).mean())
    assert transformed["validation"][0, 0] > 1.0


def test_early_stopping_restores_best_checkpoint() -> None:
    values = {
        "train": np.zeros((4, len(FEATURE_NAMES)), dtype=np.float32),
        "validation": np.ones((2, len(FEATURE_NAMES)), dtype=np.float32),
    }
    model, history, best_epoch, stopping_epoch = train_model(
        values, seed=42, max_epochs=4, patience=1, min_delta=1e6, learning_rate=1e-3
    )
    assert stopping_epoch <= 4
    assert best_epoch == 1
    assert len(history) == stopping_epoch
    with torch.no_grad():
        loss = torch.mean((model(torch.from_numpy(values["validation"])) - torch.from_numpy(values["validation"])) ** 2).item()
    assert loss == pytest.approx(history[best_epoch - 1]["validation_loss"])


def test_threshold_uses_validation_errors_only() -> None:
    assert calibrate_threshold(np.array([1.0, 2.0, 3.0])) == pytest.approx(2.98)
    with pytest.raises(ValueError, match="non-empty"):
        calibrate_threshold(np.array([]))


def test_candidate_outputs_and_production_inference_compatibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sklearn.preprocessing import StandardScaler
    import json
    import joblib

    output_dir = tmp_path / "candidate"
    model = DenseAutoencoder(len(FEATURE_NAMES))
    scaler = StandardScaler().fit(np.ones((2, len(FEATURE_NAMES))))
    metadata = {
        "splits": {"validation": {"count": 2}},
        "preprocessing": {
            "total_session_duration_policy": "zero",
            "total_session_duration_assumption": (
                "Missing values explicitly replaced with zero; candidate assumption."
            ),
            "total_session_duration_original_handling": "unknown",
        },
    }
    from scripts.train_dense_autoencoder import write_outputs

    write_outputs(output_dir, model, scaler, 0.5, metadata, [])
    assert (output_dir / "dense_autoencoder.pt").is_file()
    assert (output_dir / "autoencoder_scaler.joblib").is_file()
    assert (output_dir / "autoencoder_threshold.json").is_file()
    assert (output_dir / "autoencoder_metadata.json").is_file()
    assert (output_dir / "training_history.json").is_file()

    from app.core.config import settings

    monkeypatch.setattr(settings, "MODELS_DIR", output_dir)
    service = ANNAnomalyService()
    result = service.predict([0.0] * len(FEATURE_NAMES))
    assert result is not None
    assert json.loads((output_dir / "autoencoder_metadata.json").read_text())["preprocessing"]["total_session_duration_policy"] == "zero"


def test_output_dir_cannot_be_production_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not"):
        validate_output_dir(Path(__file__).resolve().parents[1] / "artifacts")
    with pytest.raises(ValueError, match="must not"):
        validate_output_dir(Path(__file__).resolve().parents[1] / "artifacts" / "nested")


def test_checkpoint_and_inference_contract(tmp_path: Path) -> None:
    from sklearn.preprocessing import StandardScaler
    import joblib

    model = DenseAutoencoder(len(FEATURE_NAMES))
    model_path = tmp_path / "model.pt"
    scaler_path = tmp_path / "scaler.joblib"
    torch.save(model.state_dict(), model_path)
    scaler = StandardScaler().fit(np.ones((2, len(FEATURE_NAMES))))
    joblib.dump(scaler, scaler_path)
    validate_checkpoint(model_path, scaler_path)
