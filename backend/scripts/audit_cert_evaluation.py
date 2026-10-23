from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, roc_auc_score, confusion_matrix
)

base = Path("artifacts/cert_threshold_analysis")
labeled_path = Path("artifacts/cert_user_day_labeled.csv")

pred = pd.read_csv(base / "test_predictions.csv")
report = json.loads((base / "metrics.json").read_text())
labeled = pd.read_csv(labeled_path)

print("=" * 72)
print("CERT EVALUATION AUDIT")
print("=" * 72)

print("\n1. LABEL DISTRIBUTION")
print(labeled["label"].value_counts(dropna=False).sort_index().to_string())
print("Label source counts:")
print(labeled["label_source"].value_counts(dropna=False).to_string())

print("\n2. FEATURE QUALITY")
excluded = {
    "user_id", "date", "label", "label_source",
    "event_count", "anomalous_event_count",
    "first_event_at", "last_event_at"
}
features = [
    c for c in labeled.columns
    if c not in excluded and pd.api.types.is_numeric_dtype(labeled[c])
]
for col in features:
    values = pd.to_numeric(labeled[col], errors="coerce")
    print(
        f"{col}: missing={values.isna().sum():,}/{len(values):,}, "
        f"unique_nonmissing={values.nunique(dropna=True)}"
    )

print("\n3. SAVED TEST PREDICTIONS")
y = pred["y_true"].astype(int).to_numpy()
for name, result in report["results"].items():
    scores = pred[f"{name}_score"].to_numpy()
    threshold = float(result["selected_threshold"])
    predicted = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()

    actual = {
        "precision": precision_score(y, predicted, zero_division=0),
        "recall": recall_score(y, predicted, zero_division=0),
        "f1": f1_score(y, predicted, zero_division=0),
        "pr_auc_average_precision": average_precision_score(y, scores),
        "roc_auc": roc_auc_score(y, scores),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }
    saved = result["test_metrics_at_selected_threshold"]

    print(f"\n{name}")
    print("Selected threshold:", threshold)
    for key, value in actual.items():
        saved_value = saved.get(key)
        if isinstance(value, float):
            matches = saved_value is not None and abs(value - saved_value) < 1e-8
            print(f"{key}: {value:.6f} | saved={saved_value} | match={matches}")
        else:
            print(f"{key}: {value} | saved={saved_value} | match={value == saved_value}")

print("\n4. USER OVERLAP IN SAVED TEST PREDICTIONS")
print("Test rows:", len(pred))
print("Unique test users:", pred["user_id"].astype(str).str.upper().nunique())
print("Duplicate user-date rows:", pred.duplicated(["user_id", "date"]).sum())

print("\n5. SCIENTIFIC LIMITATIONS")
print("- Positive labels mean date overlap with an official incident window.")
print("- Outside-window days are provisional negatives, not verified benign.")
print("- The model must not be described as validated real-world threat detection.")
print("- Test threshold results are evaluation results, not threshold-selection data.")
print("\nAudit complete.")
