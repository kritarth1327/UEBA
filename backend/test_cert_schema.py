
from pathlib import Path

import pandas as pd


DATASET_DIR = Path("data/raw/r4.2")


def test_logon_activity_values():
    df = pd.read_csv(
        DATASET_DIR / "logon.csv",
        usecols=["activity"],
        nrows=10_000,
    )
    print("\nLogon activities:")
    print(df["activity"].value_counts(dropna=False))


def test_device_activity_values():
    df = pd.read_csv(
        DATASET_DIR / "device.csv",
        usecols=["activity"],
        nrows=10_000,
    )
    print("\nDevice activities:")
    print(df["activity"].value_counts(dropna=False))


def test_file_content_values():
    df = pd.read_csv(
        DATASET_DIR / "file.csv",
        usecols=["content"],
        nrows=10_000,
    )
    print("\nFile content values:")
    print(df["content"].value_counts(dropna=False).head(20))


def test_email_recipient_examples():
    df = pd.read_csv(
        DATASET_DIR / "email.csv",
        usecols=["to", "attachments"],
        nrows=20,
    )
    print("\nEmail recipient examples:")
    print(df["to"].to_list())
    print("\nAttachment examples:")
    print(df["attachments"].to_list())
