import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "daily_behavior_profiles.csv"
ARTIFACT_DIR = ROOT / "backend" / "artifacts"

sys.path.insert(0, str(ROOT / "backend"))

from app.services.ann_anomaly_service import ann_anomaly_service

FEATURES = [
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

OUTPUT_DIR = ROOT / "data" / "processed"
OUTPUT_PATH = OUTPUT_DIR / "ann_evaluation_results.csv"

print("Loading processed profiles...")
df = pd.read_csv(DATA_PATH, parse_dates=["date"])

if df.empty:
    raise ValueError("The dataset is empty.")

if df[FEATURES].isna().any().any():
    raise ValueError("Missing values found in model features.")

if (df[FEATURES] < 0).any().any():
    raise ValueError("Negative feature values found.")

if not ann_anomaly_service.is_available():
    raise RuntimeError("ANN service could not load its model artifacts.")

print("Profiles:", f"{len(df):,}")
print("Unique users:", f"{df['user_id'].nunique():,}")

# Reuse the exact model, scaler, feature order, and threshold
# already loaded by the production inference service.
scored_rows = []

for start in range(0, len(df), 5000):
    batch = df.iloc[start:start + 5000]

    for row in batch.itertuples(index=False):
        record = row._asdict()
        feature_vector = [float(record[name]) for name in FEATURES]
        prediction = ann_anomaly_service.predict(feature_vector)

        scored_rows.append({
            "user_id": record["user_id"],
            "date": record["date"],
            "ann_anomaly_score": prediction["ann_anomaly_score"],
            "threshold": prediction["threshold"],
            "is_anomaly_candidate": prediction["is_anomaly_candidate"],
        })

    completed = min(start + len(batch), len(df))
    print(f"Scored {completed:,} / {len(df):,} profiles")

results = pd.DataFrame(scored_rows)
results["date"] = pd.to_datetime(results["date"])

results.to_csv(OUTPUT_PATH, index=False)

candidate_mask = results["is_anomaly_candidate"].astype(bool)
candidates = results[candidate_mask].copy()

print("\n" + "=" * 55)
print("FULL DATASET EVALUATION")
print("=" * 55)
print("Total profiles scored:", f"{len(results):,}")
print("Unique users:", f"{results['user_id'].nunique():,}")
print("Anomaly candidates:", f"{len(candidates):,}")
print(
    "Candidate rate:",
    f"{100 * len(candidates) / len(results):.2f}%"
)
print("Threshold:", results["threshold"].iloc[0])

print("\nCandidates by date period:")
if candidates.empty:
    print("No profiles exceeded the threshold.")
else:
    candidates["period"] = candidates["date"].dt.to_period("M").astype(str)
    print(candidates.groupby("period").size().to_string())

    print("\nTop 20 profiles by reconstruction error:")
    print(
        candidates.nlargest(20, "ann_anomaly_score")[
            ["user_id", "date", "ann_anomaly_score", "threshold"]
        ].to_string(index=False)
    )

    print("\nTop 15 users by candidate count:")
    print(
        candidates.groupby("user_id")
        .agg(
            candidate_profiles=("date", "count"),
            highest_score=("ann_anomaly_score", "max"),
        )
        .sort_values(
            ["candidate_profiles", "highest_score"],
            ascending=False,
        )
        .head(15)
        .to_string()
    )

print("\nFull results saved to:")
print(OUTPUT_PATH)
print(
    "\nReminder: these are anomaly candidates, "
    "not confirmed malicious activities."
)
