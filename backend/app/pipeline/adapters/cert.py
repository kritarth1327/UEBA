
"""CERT Insider Threat r4.2 dataset adapter.

Reads documented CERT r4.2 CSV files in chunks and normalises them
into the shared event schema.

Raw content fields such as email content, web content, URLs and filenames
are never read into the normalised event stream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from app.pipeline.adapters.base import (
    IngestStats,
    has_external_recipient,
    normalize_user,
)
from app.pipeline.schema import CERT_R42, available_features


DATE_FORMAT = "%m/%d/%Y %H:%M:%S"

FILES = (
    "logon.csv",
    "device.csv",
    "file.csv",
    "email.csv",
    "http.csv",
)

_COLS = {
    "logon.csv": ["id", "date", "user", "activity"],
    "device.csv": ["id", "date", "user", "activity"],
    "file.csv": ["id", "date", "user"],
    "email.csv": [
        "id", "date", "user", "to", "cc", "bcc", "size", "attachments",
    ],
    "http.csv": ["id", "date", "user"],
}


def _count_attachments(s: pd.Series) -> pd.Series:
    """Convert attachment counts to numbers, preserving missing values."""
    numeric = pd.to_numeric(s, errors="coerce")
    text = s.fillna("").astype(str).str.strip()
    listed = text.str.count(";") + text.ne("").astype(int)
    return numeric.fillna(listed.where(numeric.isna()))


class CertR42Adapter:
    """Normalise CERT r4.2 activity logs into the shared event schema."""

    name = CERT_R42
    has_labels = False
    weekend_is_after_hours = True

    def __init__(
        self,
        internal_domains=("dtaa.com",),
        file_is_removable_copy: bool = True,
    ):
        self.internal_domains = tuple(
            domain.lower().lstrip("@")
            for domain in internal_domains
        )
        self.file_is_removable_copy = file_is_removable_copy
        self._file_source_available = False

        overrides = (
            ["file_copied_removable"]
            if self.file_is_removable_copy
            else None
        )
        self.available = set(available_features(CERT_R42, overrides))

    def source_files(self, directory) -> list[Path]:
        """Return the expected source files that exist."""
        root = Path(directory)
        return [
            root / filename
            for filename in FILES
            if (root / filename).exists()
        ]

    def iter_events(
        self,
        directory,
        chunksize: int,
        stats: IngestStats,
    ) -> Iterator[pd.DataFrame]:
        """Read and normalise source CSVs incrementally."""
        root = Path(directory)
        file_path = root / "file.csv"

        # Determine availability before yielding any events.
        self._file_source_available = (
            self.file_is_removable_copy and file_path.exists()
        )

        if not self._file_source_available:
            self.available.discard("file_copied_removable")
        elif self.file_is_removable_copy:
            self.available.add("file_copied_removable")

        for filename in FILES:
            path = root / filename

            if not path.exists():
                stats.missing_sources.append(filename)
                continue

            reader = pd.read_csv(
                path,
                usecols=_COLS[filename],
                chunksize=chunksize,
                dtype=str,
                on_bad_lines="skip",
                encoding_errors="replace",
            )

            for raw in reader:
                stats.rows_read += len(raw)
                events = self._normalise(filename, raw, stats)

                if events is not None and not events.empty:
                    stats.rows_accepted += len(events)
                    yield events

    def _normalise(
        self,
        filename: str,
        frame: pd.DataFrame,
        stats: IngestStats,
    ) -> Optional[pd.DataFrame]:
        """Convert one source chunk to the shared event format."""
        if frame.empty:
            return None

        df = frame.copy()

        duplicate = df["id"].duplicated(keep="first")
        stats.reject("duplicate_event_id", int(duplicate.sum()))
        df = df.loc[~duplicate].copy()

        if df.empty:
            return None

        timestamps = pd.to_datetime(
            df["date"],
            format=DATE_FORMAT,
            errors="coerce",
        )

        bad_timestamp = timestamps.isna()
        stats.reject("bad_timestamp", int(bad_timestamp.sum()))

        df = df.loc[~bad_timestamp].copy()
        timestamps = timestamps.loc[~bad_timestamp]

        if df.empty:
            return None

        users = normalize_user(df["user"], domain_prefix=True)
        missing_user = users.isna()
        stats.reject("missing_user", int(missing_user.sum()))

        df = df.loc[~missing_user].copy()
        timestamps = timestamps.loc[~missing_user]
        users = users.loc[~missing_user]

        if df.empty:
            return None

        kind = pd.Series("", index=df.index, dtype="object")
        attachments = pd.Series(float("nan"), index=df.index)
        size = pd.Series(float("nan"), index=df.index)
        external_recipient = pd.Series(False, index=df.index)

        if filename in ("logon.csv", "device.csv"):
            activity = df["activity"].str.strip().str.lower()

            if filename == "logon.csv":
                kind = activity.map({
                    "logon": "logon",
                    "logoff": "logoff",
                })
            else:
                kind = activity.map({
                    "connect": "device",
                    "disconnect": "device",
                })

            unknown = kind.isna()
            stats.reject(
                "unrecognised_event_type",
                int(unknown.sum()),
            )

            df = df.loc[~unknown].copy()
            timestamps = timestamps.loc[~unknown]
            users = users.loc[~unknown]
            kind = kind.loc[~unknown]
            attachments = attachments.loc[~unknown]
            size = size.loc[~unknown]
            external_recipient = external_recipient.loc[~unknown]

        elif filename == "file.csv":
            kind[:] = "file_access"

        elif filename == "http.csv":
            kind[:] = "http"

        elif filename == "email.csv":
            kind[:] = "email"
            attachments = _count_attachments(df["attachments"])
            size = pd.to_numeric(df["size"], errors="coerce")

            recipients = (
                df["to"].fillna("").astype(str)
                + ";"
                + df["cc"].fillna("").astype(str)
                + ";"
                + df["bcc"].fillna("").astype(str)
            )

            external_recipient = has_external_recipient(
                recipients,
                self.internal_domains,
            )

        else:
            stats.reject("unsupported_source_file", len(df))
            return None

        if df.empty:
            return None

        events = pd.DataFrame({
            "user_id": users.astype(str).values,
            "ts": timestamps.values,
            "kind": kind.values,
            "n_attach": attachments.values,
            "size": size.values,
            "ext_recipient": external_recipient.values,
            "label": pd.array(
                [pd.NA] * len(df),
                dtype="Int8",
            ),
        })

        # Emit this column only for actual file.csv records when the
        # source exists and the adapter is configured to interpret
        # those records as removable-media copies.
        if filename == "file.csv" and self._file_source_available:
            events["file_copied_removable"] = (
                events["kind"] == "file_access"
            ).astype("int64")

        return events
