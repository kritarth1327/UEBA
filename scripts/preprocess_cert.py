from collections import defaultdict
from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "r4.2"
OUT = ROOT / "data" / "processed" / "daily_behavior_profiles.csv"

CHUNK_SIZE = 250_000
AFTER_HOURS_START = 18
AFTER_HOURS_END = 6
MAX_SESSION_HOURS = 24

profiles = defaultdict(lambda: {
    "logon_count": 0,
    "after_hours_logons": 0,
    "file_access_count": 0,
    "file_copied_removable": 0,
    "email_count": 0,
    "email_external_count": 0,
    "email_attachment_count": 0,
    "http_request_count": 0,
    "http_after_hours_count": 0,
    "removable_device_events": 0,
    "total_session_duration": 0.0,
})


def read_chunks(filename, usecols):
    path = RAW / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing dataset file: {path}")

    return pd.read_csv(
        path,
        usecols=usecols,
        chunksize=CHUNK_SIZE,
        dtype=str,
        on_bad_lines="warn",
        low_memory=False,
    )


def prepare_dates(df):
    df["date"] = pd.to_datetime(
        df["date"],
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    )

    df["user"] = df["user"].fillna("").str.strip()
    df = df.dropna(subset=["date"])
    df = df[df["user"] != ""].copy()

    df["day"] = df["date"].dt.strftime("%Y-%m-%d")
    df["hour"] = df["date"].dt.hour

    return df


def add_grouped_counts(df, mask, feature):
    if not mask.any():
        return

    counts = df.loc[mask].groupby(["user", "day"]).size()

    for (user, day), count in counts.items():
        profiles[(user, day)][feature] += int(count)


def is_after_hours(df):
    return (
        (df["hour"] < AFTER_HOURS_END)
        | (df["hour"] >= AFTER_HOURS_START)
    )


def process_logons():
    print("\n[1/6] Processing logon counts and session durations ...")

    # First pass: count logons and after-hours logons.
    for chunk in read_chunks(
        "logon.csv",
        ["date", "user", "pc", "activity"],
    ):
        chunk = prepare_dates(chunk)
        chunk["activity"] = (
            chunk["activity"].fillna("").str.strip().str.lower()
        )

        logons = chunk["activity"] == "logon"

        add_grouped_counts(chunk, logons, "logon_count")
        add_grouped_counts(
            chunk,
            logons & is_after_hours(chunk),
            "after_hours_logons",
        )

    print("      Logon counts complete.")
    print("      Pairing events for estimated session durations ...")

    # Second pass: read the relatively small logon file and pair events.
    events = pd.read_csv(
        RAW / "logon.csv",
        usecols=["date", "user", "pc", "activity"],
        dtype=str,
        low_memory=False,
    )

    events["date"] = pd.to_datetime(
        events["date"],
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    )
    events["user"] = events["user"].fillna("").str.strip()
    events["pc"] = events["pc"].fillna("").str.strip()
    events["activity"] = (
        events["activity"].fillna("").str.strip().str.lower()
    )

    events = events.dropna(subset=["date"])
    events = events[
        (events["user"] != "")
        & (events["pc"] != "")
        & events["activity"].isin(["logon", "logoff"])
    ]

    events = events.sort_values(
        ["user", "pc", "date"],
        kind="mergesort",
    )

    pending_logons = {}
    paired_sessions = 0
    rejected_sessions = 0

    for row in events.itertuples(index=False):
        key = (row.user, row.pc)

        if row.activity == "logon":
            # If another logon occurs before a logoff, keep the latest
            # logon as the start of the current session.
            pending_logons[key] = row.date
            continue

        start = pending_logons.pop(key, None)

        if start is None:
            continue

        seconds = (row.date - start).total_seconds()

        if seconds < 0 or seconds > MAX_SESSION_HOURS * 3600:
            rejected_sessions += 1
            continue

        day = start.strftime("%Y-%m-%d")
        profiles[(row.user, day)]["total_session_duration"] += seconds / 3600
        paired_sessions += 1

    print(f"      Paired sessions: {paired_sessions:,}")
    print(f"      Rejected duration outliers: {rejected_sessions:,}")
    print("      Session duration is estimated from recorded event pairs.")


def process_devices():
    print("\n[2/6] Processing device.csv ...")

    for chunk in read_chunks("device.csv", ["date", "user", "activity"]):
        chunk = prepare_dates(chunk)

        connected = (
            chunk["activity"].fillna("").str.strip().str.lower()
            == "connect"
        )

        add_grouped_counts(
            chunk,
            connected,
            "removable_device_events",
        )

    print("      Device aggregation complete.")


def process_files():
    print("\n[3/6] Processing file.csv ...")

    for chunk in read_chunks("file.csv", ["date", "user"]):
        chunk = prepare_dates(chunk)

        all_rows = pd.Series(True, index=chunk.index)

        # CERT file.csv represents file copies to removable media.
        add_grouped_counts(
            chunk,
            all_rows,
            "file_copied_removable",
        )

    # Keep the old backend schema, but do not pretend this is a separate
    # general file-access count. It will be excluded from model features.
    print("      Removable-media file-copy aggregation complete.")


def has_external_recipient(row):
    for field in ("to", "cc", "bcc"):
        value = row.get(field, "")

        if not isinstance(value, str) or not value.strip():
            continue

        for address in value.split(";"):
            address = address.strip().lower()
            match = re.search(r"@([^>\\s,;]+)", address)

            if match and match.group(1).rstrip(".") != "dtaa.com":
                return True

    return False


def process_emails():
    print("\n[4/6] Processing email.csv ...")

    columns = ["date", "user", "to", "cc", "bcc", "attachments"]

    for chunk in read_chunks("email.csv", columns):
        chunk = prepare_dates(chunk)

        add_grouped_counts(
            chunk,
            pd.Series(True, index=chunk.index),
            "email_count",
        )

        external = chunk.apply(has_external_recipient, axis=1)

        add_grouped_counts(
            chunk,
            external,
            "email_external_count",
        )

        chunk["attachments_numeric"] = pd.to_numeric(
            chunk["attachments"],
            errors="coerce",
        ).fillna(0)

        totals = chunk.groupby(["user", "day"])[
            "attachments_numeric"
        ].sum()

        for (user, day), count in totals.items():
            profiles[(user, day)]["email_attachment_count"] += int(count)

    print("      Email aggregation complete.")


def process_http():
    print("\n[5/6] Processing http.csv ...")

    for chunk in read_chunks("http.csv", ["date", "user"]):
        chunk = prepare_dates(chunk)

        add_grouped_counts(
            chunk,
            pd.Series(True, index=chunk.index),
            "http_request_count",
        )

        add_grouped_counts(
            chunk,
            is_after_hours(chunk),
            "http_after_hours_count",
        )

    print("      HTTP aggregation complete.")


def main():
    print("CERT r4.2 daily behavior preprocessing")
    print(f"Input directory: {RAW}")
    print(f"Output file: {OUT}")

    required = [
        "logon.csv",
        "device.csv",
        "file.csv",
        "email.csv",
        "http.csv",
    ]

    for filename in required:
        if not (RAW / filename).exists():
            raise FileNotFoundError(f"Missing dataset file: {RAW / filename}")

    process_logons()
    process_devices()
    process_files()
    process_emails()
    process_http()

    print("\n[6/6] Building final daily profiles ...")

    rows = [
        {"user_id": user, "date": day, **metrics}
        for (user, day), metrics in profiles.items()
    ]

    output_columns = [
        "user_id",
        "date",
        "logon_count",
        "after_hours_logons",
        "file_access_count",
        "file_copied_removable",
        "email_count",
        "email_external_count",
        "email_attachment_count",
        "http_request_count",
        "http_after_hours_count",
        "removable_device_events",
        "total_session_duration",
    ]

    result = pd.DataFrame(rows, columns=output_columns)

    if result.empty:
        raise RuntimeError("No daily profiles were generated.")

    result = result.sort_values(
        ["user_id", "date"]
    ).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)

    print("\nPreprocessing complete!")
    print(f"Output: {OUT}")
    print(f"Daily profiles: {len(result):,}")
    print(f"Distinct users: {result['user_id'].nunique():,}")
    print(f"Date range: {result['date'].min()} to {result['date'].max()}")
    print(f"Output size: {OUT.stat().st_size / (1024**2):.2f} MB")
    print("\nFirst five rows:")
    print(result.head().to_string(index=False))
    print("\nMissing values per column:")
    print(result.isna().sum().to_string())


if __name__ == "__main__":
    main()
