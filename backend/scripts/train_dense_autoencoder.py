"""Reproducible candidate trainer for the UEBA dense autoencoder.

This is a replacement training workflow, not a reconstruction of the missing
historical training program. It writes only to a candidate directory.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import platform
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ann_anomaly_service import DenseAutoencoder
from app.pipeline.schema import SCHEMA_VERSION


FEATURE_NAMES = [
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
]
HISTORICAL_COUNTS = {"train": 239737, "validation": 45105, "test": 45443}
HISTORICAL_BOUNDARIES = {
    "train_start": "2010-01-02",
    "train_end": "2010-12-17",
    "validation_start": "2010-12-18",
    "validation_end": "2011-03-02",
    "test_start": "2011-03-03",
    "test_end": "2011-05-17",
}


@dataclass(frozen=True)
class Split:
    name: str
    start: str
    end: str


def set_deterministic_seed(seed: int) -> None:
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False


def validate_feature_order(columns: Iterable[str]) -> None:
    actual = list(columns)
    if actual != FEATURE_NAMES:
        raise ValueError(
            "Feature order mismatch. Expected "
            f"{FEATURE_NAMES}, received {actual}."
        )


def validate_source_columns(columns: Iterable[str]) -> None:
    actual = list(columns)
    duplicates = sorted(
        {name for name in actual if actual.count(name) > 1}
        & set(FEATURE_NAMES)
    )
    if duplicates:
        raise ValueError(f"Input contains duplicate feature columns: {duplicates}")
    missing = [name for name in FEATURE_NAMES if name not in actual]
    if missing:
        raise ValueError(f"Input is missing required features: {missing}")


def load_features(path: Path, duration_policy: str, duration_value: float) -> pd.DataFrame:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        source_columns = next(csv.reader(source), [])
    validate_source_columns(source_columns)
    frame = pd.read_csv(path)
    if "date" not in frame:
        raise ValueError("Input must contain a date column for chronological splits.")

    validate_source_columns(frame.columns)
    values = frame.loc[:, FEATURE_NAMES].apply(pd.to_numeric, errors="coerce")
    duration_missing = values["total_session_duration"].isna()
    if duration_missing.any():
        if duration_policy == "reject":
            raise ValueError(
                f"{int(duration_missing.sum())} rows have missing "
                "total_session_duration; choose an explicit non-reject policy."
            )
        if duration_policy == "zero":
            values.loc[duration_missing, "total_session_duration"] = 0.0
        elif duration_policy == "constant":
            if not np.isfinite(duration_value) or duration_value < 0:
                raise ValueError("duration_value must be finite and nonnegative.")
            values.loc[duration_missing, "total_session_duration"] = duration_value
        else:
            raise ValueError(f"Unsupported duration policy: {duration_policy}")

    if values.isna().any().any():
        bad = values.columns[values.isna().any()].tolist()
        raise ValueError(f"Missing or non-numeric values remain in features: {bad}")
    array = values.to_numpy(dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("Feature inputs must all be finite.")
    if (array < 0).any():
        raise ValueError("Feature inputs must all be nonnegative.")

    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("Input contains invalid dates.")
    result = frame.copy()
    result["date"] = dates.dt.strftime("%Y-%m-%d")
    result[FEATURE_NAMES] = values
    return result


def split_rows(frame: pd.DataFrame, splits: Sequence[Split]) -> Dict[str, pd.DataFrame]:
    expected_names = ("train", "validation", "test")
    if tuple(split.name for split in splits) != expected_names:
        raise ValueError(
            f"Splits must be ordered and named {list(expected_names)}."
        )
    dates = pd.to_datetime(frame["date"])
    if dates.isna().any():
        raise ValueError("Split input contains invalid dates.")
    output: Dict[str, pd.DataFrame] = {}
    used = pd.Series(False, index=frame.index)
    previous_end: pd.Timestamp | None = None
    for split in splits:
        try:
            start = pd.Timestamp(split.start)
            end = pd.Timestamp(split.end)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Split {split.name} has invalid date boundaries: "
                f"{split.start!r} through {split.end!r}."
            ) from exc
        if start > end:
            raise ValueError(
                f"Split {split.name} has start date after end date: "
                f"{split.start} > {split.end}."
            )
        if previous_end is not None and start <= previous_end:
            raise ValueError(
                f"Split {split.name} is not chronological after the previous split."
            )
        mask = (dates >= start) & (dates <= end)
        if (used & mask).any():
            raise ValueError("Chronological split boundaries overlap.")
        if not mask.any():
            raise ValueError(
                f"Split {split.name} is empty for boundaries "
                f"{split.start} through {split.end}."
            )
        output[split.name] = frame.loc[mask].copy()
        used |= mask
        previous_end = end
    excluded = int((~used).sum())
    if excluded:
        raise ValueError(
            f"{excluded} rows fall outside the configured split boundaries; "
            "choose boundaries covering the complete input."
        )
    return output


def calibrate_threshold(validation_errors: np.ndarray) -> float:
    values = np.asarray(validation_errors, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("Validation errors must be a non-empty one-dimensional array.")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Validation errors must be finite and nonnegative.")
    return float(np.percentile(values, 99))


def transform_splits(
    splits: Mapping[str, pd.DataFrame],
) -> Tuple[Dict[str, np.ndarray], StandardScaler]:
    raw_train = splits["train"][FEATURE_NAMES].to_numpy(dtype=np.float64)
    scaler = StandardScaler()
    train_log = np.log1p(raw_train)
    train_scaled = scaler.fit_transform(train_log)
    if not np.isfinite(train_scaled).all():
        raise ValueError("Training preprocessing produced non-finite values.")
    transformed = {"train": train_scaled.astype(np.float32)}
    for name, frame in splits.items():
        if name == "train":
            continue
        values = scaler.transform(
            np.log1p(frame[FEATURE_NAMES].to_numpy(dtype=np.float64))
        )
        if not np.isfinite(values).all():
            raise ValueError(f"{name} preprocessing produced non-finite values.")
        transformed[name] = values.astype(np.float32)
    return transformed, scaler


def reconstruction_errors(model: DenseAutoencoder, values: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        tensor = torch.from_numpy(values)
        reconstruction = model(tensor)
        errors = torch.mean((tensor - reconstruction) ** 2, dim=1).cpu().numpy()
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
) -> Tuple[DenseAutoencoder, List[Dict[str, float]], int, int]:
    if max_epochs < 1 or patience < 1 or min_delta < 0:
        raise ValueError("max_epochs >= 1, patience >= 1, and min_delta >= 0 required.")
    set_deterministic_seed(seed)
    model = DenseAutoencoder(len(FEATURE_NAMES))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()
    train_tensor = torch.from_numpy(transformed["train"])
    validation_tensor = torch.from_numpy(transformed["validation"])
    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    best_state: Dict[str, torch.Tensor] | None = None
    history: List[Dict[str, float]] = []

    for epoch in range(1, max_epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_loss = criterion(model(train_tensor), train_tensor)
        train_loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = criterion(
                model(validation_tensor), validation_tensor
            )
        train_value = float(train_loss.item())
        validation_value = float(validation_loss.item())
        history.append(
            {
                "epoch": float(epoch),
                "train_loss": train_value,
                "validation_loss": validation_value,
            }
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


def validate_checkpoint(
    model_path: Path,
    scaler_path: Path,
    threshold_path: Path | None = None,
    input_dim: int = len(FEATURE_NAMES),
) -> None:
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    model = DenseAutoencoder(input_dim)
    model.load_state_dict(state)
    model.eval()
    scaler = joblib.load(scaler_path)
    if getattr(scaler, "n_features_in_", None) != input_dim:
        raise ValueError("Saved scaler is incompatible with the feature count.")
    probe = np.zeros((1, input_dim), dtype=np.float64)
    transformed = scaler.transform(np.log1p(probe))
    reconstruction_errors(model, transformed.astype(np.float32))
    if threshold_path is not None:
        threshold_data = json.loads(threshold_path.read_text(encoding="utf-8"))
        threshold = float(threshold_data["threshold"])
        if not np.isfinite(threshold) or threshold < 0:
            raise ValueError("Saved threshold is invalid.")


def validate_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.resolve()
    artifacts_dir = (ROOT / "backend" / "artifacts").resolve()
    if resolved == artifacts_dir or artifacts_dir in resolved.parents:
        raise ValueError(
            f"Candidate output must not target or be inside {artifacts_dir}."
        )
    return resolved


def jsonable_versions() -> Dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "pytorch": torch.__version__,
    }


def write_outputs(
    output_dir: Path,
    model: DenseAutoencoder,
    scaler: StandardScaler,
    threshold: float,
    metadata: Mapping[str, Any],
    history: Sequence[Mapping[str, float]],
) -> None:
    output_dir = validate_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / "dense_autoencoder.pt")
    joblib.dump(scaler, output_dir / "autoencoder_scaler.joblib")
    (output_dir / "autoencoder_threshold.json").write_text(
        json.dumps(
            {
                "threshold": threshold,
                "validation_percentile": 99.0,
                "validation_profiles": metadata["splits"]["validation"]["count"],
                "method": "99th percentile of validation reconstruction errors",
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
    validate_checkpoint(
        output_dir / "dense_autoencoder.pt",
        output_dir / "autoencoder_scaler.joblib",
        output_dir / "autoencoder_threshold.json",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "backend" / "artifacts" / "cert_user_day_features.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "backend" / "ann_candidates" / "dense_autoencoder",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument(
        "--total-session-duration-policy",
        choices=("reject", "zero", "constant"),
        required=True,
        help="Explicitly handle the unavailable duration feature; historical handling is unknown.",
    )
    parser.add_argument("--duration-fill-value", type=float, default=0.0)
    parser.add_argument("--train-end-date", default=HISTORICAL_BOUNDARIES["train_end"])
    parser.add_argument(
        "--validation-end-date", default=HISTORICAL_BOUNDARIES["validation_end"]
    )
    parser.add_argument("--test-end-date", default=HISTORICAL_BOUNDARIES["test_end"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.seed < 0:
        raise ValueError("seed must be nonnegative.")
    frame = load_features(
        args.input,
        args.total_session_duration_policy,
        args.duration_fill_value,
    )
    start = str(frame["date"].min())
    splits = split_rows(
        frame,
        [
            Split("train", start, args.train_end_date),
            Split(
                "validation",
                str((pd.Timestamp(args.train_end_date) + pd.Timedelta(days=1)).date()),
                args.validation_end_date,
            ),
            Split(
                "test",
                str((pd.Timestamp(args.validation_end_date) + pd.Timedelta(days=1)).date()),
                args.test_end_date,
            ),
        ],
    )
    for name, split in splits.items():
        print(
            f"{name}: count={len(split):,}, "
            f"date_start={split['date'].min()}, date_end={split['date'].max()}"
        )
        print(
            f"historical_count={HISTORICAL_COUNTS[name]:,}, "
            f"delta={len(split) - HISTORICAL_COUNTS[name]:+,} "
            "(historical row-selection rule unavailable)"
        )

    transformed, scaler = transform_splits(splits)
    model, history, best_epoch, stopping_epoch = train_model(
        transformed,
        args.seed,
        args.max_epochs,
        args.patience,
        args.min_delta,
        args.learning_rate,
    )
    validation_errors = reconstruction_errors(model, transformed["validation"])
    test_errors = reconstruction_errors(model, transformed["test"])
    threshold = calibrate_threshold(validation_errors)
    metadata = {
        "model_name": "dense_autoencoder",
        "model_version": "candidate-replacement-1",
        "schema_version": SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
        "architecture": [10, 32, 16, 8, 16, 32, 10],
        "preprocessing": {
            "transformation": "numpy.log1p",
            "scaler": "StandardScaler",
            "scaler_fitted_on": "training split only",
            "total_session_duration_policy": args.total_session_duration_policy,
            "total_session_duration_assumption": (
                "Missing total_session_duration values were explicitly replaced "
                "with zero; this is a candidate assumption, not historical behavior."
                if args.total_session_duration_policy == "zero"
                else None
            ),
            "total_session_duration_original_handling": "unknown",
            "duration_fill_value": (
                args.duration_fill_value
                if args.total_session_duration_policy == "constant"
                else None
            ),
        },
        "seed": args.seed,
        "early_stopping": {
            "max_epochs": args.max_epochs,
            "patience": args.patience,
            "min_delta": args.min_delta,
            "best_epoch": best_epoch,
            "stopping_epoch": stopping_epoch,
            "best_validation_loss": history[best_epoch - 1]["validation_loss"],
        },
        "threshold_calibration": {
            "percentile": 99.0,
            "source": "validation reconstruction errors only",
            "test_used_for_selection_or_calibration": False,
            "threshold": threshold,
        },
        "splits": {
            name: {
                "count": len(split),
                "date_start": split["date"].min(),
                "date_end": split["date"].max(),
                "historical_count": HISTORICAL_COUNTS[name],
                "count_delta_vs_historical": len(split) - HISTORICAL_COUNTS[name],
            }
            for name, split in splits.items()
        },
        "source_rows": len(frame),
        "historical_total_rows": sum(HISTORICAL_COUNTS.values()),
        "historical_discrepancy_explanation": (
            "The source has 330,452 unique user-day rows and the recorded "
            "historical counts sum to 330,285. The recorded date boundaries "
            "cover the full source and produce 239,854/45,138/45,460 rows. "
            "The missing 167-row selection rule cannot be determined from "
            "the available artifacts; this replacement retains all valid rows."
        ),
        "versions": jsonable_versions(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_reconstruction_error_mean": float(test_errors.mean()),
    }
    output_dir = validate_output_dir(args.output_dir)
    write_outputs(output_dir, model, scaler, threshold, metadata, history)
    print(f"Wrote candidate outputs to {output_dir}")


if __name__ == "__main__":
    main()
