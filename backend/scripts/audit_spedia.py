"""Offline audit of the SPEDIA CSV (reads Agent_name on purpose: this is leakage analysis only).

    python scripts/audit_spedia.py /path/to/logs_SPEDIA_annotated_en.csv [--out audit.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.pipeline.adapters.base import normalize_user  # noqa: E402


def audit(path: str) -> dict:
    df = pd.read_csv(path, low_memory=False)
    ts = pd.to_datetime(df["Timestamp"], errors="coerce")
    user = normalize_user(df["User"])
    sim = df["Agent_name"].str.endswith("_simulation")
    y = df["Anomaly"]
    per_user = {}
    for u, g in df.assign(u=user, ts=ts, sim=sim).dropna(subset=["u"]).groupby("u"):
        per_user[u] = {
            "events": int(len(g)),
            "benign_days": int(g.loc[g.Anomaly == 0, "ts"].dt.date.nunique()),
            "anomalous_days": int(g.loc[g.Anomaly == 1, "ts"].dt.date.nunique()),
            "anomalous_events": int((g.Anomaly == 1).sum()),
        }
    return {
        "rows": int(len(df)), "columns": {c: str(t) for c, t in df.dtypes.items()},
        "missing_by_column": {c: int(n) for c, n in df.isna().sum().items() if n},
        "duplicate_rows": int(df.duplicated().sum()), "duplicate_ids": int(df["id"].duplicated().sum()),
        "bad_timestamps": int(ts.isna().sum()),
        "date_range": [str(ts.min()), str(ts.max())], "distinct_days": int(ts.dt.date.nunique()),
        "raw_user_strings": int(df["User"].nunique()), "normalised_users": int(user.nunique()),
        "events_without_user": int(user.isna().sum()),
        "activity_counts": df["Activity"].value_counts().to_dict(),
        "label_counts": {str(k): int(v) for k, v in y.value_counts().items()},
        "label_by_activity": pd.crosstab(df["Activity"], y).to_dict(orient="index"),
        "LEAKAGE_label_equals_not_simulation_agent": bool(((y == 1) == (~sim)).all()),
        "agent_name_types": df["Agent_name"].str.replace(r"_[0-9a-f]{40}$", "_<hash>", regex=True).value_counts().to_dict(),
        "users_with_only_anomalous_events": sorted(u for u, v in per_user.items() if v["benign_days"] == 0),
        "per_user": per_user,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out")
    a = ap.parse_args()
    res = audit(a.csv)
    txt = json.dumps(res, indent=2, default=str)
    Path(a.out).write_text(txt) if a.out else print(txt)
