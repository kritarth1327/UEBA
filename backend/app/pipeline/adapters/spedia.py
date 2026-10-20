"""SPEDIA annotated log adapter.

Verified facts about the file (see docs/dataset_selection.md):
  * Anomaly == 1  <=>  Agent_name is not a '*_simulation' agent. The label encodes the log
    *source*, so `Agent_name` is deliberately never read here.
  * Raw content columns (Full_log, Content, Url, Filename, Path, Command, From) are never read.
  * 'Timestamp' is used as-is (host syslog offsets differ by host, so no tz conversion is safe).
"""
from __future__ import annotations

from typing import Iterator

import numpy as np
import pandas as pd

from app.pipeline.adapters.base import IngestStats, has_external_recipient, normalize_user
from app.pipeline.schema import SPEDIA, available_features

USECOLS = ["id", "User", "Timestamp", "Decoder_name", "Activity", "Action",
           "To", "Cc", "Bcc", "Attachments", "Size", "Anomaly"]


def _kind(df: pd.DataFrame) -> pd.Series:
    act, action, dec = df["Activity"].str.lower(), df["Action"].str.lower(), df["Decoder_name"].str.lower()
    k = pd.Series(pd.NA, index=df.index, dtype="object")
    k[(act == "session") & (action == "login")] = "logon"
    k[(act == "session") & (action == "logoff")] = "logoff"
    k[(act == "session") & action.isin(["login failed", "multiple failed logins"])] = "failed_logon"
    k[act == "device"] = "device"
    k[act == "email"] = "email"
    k[act == "http"] = "http"
    k[act == "command"] = "command"
    k[(act == "file") & dec.str.startswith("syscheck")] = "file_integrity"
    k[(act == "file") & ~dec.str.startswith("syscheck")] = "file_access"
    return k


class SpediaAdapter:
    name = SPEDIA
    has_labels = True
    # Evidence (benign simulated users): 1,234 events/day on weekends vs 1,226 on weekdays with the same
    # hourly profile, so weekends are NOT treated as after-hours for this dataset.
    weekend_is_after_hours = False

    def __init__(self, internal_domains=("dtaa.com",), dedupe_ids: bool = True):
        self.internal_domains = tuple(internal_domains)
        self.dedupe_ids = dedupe_ids
        self.available = available_features(SPEDIA)

    def iter_events(self, path, chunksize: int, stats: IngestStats) -> Iterator[pd.DataFrame]:
        seen: set = set()
        reader = pd.read_csv(path, usecols=USECOLS, chunksize=chunksize, dtype=str,
                             keep_default_na=True, on_bad_lines="skip", encoding_errors="replace")
        for raw in reader:
            stats.rows_read += len(raw)
            df = raw
            if self.dedupe_ids:
                dup = df["id"].duplicated() | df["id"].isin(seen)
                stats.reject("duplicate_event_id", dup.sum())
                seen.update(df.loc[~dup, "id"].dropna())
                df = df[~dup]
            ts = pd.to_datetime(df["Timestamp"], errors="coerce")
            bad = ts.isna()
            stats.reject("bad_timestamp", bad.sum()); df, ts = df[~bad], ts[~bad]

            user = normalize_user(df["User"])
            nou = user.isna()
            stats.reject("missing_user", nou.sum())
            df, ts, user = df[~nou], ts[~nou], user[~nou]

            kind = _kind(df)
            unk = kind.isna()
            stats.reject("unrecognised_event_type", unk.sum())
            df, ts, user, kind = df[~unk], ts[~unk], user[~unk], kind[~unk]
            if df.empty:
                continue

            label = pd.to_numeric(df["Anomaly"], errors="coerce")
            label = label.where(label.isin([0, 1])).astype("Int8")
            joined = df["To"].fillna("") + ";" + df["Cc"].fillna("") + ";" + df["Bcc"].fillna("")
            ev = pd.DataFrame({
                "user_id": user.astype(str).values,
                "ts": ts.values,
                "kind": kind.values,
                "n_attach": pd.to_numeric(df["Attachments"], errors="coerce").values,
                "size": pd.to_numeric(df["Size"], errors="coerce").values,
                "ext_recipient": (has_external_recipient(joined, self.internal_domains).values
                                  & (kind == "email").values),
                "label": label.values,
            })
            stats.rows_accepted += len(ev)
            yield ev
