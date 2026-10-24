
#!/usr/bin/env python3
"""Generate CERT r4.2 user-day proxy labels from official incident windows."""

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
FEATURES = BASE / "artifacts" / "cert_user_day_features.csv"
ANSWERS = (
    Path.home()
    / "Downloads"
    / "CERT_answers"
    / "answers"
    / "insiders.csv"
)
OUTPUT = BASE / "artifacts" / "cert_user_day_labeled.csv"
AUDIT = BASE / "artifacts" / "cert_user_day_label_audit.json"


def parse_incident_dates(series):
    """Parse dates that may use either month/day/year or day/month/year."""
    values = series.astype(str).str.strip()

    # Try month/day/year first, matching common CERT ground-truth formats.
    parsed = pd.to_datetime(
        values,
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    )

    # Retry unparsed values as day/month/year.
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            values.loc[missing],
            format="%d/%m/%Y %H:%M:%S",
            errors="coerce",
        )

    # Final fallback for other recognizable date formats.
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            values.loc[missing],
            format="mixed",
            errors="coerce",
        )

    if parsed.isna().any():
        bad_values = values.loc[parsed.isna()].head(10).tolist()
        raise ValueError(
            f"Could not parse incident dates. Examples: {bad_values}"
        )

    return parsed.dt.normalize()


def main():
    if not FEATURES.exists():
        raise FileNotFoundError(f"Feature CSV not found: {FEATURES}")

    if not ANSWERS.exists():
        raise FileNotFoundError(
            f"Ground-truth file not found: {ANSWERS}"
        )

    print("Loading feature dataset...")
    features = pd.read_csv(FEATURES)

    print("Loading official incident records...")
    incidents = pd.read_csv(ANSWERS)

    required_features = {"user_id", "date"}
    required_incidents = {"user", "start", "end", "scenario"}

    if not required_features.issubset(features.columns):
        raise ValueError(
            f"Features must contain: {sorted(required_features)}"
        )

    if not required_incidents.issubset(incidents.columns):
        raise ValueError(
            f"insiders.csv must contain: {sorted(required_incidents)}"
        )

    features["user_id"] = (
        features["user_id"].astype(str).str.strip().str.upper()
    )
    features["date"] = pd.to_datetime(
        features["date"], errors="raise"
    ).dt.normalize()

    incidents["user"] = (
        incidents["user"].astype(str).str.strip().str.upper()
    )
    incidents["start"] = parse_incident_dates(incidents["start"])
    incidents["end"] = parse_incident_dates(incidents["end"])

    if (incidents["start"] > incidents["end"]).any():
        bad = incidents.loc[
            incidents["start"] > incidents["end"],
            ["user", "start", "end"],
        ].head(10)
        raise ValueError(
            "Some incidents start after their end:\n"
            + bad.to_string(index=False)
        )

    if features.duplicated(["user_id", "date"]).any():
        raise ValueError(
            "Feature dataset contains duplicate user-day rows."
        )

    print("Generating user-day labels...")
    labels = pd.Series(0, index=features.index, dtype="int8")

    for incident in incidents.itertuples(index=False):
        mask = (
            features["user_id"].eq(incident.user)
            & features["date"].between(
                incident.start, incident.end, inclusive="both"
            )
        )
        labels.loc[mask] = 1

    features["label"] = labels
    features["label_source"] = labels.map(
        {
            1: "inside_official_incident_window_proxy",
            0: "outside_official_incident_window_provisional",
        }
    )

    missing_users = sorted(
        set(incidents["user"]) - set(features["user_id"])
    )

    audit = {
        "dataset": "CERT r4.2",
        "ground_truth_file": str(ANSWERS),
        "label_definition": (
            "Positive when a user-day overlaps an official incident "
            "window. Days outside incident windows are provisional "
            "negatives, not verified benign labels."
        ),
        "date_granularity": (
            "Calendar day; incident timestamps reduced to dates"
        ),
        "incident_records": int(len(incidents)),
        "unique_incident_users": int(incidents["user"].nunique()),
        "feature_rows": int(len(features)),
        "feature_users": int(features["user_id"].nunique()),
        "positive_user_days": int(labels.sum()),
        "provisional_negative_user_days": int(labels.eq(0).sum()),
        "positive_percentage": round(float(labels.mean() * 100), 4),
        "incident_users_missing_from_features": missing_users,
        "scenario_counts": {
            str(scenario): {
                "incident_records": int(len(group)),
                "unique_users": int(group["user"].nunique()),
            }
            for scenario, group in incidents.groupby("scenario")
        },
        "output_csv": "artifacts/cert_user_day_labeled.csv",
    }

    # Verify against the existing dataset before replacing it.
    if OUTPUT.exists():
        print("Checking existing labels before overwriting...")
        old = pd.read_csv(
            OUTPUT,
            usecols=["user_id", "date", "label"],
        )

        old["user_id"] = (
            old["user_id"].astype(str).str.strip().str.upper()
        )
        old["date"] = pd.to_datetime(
            old["date"], errors="raise"
        ).dt.normalize()

        keys = ["user_id", "date"]

        new_check = features[keys + ["label"]].copy()
        old_check = old[keys + ["label"]].copy()

        new_check["label"] = new_check["label"].astype("int8")
        old_check["label"] = pd.to_numeric(
            old_check["label"], errors="raise"
        ).astype("int8")

        new_check = (
            new_check.sort_values(keys).reset_index(drop=True)
        )
        old_check = (
            old_check.sort_values(keys).reset_index(drop=True)
        )

        if not new_check.equals(old_check):
            mismatches = new_check.merge(
                old_check,
                on=keys,
                how="outer",
                suffixes=("_new", "_old"),
                indicator=True,
            )
            mismatches = mismatches[
                (mismatches["_merge"] != "both")
                | (
                    mismatches["label_new"].fillna(-1)
                    != mismatches["label_old"].fillna(-1)
                )
            ]

            raise RuntimeError(
                "Generated labels differ from the existing dataset. "
                "The existing CSV and audit were preserved.\n"
                "First mismatches:\n"
                + mismatches.head(10).to_string(index=False)
            )

        print("Verified: generated labels match the existing CSV.")

    # Write to a temporary file, then replace the CSV atomically.
    features["date"] = features["date"].dt.strftime("%Y-%m-%d")

    temp_output = OUTPUT.with_suffix(".csv.tmp")
    features.to_csv(temp_output, index=False)
    temp_output.replace(OUTPUT)

    AUDIT.write_text(json.dumps(audit, indent=2) + "\n")

    print("\nLabel generation completed successfully.")
    print(f"Dataset: {OUTPUT}")
    print(f"Audit:   {AUDIT}")
    print(f"Rows:    {len(features):,}")
    print(f"Users:   {features['user_id'].nunique():,}")
    print(f"Positive user-days: {int(labels.sum()):,}")
    print(f"Provisional negative user-days: {int(labels.eq(0).sum()):,}")
    print(f"Positive percentage: {labels.mean() * 100:.4f}%")


if __name__ == "__main__":
    main()
