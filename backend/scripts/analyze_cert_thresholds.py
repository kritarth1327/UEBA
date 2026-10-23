from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    average_precision_score, roc_auc_score, confusion_matrix,
    precision_recall_curve
)

warnings.filterwarnings("ignore")

DATA = Path("artifacts/cert_user_day_labeled.csv")
OUT = Path("artifacts/cert_threshold_analysis")
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
df["user_id"] = df["user_id"].astype(str).str.strip().str.upper()
df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

excluded = {
    "user_id", "date", "label", "label_source",
    "event_count", "anomalous_event_count",
    "first_event_at", "last_event_at"
}
features = [
    c for c in df.columns
    if c not in excluded and pd.api.types.is_numeric_dtype(df[c])
]
X = df[features].replace([np.inf, -np.inf], np.nan)
y = df["label"]
groups = df["user_id"]

# 25% test users; split remaining users into 80% train / 20% validation.
outer = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
trainval_idx, test_idx = next(outer.split(X, y, groups))

inner = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=43)
train_rel, val_rel = next(
    inner.split(X.iloc[trainval_idx], y.iloc[trainval_idx],
                groups.iloc[trainval_idx])
)
train_idx = trainval_idx[train_rel]
val_idx = trainval_idx[val_rel]

X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
X_val, y_val = X.iloc[val_idx], y.iloc[val_idx]
X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]

train_users = set(groups.iloc[train_idx])
val_users = set(groups.iloc[val_idx])
test_users = set(groups.iloc[test_idx])

print("=" * 70)
print("CERT R4.2 — VALIDATION THRESHOLD ANALYSIS")
print("=" * 70)
print("Rows:", len(df), "| Unique users:", groups.nunique())
print("Features:", features)
print(f"Train: {len(train_idx):,} rows, {len(train_users)} users, "
      f"labels={y_train.value_counts().sort_index().to_dict()}")
print(f"Validation: {len(val_idx):,} rows, {len(val_users)} users, "
      f"labels={y_val.value_counts().sort_index().to_dict()}")
print(f"Test: {len(test_idx):,} rows, {len(test_users)} users, "
      f"labels={y_test.value_counts().sort_index().to_dict()}")

assert not (train_users & val_users), "Train/validation user overlap!"
assert not (train_users & test_users), "Train/test user overlap!"
assert not (val_users & test_users), "Validation/test user overlap!"

if any(part.nunique() < 2 for part in [y_train, y_val, y_test]):
    raise RuntimeError(
        "At least one partition lacks a class. Do not report results; "
        "a different group split is required."
    )

models = {
    "random_forest": RandomForestClassifier(
        n_estimators=400,
        class_weight="balanced_subsample",
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
}

try:
    from xgboost import XGBClassifier
    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())
    models["xgboost"] = XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=1.0,
        scale_pos_weight=neg / max(pos, 1),
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
except ImportError:
    print("XGBoost unavailable; only Random Forest will be evaluated.")

def metric_record(y_true, scores, threshold):
    pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(
        y_true, pred, labels=[0, 1]
    ).ravel()
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "pr_auc_average_precision": float(
            average_precision_score(y_true, scores)
        ),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }

all_results = {}
all_predictions = pd.DataFrame({
    "user_id": groups.iloc[test_idx].to_numpy(),
    "date": df["date"].iloc[test_idx].to_numpy(),
    "y_true": y_test.to_numpy(),
})
pr_rows = []

for name, estimator in models.items():
    print(f"\n--- Fitting {name} ---")
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", estimator),
    ])
    pipeline.fit(X_train, y_train)

    val_scores = pipeline.predict_proba(X_val)[:, 1]
    precision, recall, thresholds = precision_recall_curve(y_val, val_scores)

    # Choose threshold maximizing validation F1. Test labels are not used.
    f1_values = (
        2 * precision[:-1] * recall[:-1]
        / (precision[:-1] + recall[:-1] + 1e-12)
    )
    best_idx = int(np.nanargmax(f1_values))
    best_threshold = float(thresholds[best_idx])

    val_metrics = metric_record(y_val, val_scores, best_threshold)
    test_scores = pipeline.predict_proba(X_test)[:, 1]
    test_metrics = metric_record(y_test, test_scores, best_threshold)

    # Save model, validation-selected threshold, and held-out predictions.
    joblib.dump(pipeline, OUT / f"{name}.joblib")
    all_predictions[f"{name}_score"] = test_scores
    all_predictions[f"{name}_prediction"] = (
        test_scores >= best_threshold
    ).astype(int)

    all_results[name] = {
        "selected_threshold": best_threshold,
        "threshold_selection": "Maximum validation F1",
        "validation_metrics_at_selected_threshold": val_metrics,
        "test_metrics_at_selected_threshold": test_metrics,
        "test_confusion_matrix": [
            [test_metrics["tn"], test_metrics["fp"]],
            [test_metrics["fn"], test_metrics["tp"]],
        ],
    }

    print("Selected validation threshold:", round(best_threshold, 6))
    print("Validation F1:", round(val_metrics["f1"], 4))
    print("TEST results at selected threshold:")
    for metric in [
        "precision", "recall", "f1", "pr_auc_average_precision",
        "roc_auc", "accuracy", "fp", "fn", "tp", "tn"
    ]:
        print(f"  {metric}: {test_metrics[metric]}")
    print("Test confusion matrix [[TN, FP], [FN, TP]]:")
    print(all_results[name]["test_confusion_matrix"])

    # Threshold comparison on validation only.
    for threshold in sorted(set(
        [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50,
         best_threshold]
    )):
        row = metric_record(y_val, val_scores, threshold)
        row["model"] = name
        row["selected_threshold"] = (
            abs(threshold - best_threshold) < 1e-12
        )
        pr_rows.append(row)

    # Test-set PR curve is for reporting only, not threshold selection.
    test_precision, test_recall, _ = precision_recall_curve(
        y_test, test_scores
    )
    plt.plot(
        test_recall, test_precision,
        label=f"{name} (AP={test_metrics['pr_auc_average_precision']:.3f})"
    )

plt.xlabel("Recall")
plt.ylabel("Precision")
plt.title("CERT r4.2 — Held-out Test Precision–Recall Curve")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "test_precision_recall_curve.png", dpi=180)
plt.close()

all_predictions.to_csv(OUT / "test_predictions.csv", index=False)
pd.DataFrame(pr_rows).to_csv(OUT / "validation_threshold_comparison.csv", index=False)

report = {
    "dataset": "CERT r4.2",
    "split": "User-grouped: 60% train, 15% validation, 25% test",
    "random_seeds": {"outer": 42, "inner": 43},
    "user_overlap": {
        "train_validation": len(train_users & val_users),
        "train_test": len(train_users & test_users),
        "validation_test": len(val_users & test_users),
    },
    "label_caveat": (
        "Labels represent calendar-day overlap with official CERT incident "
        "windows. Outside-window days are provisional negatives, not "
        "verified benign. Metrics measure incident-window proxy classification, "
        "not validated insider-threat detection."
    ),
    "features": features,
    "results": all_results,
}
(OUT / "metrics.json").write_text(json.dumps(report, indent=2))

print("\nSaved outputs to:", OUT)
print("- metrics.json")
print("- validation_threshold_comparison.csv")
print("- test_predictions.csv")
print("- test_precision_recall_curve.png")
print("\nThresholds were selected using validation data only.")
print("Test metrics were not used to choose thresholds.")
print("Interpret all results as incident-window proxy classification.")
