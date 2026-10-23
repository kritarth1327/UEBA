from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore")

DATA = Path("artifacts/cert_user_day_labeled.csv")
OUT = Path("artifacts/cert_threshold_stability")
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
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
features = [
    c for c in df.columns
    if c not in excluded and pd.api.types.is_numeric_dtype(df[c])
]
X = df[features].replace([np.inf, -np.inf], np.nan)
y = df["label"]
groups = df["user_id"]

try:
    from xgboost import XGBClassifier
except ImportError as exc:
    raise SystemExit("XGBoost is required. Activate .venv311 and retry.") from exc

def metrics(y_true, scores, threshold):
    pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(
        y_true, pred, labels=[0, 1]
    ).ravel()
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }

seeds = [(42, 43), (52, 53), (62, 63), (72, 73), (82, 83)]
records = []

for run, (outer_seed, inner_seed) in enumerate(seeds, start=1):
    outer = GroupShuffleSplit(
        n_splits=1, test_size=0.25, random_state=outer_seed
    )
    trainval_idx, test_idx = next(outer.split(X, y, groups))

    inner = GroupShuffleSplit(
        n_splits=1, test_size=0.20, random_state=inner_seed
    )
    train_rel, val_rel = next(
        inner.split(
            X.iloc[trainval_idx],
            y.iloc[trainval_idx],
            groups.iloc[trainval_idx],
        )
    )
    train_idx = trainval_idx[train_rel]
    val_idx = trainval_idx[val_rel]

    train_users = set(groups.iloc[train_idx])
    val_users = set(groups.iloc[val_idx])
    test_users = set(groups.iloc[test_idx])

    assert not train_users & val_users
    assert not train_users & test_users
    assert not val_users & test_users

    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_val, y_val = X.iloc[val_idx], y.iloc[val_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]

    if any(part.nunique() < 2 for part in (y_train, y_val, y_test)):
        print(f"Skipping seed pair {outer_seed}/{inner_seed}: missing class.")
        continue

    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())

    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=400,
            class_weight="balanced_subsample",
            min_samples_leaf=3,
            random_state=outer_seed,
            n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=400,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_weight=3,
            reg_lambda=1.0,
            scale_pos_weight=neg / max(pos, 1),
            eval_metric="logloss",
            random_state=outer_seed,
            n_jobs=-1,
        ),
    }

    for name, model in models.items():
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", model),
        ])
        pipeline.fit(X_train, y_train)

        val_scores = pipeline.predict_proba(X_val)[:, 1]
        # Select threshold using validation F1 only.
        candidates = np.unique(np.concatenate([
            np.linspace(0.01, 0.99, 99),
            val_scores,
        ]))
        val_f1 = [
            f1_score(y_val, val_scores >= t, zero_division=0)
            for t in candidates
        ]
        threshold = float(candidates[int(np.argmax(val_f1))])

        test_scores = pipeline.predict_proba(X_test)[:, 1]
        row = metrics(y_test, test_scores, threshold)
        row.update({
            "run": run,
            "outer_seed": outer_seed,
            "inner_seed": inner_seed,
            "model": name,
            "train_users": len(train_users),
            "validation_users": len(val_users),
            "test_users": len(test_users),
            "train_rows": len(train_idx),
            "validation_rows": len(val_idx),
            "test_rows": len(test_idx),
            "validation_f1_at_selected_threshold": float(max(val_f1)),
            "train_validation_overlap": len(train_users & val_users),
            "train_test_overlap": len(train_users & test_users),
            "validation_test_overlap": len(val_users & test_users),
        })
        records.append(row)
        print(
            f"Run {run}/5 | {name} | threshold={threshold:.4f} "
            f"| test F1={row['f1']:.4f} "
            f"| precision={row['precision']:.4f} "
            f"| recall={row['recall']:.4f} "
            f"| PR-AUC={row['pr_auc']:.4f} "
            f"| FP={row['fp']} FN={row['fn']}"
        )

if not records:
    raise SystemExit("No valid runs completed.")

results = pd.DataFrame(records)
results.to_csv(OUT / "per_split_results.csv", index=False)

summary = (
    results.groupby("model")
    .agg({
        "threshold": ["mean", "std", "min", "max"],
        "precision": ["mean", "std"],
        "recall": ["mean", "std"],
        "f1": ["mean", "std"],
        "pr_auc": ["mean", "std"],
        "roc_auc": ["mean", "std"],
        "fp": ["mean", "std"],
        "fn": ["mean", "std"],
    })
)
summary.to_csv(OUT / "stability_summary.csv")

report = {
    "dataset": "CERT r4.2",
    "split_method": "User-grouped 60/15/25 train/validation/test",
    "seed_pairs": [{"outer": a, "inner": b} for a, b in seeds],
    "features": features,
    "completed_runs": int(results["run"].nunique()),
    "label_caveat": (
        "Incident-window proxy classification only. Outside-window days "
        "are provisional negatives, not verified benign labels."
    ),
    "threshold_selection": (
        "Maximum validation F1 over a grid from 0.01 to 0.99 plus observed "
        "validation scores. Test labels are not used for threshold selection."
    ),
    "note": (
        "Different seeds change user partitions and model randomness. "
        "These repeated holdouts assess sensitivity; they are not independent "
        "external validation, and threshold variability should be interpreted "
        "with the small number of splits in mind."
    ),
}
(OUT / "summary.json").write_text(json.dumps(report, indent=2))

print("\nSaved stability results to:", OUT)
print("- per_split_results.csv")
print("- stability_summary.csv")
print("- summary.json")
print("\nUse means and standard deviations to assess split sensitivity.")
