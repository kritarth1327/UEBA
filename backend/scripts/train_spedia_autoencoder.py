"""Train an isolated experimental autoencoder from persisted SPEDIA profiles.

This script reads user-day profiles already stored in the application database.
It never re-ingests raw events and writes only to the SPEDIA artifact directory.
The annotation-clean rule is a provenance filter, not verified maliciousness
ground truth: only rows with anomalous_event_count == 0 are used for training,
validation, and threshold calibration.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import random
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = ROOT / "backend" / "ueba.db"
DEFAULT_OUTPUT = ROOT / "backend" / "artifacts" / "spedia_dense_autoencoder"
DATASET = "spedia"
SCHEMA_VERSION = "1.0.0"
FEATURE_NAMES = [
    "logon_count",
    "after_hours_logons",
    "failed_logon_count",
    "file_access_count",
    "file_integrity_event_count",
    "email_count",
    "email_external_count",
    "email_attachment_count",
    "email_total_bytes",
    "http_request_count",
    "http_after_hours_count",
    "removable_device_events",
    "command_exec_count",
    "after_hours_event_count",
]
MIN_SPLIT_COUNTS = {"train": 30, "validation": 10, "test": 10}
BENIGN_RULE = (
    "dataset_source == 'spedia' and anomalous_event_count == 0 and "
    "event_count > 0; this is annotation-clean/provenance-normal, not "
    "verified benign or malicious ground truth"
)


class SpediaAutoencoder(nn.Module):
    """Compact 14 -> 8 -> 4 -> 8 -> 14 autoencoder."""

    def __init__(self, input_dim: int = len(FEATURE_NAMES)):
        super().__init__()
        if input_dim != len(FEATURE_NAMES):
            raise ValueError(f"SPEDIA autoencoder requires {len(FEATURE_NAMES)} features.")
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 8),
            nn.ReLU(),
            nn.Linear(8, 4),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(4, 8),
            nn.ReLU(),
            nn.Linear(8, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


def set_seed(seed: int) -> None:
    if seed < 0:
        raise ValueError("seed must be nonnegative.")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def _validate_feature_values(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [name for name in FEATURE_NAMES if name not in frame.columns]
    if missing:
        raise ValueError(f"Database records are missing SPEDIA features: {missing}")
    values = frame.loc[:, FEATURE_NAMES].apply(pd.to_numeric, errors="coerce")
    if values.isna().any().any():
        bad = values.columns[values.isna().any()].tolist()
        raise ValueError(f"SPEDIA features contain missing or non-numeric values: {bad}")
    array = values.to_numpy(dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("SPEDIA features must be finite.")
    if (array < 0).any():
        raise ValueError("SPEDIA features must be nonnegative.")
    return values


def load_annotation_clean_profiles(database: Path) -> pd.DataFrame:
    """Load persisted SPEDIA features without re-ingesting the raw CSV."""
    if not database.is_file():
        raise FileNotFoundError(f"SPEDIA database not found: {database}")
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            """
            SELECT user_id, date, event_count, anomalous_event_count, features_json
            FROM daily_behavior_profiles
            WHERE dataset_source = 'spedia'
            ORDER BY date, user_id
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError(f"Could not read SPEDIA profiles from {database}: {exc}") from exc
    finally:
        connection.close()

    records = []
    for user_id, date_value, event_count, anomalous_count, payload in rows:
        if event_count is None or int(event_count) <= 0:
            continue
        if anomalous_count != 0:
            continue
        try:
            features = json.loads(payload or "{}").get("features")
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid features_json for {user_id} on {date_value}") from exc
        if not isinstance(features, dict):
            raise ValueError(f"Missing features object for {user_id} on {date_value}")
        records.append(
            {
                "user_id": str(user_id),
                "date": str(date_value),
                "event_count": int(event_count),
                "anomalous_event_count": int(anomalous_count),
                **{name: features.get(name) for name in FEATURE_NAMES},
            }
        )

    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("No annotation-clean SPEDIA user-day profiles are available.")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any():
        raise ValueError("SPEDIA profiles contain invalid dates.")
    frame[FEATURE_NAMES] = _validate_feature_values(frame)
    return frame.sort_values(["date", "user_id"]).reset_index(drop=True)


def split_chronologically(
    frame: pd.DataFrame,
    train_end: str,
    validation_end: str,
) -> Dict[str, pd.DataFrame]:
    train_end_date = pd.Timestamp(train_end)
    validation_end_date = pd.Timestamp(validation_end)
    if train_end_date >= validation_end_date:
        raise ValueError("train_end must be before validation_end.")
    dates = frame["date"]
    masks = {
        "train": dates <= train_end_date,
        "validation": (dates > train_end_date) & (dates <= validation_end_date),
        "test": dates > validation_end_date,
    }
    splits = {name: frame.loc[mask].copy() for name, mask in masks.items()}
    insufficient = {
        name: {"records": len(part), "required": MIN_SPLIT_COUNTS[name]}
        for name, part in splits.items()
        if len(part) < MIN_SPLIT_COUNTS[name]
    }
    if insufficient:
        raise ValueError(
            "Insufficient annotation-clean SPEDIA data for a meaningful "
            f"chronological split: {insufficient}"
        )
    return splits


def transform_splits(
    splits: Mapping[str, pd.DataFrame],
) -> Tuple[Dict[str, np.ndarray], StandardScaler]:
    train_values = splits["train"][FEATURE_NAMES].to_numpy(dtype=np.float64)
    scaler = StandardScaler()
    transformed: Dict[str, np.ndarray] = {}
    transformed["train"] = scaler.fit_transform(np.log1p(train_values)).astype(np.float32)
    for name in ("validation", "test"):
        values = splits[name][FEATURE_NAMES].to_numpy(dtype=np.float64)
        transformed[name] = scaler.transform(np.log1p(values)).astype(np.float32)
    if not all(np.isfinite(values).all() for values in transformed.values()):
        raise ValueError("SPEDIA preprocessing produced non-finite values.")
    return transformed, scaler


def reconstruction_errors(model: SpediaAutoencoder, values: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        tensor = torch.from_numpy(values)
        errors = torch.mean((tensor - model(tensor)) ** 2, dim=1).numpy()
    if not np.isfinite(errors).all() or (errors < 0).any():
        raise ValueError("Model produced invalid reconstruction errors.")
    return errors


def train_model(
    transformed: Mapping[str, np.ndarray],
    seed: int,
    max_epochs: int,
    patience: int,
    min_delta: float,
    learning_rate: float,
    weight_decay: float,
) -> Tuple[SpediaAutoencoder, list[dict[str, float]], int, int]:
    if max_epochs < 1 or patience < 1 or min_delta < 0 or weight_decay < 0:
        raise ValueError("Invalid training hyperparameters.")
    set_seed(seed)
    model = SpediaAutoencoder()
    optimizer = torch.optim.Adam(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    criterion = nn.MSELoss()
    train_tensor = torch.from_numpy(transformed["train"])
    validation_tensor = torch.from_numpy(transformed["validation"])
    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, float]] = []

    for epoch in range(1, max_epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_loss = criterion(model(train_tensor), train_tensor)
        train_loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = criterion(model(validation_tensor), validation_tensor)
        train_value = float(train_loss.item())
        validation_value = float(validation_loss.item())
        history.append(
            {"epoch": float(epoch), "train_loss": train_value, "validation_loss": validation_value}
        )
        if validation_value < best_loss - min_delta:
            best_loss = validation_value
            best_epoch = epoch
            stale_epochs = 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale_epochs += 1
        if stale_epochs >= patience:
            break
    if best_state is None:
        raise RuntimeError("No validation checkpoint was produced.")
    model.load_state_dict(best_state)
    return model, history, best_epoch, len(history)


def calibrate_threshold(validation_errors: np.ndarray) -> float:
    values = np.asarray(validation_errors, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("Validation errors must be a non-empty vector.")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Validation errors must be finite and nonnegative.")
    return float(np.percentile(values, 99.0))


def _error_summary(errors: np.ndarray, threshold: float) -> Dict[str, Any]:
    exceeded = int((errors > threshold).sum())
    return {
        "count": int(errors.size),
        "mean": float(errors.mean()),
        "std": float(errors.std()),
        "min": float(errors.min()),
        "median": float(np.percentile(errors, 50)),
        "p95": float(np.percentile(errors, 95)),
        "p99": float(np.percentile(errors, 99)),
        "max": float(errors.max()),
        "threshold_exceeded": exceeded,
        "threshold_exceeded_percentage": float(100 * exceeded / errors.size),
    }


def _grouped_report(frame: pd.DataFrame, errors: np.ndarray, threshold: float) -> Dict[str, Any]:
    scored = frame[["user_id", "date"]].copy()
    scored["reconstruction_error"] = errors
    scored["threshold_exceeded"] = errors > threshold
    by_user = {}
    for user, group in scored.groupby("user_id"):
        by_user[str(user)] = {
            "records": int(len(group)),
            "threshold_exceeded": int(group["threshold_exceeded"].sum()),
            "mean_reconstruction_error": float(group["reconstruction_error"].mean()),
        }
    by_date = {}
    for date_value, group in scored.groupby("date"):
        by_date[str(date_value.date())] = {
            "records": int(len(group)),
            "threshold_exceeded": int(group["threshold_exceeded"].sum()),
            "mean_reconstruction_error": float(group["reconstruction_error"].mean()),
        }
    return {"by_user": by_user, "by_date": by_date}


def _split_metadata(frame: pd.DataFrame) -> Dict[str, Any]:
    return {
        "records": int(len(frame)),
        "users": int(frame["user_id"].nunique()),
        "date_start": str(frame["date"].min().date()),
        "date_end": str(frame["date"].max().date()),
    }


def _artifact_hashes(directory: Path) -> Dict[str, str]:
    result = {}
    for path in sorted(directory.glob("*")):
        if path.is_file():
            result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def write_outputs(
    output_dir: Path,
    model: SpediaAutoencoder,
    scaler: StandardScaler,
    threshold: float,
    metadata: Mapping[str, Any],
    history: Sequence[Mapping[str, float]],
) -> None:
    resolved = output_dir.resolve()
    cert_dir = (ROOT / "backend" / "artifacts").resolve()
    if resolved == cert_dir:
        raise ValueError("SPEDIA output must be a separate directory, not the CERT artifact directory.")
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / "dense_autoencoder.pt")
    joblib.dump(scaler, output_dir / "autoencoder_scaler.joblib")
    (output_dir / "autoencoder_threshold.json").write_text(
        json.dumps(
            {
                "threshold": threshold,
                "validation_percentile": 99.0,
                "validation_profiles": metadata["splits"]["validation"]["records"],
                "method": "99th percentile of annotation-clean validation reconstruction errors",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "autoencoder_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    (output_dir / "training_history.json").write_text(
        json.dumps(list(history), indent=2),
        encoding="utf-8",
    )


def validate_artifacts(output_dir: Path) -> None:
    required = [
        output_dir / "dense_autoencoder.pt",
        output_dir / "autoencoder_scaler.joblib",
        output_dir / "autoencoder_threshold.json",
        output_dir / "autoencoder_metadata.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"SPEDIA artifact(s) missing: {missing}")
    model = SpediaAutoencoder()
    state = torch.load(output_dir / "dense_autoencoder.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    scaler = joblib.load(output_dir / "autoencoder_scaler.joblib")
    if getattr(scaler, "n_features_in_", None) != len(FEATURE_NAMES):
        raise ValueError("SPEDIA scaler dimension does not match 14 features.")
    threshold = float(json.loads((output_dir / "autoencoder_threshold.json").read_text())["threshold"])
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("SPEDIA threshold is invalid.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--train-end-date", default="2025-03-20")
    parser.add_argument("--validation-end-date", default="2025-03-25")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-epochs", type=int, default=500)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profiles = load_annotation_clean_profiles(args.database)
    splits = split_chronologically(profiles, args.train_end_date, args.validation_end_date)
    print(f"annotation-clean SPEDIA profiles: {len(profiles):,}; users: {profiles.user_id.nunique():,}")
    for name, split in splits.items():
        print(
            f"{name}: records={len(split):,}, users={split.user_id.nunique():,}, "
            f"dates={split.date.min().date()}..{split.date.max().date()}"
        )

    transformed, scaler = transform_splits(splits)
    model, history, best_epoch, stopping_epoch = train_model(
        transformed, args.seed, args.max_epochs, args.patience, args.min_delta,
        args.learning_rate, args.weight_decay,
    )
    train_errors = reconstruction_errors(model, transformed["train"])
    validation_errors = reconstruction_errors(model, transformed["validation"])
    test_errors = reconstruction_errors(model, transformed["test"])
    threshold = calibrate_threshold(validation_errors)
    evaluation = {
        name: {
            "errors": _error_summary(errors, threshold),
            **_grouped_report(splits[name], errors, threshold),
        }
        for name, errors in (
            ("train", train_errors),
            ("validation", validation_errors),
            ("test", test_errors),
        )
    }
    metadata = {
        "model_name": "spedia_dense_autoencoder",
        "model_version": "spedia-experimental-1",
        "experimental_model_status": "experimental; not validated insider-threat detection",
        "dataset": DATASET,
        "dataset_provenance": {
            "source": "persisted daily_behavior_profiles in the application database",
            "database": str(args.database.resolve()),
            "raw_reingestion": False,
            "annotation_label_limitation": (
                "Anomaly/anomalous_event_count reflect dataset annotation/provenance "
                "and are not verified malicious-behaviour ground truth."
            ),
        },
        "schema_version": SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
        "architecture": [14, 8, 4, 8, 14],
        "preprocessing": {
            "transformation": "numpy.log1p",
            "scaler": "StandardScaler",
            "scaler_fitted_on": "annotation-clean training split only",
            "missing_value_policy": "reject missing or invalid values",
        },
        "seed": args.seed,
        "regularization": {"optimizer": "Adam", "weight_decay": args.weight_decay},
        "early_stopping": {
            "max_epochs": args.max_epochs,
            "patience": args.patience,
            "min_delta": args.min_delta,
            "best_epoch": best_epoch,
            "stopping_epoch": stopping_epoch,
            "best_train_loss": history[best_epoch - 1]["train_loss"],
            "best_validation_loss": history[best_epoch - 1]["validation_loss"],
        },
        "benign_row_selection_rule": BENIGN_RULE,
        "splits": {name: _split_metadata(split) for name, split in splits.items()},
        "threshold_calibration": {
            "percentile": 99.0,
            "source": "validation reconstruction errors only",
            "test_used_for_selection_or_calibration": False,
            "threshold": threshold,
        },
        "evaluation": evaluation,
        "limitations": [
            "Annotation-clean means anomalous_event_count == 0; it is not verified benign ground truth.",
            "SPEDIA has a short and uneven chronological coverage with few users.",
            "The 2026 tail in the persisted database is a separate late period and is retained in test without random mixing.",
            "Results are experimental and must not be presented as validated insider-threat detection performance.",
        ],
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "pytorch": torch.__version__,
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_outputs(args.output_dir, model, scaler, threshold, metadata, history)
    validate_artifacts(args.output_dir)
    print(f"threshold: {threshold:.8f}")
    for name in ("train", "validation", "test"):
        summary = evaluation[name]["errors"]
        print(
            f"{name} loss={metadata['early_stopping']['best_' + ('train' if name == 'train' else 'validation') + '_loss'] if name != 'test' else summary['mean']:.8f}; "
            f"mean_error={summary['mean']:.8f}; exceeded={summary['threshold_exceeded']}/{summary['count']} "
            f"({summary['threshold_exceeded_percentage']:.2f}%)"
        )
    print(f"wrote SPEDIA artifacts to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
