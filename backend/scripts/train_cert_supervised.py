from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    average_precision_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

warnings.filterwarnings("ignore", category=UserWarning)

DATA_PATH = Path("artifacts/cert_user_day_labeled.csv")
OUT_DIR = Path("artifacts/cert_supervised")
OUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_PATH)
df["user_id"] = df["user_id"].astype(str).str.strip().str.upper()
df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

excluded = {
    "user_id", "date", "label", "label_source",
    "event_count", "anomalous_event_count",
    "first_event_at", "last_event_at",
    "failed_logon_count", "file_access_count",
    "file_integrity_event_count", "total_session_duration",
    "command_exec_count",
}
feature_cols = [
    c for c in df.columns
    if c not in excluded and pd.api.types.is_numeric_dtype(df[c])
]

if not feature_cols:
    raise ValueError("No numeric model features found.")

X = df[feature_cols].replace([np.inf, -np.inf], np.nan)
y = df["label"]
groups = df["user_id"]

# Fixed user-grouped split; test users are never used for training.
splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
train_idx, test_idx = next(splitter.split(X, y, groups=groups))

X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
train_users = set(groups.iloc[train_idx])
test_users = set(groups.iloc[test_idx])

print("=" * 68)
print("CERT R4.2 SUPERVISED BASELINE")
print("=" * 68)
print("Rows:", len(df), "| Users:", groups.nunique())
print("Features:", feature_cols)
print("Train rows/users:", len(train_idx), "/", len(train_users))
print("Test rows/users:", len(test_idx), "/", len(test_users))
print("Train labels:", y_train.value_counts().sort_index().to_dict())
print("Test labels:", y_test.value_counts().sort_index().to_dict())
print("User overlap:", len(train_users & test_users))

if len(train_users & test_users):
    raise RuntimeError("User leakage detected in grouped split.")

if y_train.nunique() < 2 or y_test.nunique() < 2:
    raise RuntimeError(
        "Grouped split does not contain both classes in train and test. "
        "Do not report metrics; revise the split strategy."
    )

# Fit imputation using training data only.
preprocessor = ColumnTransformer(
    transformers=[
        ("numeric", SimpleImputer(strategy="median"), feature_cols)
    ],
    remainder="drop",
)

models = {
    "random_forest": RandomForestClassifier(
        n_estimators=400,
        class_weight="balanced_subsample",
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    ),
}

try:
    from xgboost import XGBClassifier

    negatives = int((y_train == 0).sum())
    positives = int((y_train == 1).sum())

    models["xgboost"] = XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=1.0,
        scale_pos_weight=negatives / max(positives, 1),
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
except ImportError:
    print("XGBoost is not installed; training Random Forest only.")

results = {}
predictions = pd.DataFrame({
    "user_id": groups.iloc[test_idx].to_numpy(),
    "date": df["date"].iloc[test_idx].to_numpy(),
    "y_true": y_test.to_numpy(),
})

for name, estimator in models.items():
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", estimator),
    ])

    print(f"\n--- Training {name} ---")
    pipeline.fit(X_train, y_train)

    pred = pipeline.predict(X_test)
    scores = pipeline.predict_proba(X_test)[:, 1]
    cm = confusion_matrix(y_test, pred, labels=[0, 1])

    metrics = {
        "accuracy": float(accuracy_score(y_test, pred)),
        "precision": float(precision_score(y_test, pred, zero_division=0)),
        "recall": float(recall_score(y_test, pred, zero_division=0)),
        "f1": float(f1_score(y_test, pred, zero_division=0)),
        "pr_auc_average_precision": float(average_precision_score(y_test, scores)),
        "roc_auc": float(roc_auc_score(y_test, scores)),
        "confusion_matrix_labels_0_1": cm.tolist(),
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "train_users": int(len(train_users)),
        "test_users": int(len(test_users)),
        "features": feature_cols,
        "label_caveat": (
            "Positive labels represent calendar days overlapping official "
            "CERT r4.2 incident windows. Days outside these windows are "
            "provisional negatives, not verified benign labels. Results "
            "measure incident-window proxy classification, not validated "
            "insider-threat detection."
        ),
    }

    results[name] = metrics
    predictions[f"{name}_prediction"] = pred
    predictions[f"{name}_score"] = scores

    joblib.dump(pipeline, OUT_DIR / f"{name}.joblib")

    print("Accuracy:", round(metrics["accuracy"], 4))
    print("Precision:", round(metrics["precision"], 4))
    print("Recall:", round(metrics["recall"], 4))
    print("F1:", round(metrics["f1"], 4))
    print("PR-AUC:", round(metrics["pr_auc_average_precision"], 4))
    print("ROC-AUC:", round(metrics["roc_auc"], 4))
    print("Confusion matrix [[TN, FP], [FN, TP]]:")
    print(cm)
    print(classification_report(y_test, pred, labels=[0, 1], zero_division=0))

predictions.to_csv(OUT_DIR / "test_predictions.csv", index=False)

report = {
    "dataset": "CERT r4.2",
    "split": "GroupShuffleSplit by user, test_size=0.25, random_state=42",
    "train_label_counts": y_train.value_counts().sort_index().to_dict(),
    "test_label_counts": y_test.value_counts().sort_index().to_dict(),
    "user_overlap": len(train_users & test_users),
    "metrics": results,
}

(OUT_DIR / "metrics.json").write_text(json.dumps(report, indent=2))
print("\nSaved artifacts to:", OUT_DIR)
print("Saved metrics:", OUT_DIR / "metrics.json")
print("Saved test predictions:", OUT_DIR / "test_predictions.csv")
print("\nInterpret results as incident-window proxy classification only.")
