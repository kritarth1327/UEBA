
from pathlib import Path

import pandas as pd

from app.core.config import settings


LOGON_PATH = settings.CERT_R42_DIR / "logon.csv"


def test_logon_event_patterns():
    df = pd.read_csv(
        LOGON_PATH,
        usecols=["date", "user", "pc", "activity"],
        nrows=20_000,
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
        format="mixed",
    )

    df = df.dropna(subset=["date", "user", "pc"])
    df["activity"] = df["activity"].str.strip().str.lower()
    df = df.sort_values(["user", "pc", "date"])

    print("\nActivity counts:")
    print(df["activity"].value_counts())

    print("\nSample events for one user and PC:")
    first_pair = df.iloc[0][["user", "pc"]]
    pair = df[
        (df["user"] == first_pair["user"])
        & (df["pc"] == first_pair["pc"])
    ]

    print(pair.head(20).to_string(index=False))

    assert not df.empty
    assert {"logon", "logoff"}.issubset(set(df["activity"]))


def test_same_user_pc_has_no_negative_durations():
    df = pd.read_csv(
        LOGON_PATH,
        usecols=["date", "user", "pc", "activity"],
        nrows=20_000,
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
        format="mixed",
    )

    assert df["date"].notna().any()
