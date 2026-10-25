
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.pipeline.adapters.base import IngestStats
from app.pipeline.adapters.spedia import SpediaAdapter
from app.pipeline.features import BusinessHours, DailyAggregator
from app.pipeline.schema import FEATURE_NAMES, SCHEMA_VERSION, SPEDIA, available_features

DATA_PATH = ROOT / "data" / "raw" / "spedia" / "logs_SPEDIA_annotated_en.csv"
OUTPUT_DIR = ROOT / "backend" / "artifacts"
CHUNK_SIZE = 50_000
RANDOM_STATE = 42


def load_spedia_daily() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"SPEDIA dataset not found: {DATA_PATH}")

    adapter = SpediaAdapter()
    stats = IngestStats()
    aggregator = DailyAggregator(
        available=available_features(SPEDIA),
        bh=BusinessHours(
            weekend_is_after_hours=adapter.weekend_is_after_hours
        ),
        has_labels=True,
    )

    for events in adapter.iter_events(DATA_PATH, CHUNK_SIZE, stats):
        aggregator.add_chunk(events)

    daily = aggregator.finalize()
    print(
        f"SPEDIA ingestion: read={stats.rows_read:,}, "
        f"accepted={stats.rows_accepted:,}, rejected={stats.rows_rejected:,}"
    )

    if daily.empty:
        raise ValueError("No daily records were produced.")

    # This is a source-label target, not a verified threat label.
    daily["source_label"] = (
        daily["anomalous_event_count"] > daily["event_count"] / 2
    ).astype("int8")

    return daily


def evaluate(model, X_test, y_test) -> dict:
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "confusion_matrix_labels_0_1": confusion_matrix(
            y_test, predictions, labels=[0, 1]
        ).tolist(),
        "classification_report": classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["source_label_0", "source_label_1"],
            output_dict=True,
            zero_division=0,
        ),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = load_spedia_daily()

    # Exclude IDs, dates, labels, and bookkeeping fields from model inputs.
    feature_names = [
        name
        for name in FEATURE_NAMES
        if name in daily.columns and daily[name].notna().any()
    ]

    X = daily[feature_names].replace([np.inf, -np.inf], np.nan)
    y = daily["source_label"].astype(int)
    groups = daily["user_id"].astype(str)

    print(f"Daily records: {len(daily):,}")
    print(f"Unique users: {groups.nunique():,}")
    print(f"Feature count: {len(feature_names)}")
    print(f"Target distribution: {y.value_counts().sort_index().to_dict()}")

    splitter = GroupShuffleSplit(
        n_splits=1, test_size=0.25, random_state=RANDOM_STATE
    )
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    if y_train.nunique() != 2 or y_test.nunique() != 2:
        raise ValueError(
            "User-grouped split lacks one or more classes. "
            "Inspect the source-label/user relationship before changing the split."
        )

    # RF can use imputation; the production Booster must accept the raw
    # schema-ordered feature vector with NaNs, matching MLThreatService.
    rf = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    rf.fit(X_train, y_train)
    rf_metrics = evaluate(rf, X_test, y_test)
    print("\nRandom Forest")
    print(json.dumps(rf_metrics, indent=2))
    import joblib
    joblib.dump(rf, OUTPUT_DIR / "random_forest.joblib")

    # Native XGBoost consumes raw numeric features and supports NaNs.
    dtrain = xgb.DMatrix(
        X_train.to_numpy(dtype=np.float32),
        label=y_train.to_numpy(),
        feature_names=feature_names,
        missing=np.nan,
    )
    dtest = xgb.DMatrix(
        X_test.to_numpy(dtype=np.float32),
        label=y_test.to_numpy(),
        feature_names=feature_names,
        missing=np.nan,
    )

    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "max_depth": 5,
        "eta": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "seed": RANDOM_STATE,
        "nthread": 4,
    }
    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=300,
        evals=[(dtest, "validation")],
        verbose_eval=False,
    )

    probabilities = booster.predict(dtest)
    predictions = (probabilities >= 0.5).astype(int)
    xgb_metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "confusion_matrix_labels_0_1": confusion_matrix(
            y_test, predictions, labels=[0, 1]
        ).tolist(),
        "classification_report": classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["source_label_0", "source_label_1"],
            output_dict=True,
            zero_division=0,
        ),
    }

    booster_path = OUTPUT_DIR / "xgboost_threat_classifier.json"
    booster.save_model(str(booster_path))

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "feature_names": feature_names,
        "model_version": "1.0.0",
        "target": "source_label",
        "target_warning": (
            "SPEDIA Anomaly represents log source/agent identity, not verified "
            "malicious behaviour. Do not interpret the score as a validated "
            "insider-threat probability."
        ),
        "threshold": 0.5,
        "training_dataset": "SPEDIA",
    }
    (OUTPUT_DIR / "xgboost_threat_classifier.meta.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    results = {
        "dataset": "SPEDIA",
        "target": "source_label",
        "warning": metadata["target_warning"],
        "schema_version": SCHEMA_VERSION,
        "feature_names": feature_names,
        "split": {
            "method": "GroupShuffleSplit",
            "test_size": 0.25,
            "random_state": RANDOM_STATE,
            "train_users": int(groups.iloc[train_idx].nunique()),
            "test_users": int(groups.iloc[test_idx].nunique()),
        },
        "models": {
            "random_forest": rf_metrics,
            "xgboost": xgb_metrics,
        },
    }

    metrics_path = OUTPUT_DIR / "supervised_metrics.json"
    metrics_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\nXGBoost")
    print(json.dumps(xgb_metrics, indent=2))
    print(f"\nSaved model: {booster_path}")
    print(f"Saved metadata: {booster_path.with_suffix('.meta.json')}")
    print(f"Saved metrics: {metrics_path}")
    print("\nThese results evaluate SPEDIA source-label prediction only.")


if __name__ == "__main__":
    main()
