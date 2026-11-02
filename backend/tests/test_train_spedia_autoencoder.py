import hashlib
import json
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from scripts.train_spedia_autoencoder import (  # noqa: E402
    FEATURE_NAMES,
    SpediaAutoencoder,
    calibrate_threshold,
    load_annotation_clean_profiles,
    split_chronologically,
    train_model,
    transform_splits,
    validate_artifacts,
    write_outputs,
)


def _row(user: str, day: str, anomaly: int = 0) -> dict:
    return {
        "user_id": user,
        "date": day,
        "event_count": 10,
        "anomalous_event_count": anomaly,
        "features_json": json.dumps({"features": {name: 1.0 for name in FEATURE_NAMES}}),
    }


def _database(path: Path, rows: list[dict]) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "create table daily_behavior_profiles "
        "(user_id text, date text, event_count integer, anomalous_event_count integer, "
        "features_json text, dataset_source text)"
    )
    con.executemany(
        "insert into daily_behavior_profiles values (?, ?, ?, ?, ?, 'spedia')",
        [
            (r["user_id"], r["date"], r["event_count"], r["anomalous_event_count"], r["features_json"])
            for r in rows
        ],
    )
    con.commit()
    con.close()


def test_exact_spedia_feature_order() -> None:
    assert FEATURE_NAMES == [
        "logon_count", "after_hours_logons", "failed_logon_count",
        "file_access_count", "file_integrity_event_count", "email_count",
        "email_external_count", "email_attachment_count", "email_total_bytes",
        "http_request_count", "http_after_hours_count", "removable_device_events",
        "command_exec_count", "after_hours_event_count",
    ]
    assert len(SpediaAutoencoder().encoder[0].weight[0]) == 14


def test_missing_and_invalid_features_are_rejected(tmp_path: Path) -> None:
    rows = [_row("u", "2025-01-01")]
    payload = json.loads(rows[0]["features_json"])
    del payload["features"]["command_exec_count"]
    rows[0]["features_json"] = json.dumps(payload)
    path = tmp_path / "ueba.db"
    _database(path, rows)
    with pytest.raises(ValueError, match="missing or non-numeric"):
        load_annotation_clean_profiles(path)

    rows = [_row("u", "2025-01-01")]
    payload = json.loads(rows[0]["features_json"])
    payload["features"]["email_count"] = -1
    rows[0]["features_json"] = json.dumps(payload)
    path = tmp_path / "invalid.db"
    _database(path, rows)
    with pytest.raises(ValueError, match="nonnegative"):
        load_annotation_clean_profiles(path)


def test_annotation_clean_selection_excludes_annotated_rows(tmp_path: Path) -> None:
    path = tmp_path / "ueba.db"
    _database(path, [_row("u", "2025-01-01"), _row("u", "2025-01-02", anomaly=1)])
    frame = load_annotation_clean_profiles(path)
    assert len(frame) == 1
    assert frame.iloc[0]["anomalous_event_count"] == 0


def test_chronological_split_rejects_insufficient_data() -> None:
    frame = pd.DataFrame(
        [{"user_id": "u", "date": pd.Timestamp("2025-01-01"), **{n: 1.0 for n in FEATURE_NAMES}}]
    )
    with pytest.raises(ValueError, match="Insufficient"):
        split_chronologically(frame, "2025-01-01", "2025-01-02")


def test_scaler_is_fit_on_training_rows_only() -> None:
    rows = []
    for i, value in enumerate([1.0, 3.0, 1000.0]):
        rows.append({"user_id": "u", "date": pd.Timestamp(f"2025-01-0{i + 1}"), **{n: value for n in FEATURE_NAMES}})
    frame = pd.DataFrame(rows)
    splits = {"train": frame.iloc[:2], "validation": frame.iloc[2:], "test": frame.iloc[2:]}
    transformed, scaler = transform_splits(splits)
    assert scaler.mean_[0] == pytest.approx(np.log1p([1.0, 3.0]).mean())
    assert transformed["validation"][0, 0] > 1.0


def test_artifact_generation_reload_and_cert_isolation(tmp_path: Path) -> None:
    output = tmp_path / "spedia_dense_autoencoder"
    values = np.ones((4, len(FEATURE_NAMES)), dtype=np.float32)
    transformed = {"train": values, "validation": values, "test": values}
    model, history, _, _ = train_model(
        transformed, seed=42, max_epochs=3, patience=2, min_delta=0.0,
        learning_rate=1e-3, weight_decay=1e-4,
    )
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler().fit(np.ones((4, len(FEATURE_NAMES))))
    write_outputs(
        output, model, scaler, calibrate_threshold(np.array([0.1, 0.2])),
        {"splits": {"validation": {"records": 2}}, "feature_names": FEATURE_NAMES},
        history,
    )
    validate_artifacts(output)
    reloaded = SpediaAutoencoder()
    reloaded.load_state_dict(torch.load(output / "dense_autoencoder.pt", weights_only=True))
    assert getattr(joblib.load(output / "autoencoder_scaler.joblib"), "n_features_in_") == 14
    assert (output / "autoencoder_threshold.json").is_file()
    assert (output / "autoencoder_metadata.json").is_file()
    cert_dir = Path(__file__).resolve().parents[1] / "artifacts"
    cert_hash_before = hashlib.sha256(
        (cert_dir / "dense_autoencoder.pt").read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError, match="separate directory"):
        write_outputs(
            cert_dir, model, scaler, 0.5,
            {"splits": {"validation": {"records": 2}}},
            history,
        )
    cert_hash_after = hashlib.sha256(
        (cert_dir / "dense_autoencoder.pt").read_bytes()
    ).hexdigest()
    assert cert_hash_after == cert_hash_before


def test_threshold_and_scaler_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        calibrate_threshold(np.array([]))
    output = tmp_path / "bad"
    output.mkdir()
    torch.save(SpediaAutoencoder().state_dict(), output / "dense_autoencoder.pt")
    joblib.dump(__import__("sklearn").preprocessing.StandardScaler().fit(np.ones((2, 13))), output / "autoencoder_scaler.joblib")
    (output / "autoencoder_threshold.json").write_text('{"threshold": 1}')
    (output / "autoencoder_metadata.json").write_text("{}")
    with pytest.raises(ValueError, match="dimension"):
        validate_artifacts(output)
