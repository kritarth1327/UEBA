from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score, recall_score, f1_score, accuracy_score,
    confusion_matrix, average_precision_score, roc_auc_score
)

base = Path("artifacts/cert_threshold_analysis")
pred = pd.read_csv(base / "test_predictions.csv")
report = json.loads((base / "metrics.json").read_text())
validation = pd.read_csv(base / "validation_threshold_comparison.csv")

y = pred["y_true"].astype(int).to_numpy()

def evaluate(y_true, scores, threshold):
    p = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, p, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "precision": precision_score(y_true, p, zero_division=0),
        "recall": recall_score(y_true, p, zero_division=0),
        "f1": f1_score(y_true, p, zero_division=0),
        "accuracy": accuracy_score(y_true, p),
        "PR_AUC": average_precision_score(y_true, scores),
        "ROC_AUC": roc_auc_score(y_true, scores),
        "TN": tn, "FP": fp, "FN": fn, "TP": tp,
    }

rows = []
for name, result in report["results"].items():
    score_col = f"{name}_score"
    scores = pred[score_col].to_numpy()
    tuned = float(result["selected_threshold"])

    for label, threshold in [
        ("Default threshold", 0.5),
        ("Validation-selected threshold", tuned),
    ]:
        row = evaluate(y, scores, threshold)
        row["model"] = name
        row["threshold_type"] = label
        rows.append(row)

comparison = pd.DataFrame(rows)
cols = [
    "model", "threshold_type", "threshold", "precision", "recall",
    "f1", "PR_AUC", "ROC_AUC", "accuracy", "TN", "FP", "FN", "TP"
]
comparison = comparison[cols]
comparison.to_csv(base / "default_vs_tuned_test.csv", index=False)

print("=" * 76)
print("DEFAULT 0.5 VS VALIDATION-SELECTED THRESHOLD — HELD-OUT TEST")
print("=" * 76)
print(comparison.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print("\n" + "=" * 76)
print("VALIDATION THRESHOLD SENSITIVITY — VALIDATION DATA ONLY")
print("=" * 76)
for name, group in validation.groupby("model"):
    group = group.sort_values("threshold")
    print(f"\n{name}")
    print(group[
        ["threshold", "precision", "recall", "f1", "fp", "fn"]
    ].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    best = group.loc[group["f1"].idxmax()]
    print(
        f"Best F1 among saved validation thresholds: {best['f1']:.4f} "
        f"at threshold {best['threshold']:.6f}"
    )

print("\nSaved:", base / "default_vs_tuned_test.csv")
print(
    "\nCaveat: these labels represent official incident-window overlap, "
    "not verified malicious days. Threshold stability here is only a "
    "coarse-grid sensitivity check; it is not repeated-split stability."
)
