"""Chunk-safe user-day aggregation of normalised events (dataset independent).

Adapters emit normalised event frames with columns:
    user_id (str), ts (datetime64), kind (str), n_attach (float), size (float),
    ext_recipient (bool), label (Int8, optional)
Only additive statistics are computed so chunked reading yields exactly the same
result as a single pass. No raw content (bodies, URLs, file names, full logs) is carried.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Set

import numpy as np
import pandas as pd

from app.pipeline.schema import FEATURE_NAMES

KINDS = ("logon", "logoff", "failed_logon", "file_access", "file_integrity",
         "email", "http", "device", "command")


@dataclass(frozen=True)
class BusinessHours:
    start: int = 8
    end: int = 18   # exclusive
    weekend_is_after_hours: bool = True


def after_hours_mask(ts: pd.Series, bh: BusinessHours) -> pd.Series:
    hour = ts.dt.hour
    off = (hour < bh.start) | (hour >= bh.end)
    if bh.weekend_is_after_hours:
        off = off | (ts.dt.dayofweek >= 5)
    return off


_ADDITIVE = [n for n in FEATURE_NAMES if n != "total_session_duration"]


class DailyAggregator:
    def __init__(self, available: Iterable[str], bh: BusinessHours, has_labels: bool):
        self.available: Set[str] = set(available)
        self.bh = bh
        self.has_labels = has_labels
        self._acc: Optional[pd.DataFrame] = None
        self._first: Optional[pd.Series] = None
        self._last: Optional[pd.Series] = None

    def add_chunk(self, ev: pd.DataFrame) -> None:
        if ev.empty:
            return
        k = ev["kind"]
        off = after_hours_mask(ev["ts"], self.bh)
        is_email = k == "email"
        d = pd.DataFrame({
            "user_id": ev["user_id"].values,
            "day": ev["ts"].dt.floor("D").values,
            "logon_count": (k == "logon").astype(int).values,
            "after_hours_logons": ((k == "logon") & off).astype(int).values,
            "failed_logon_count": (k == "failed_logon").astype(int).values,
            "file_access_count": (k == "file_access").astype(int).values,
            "file_copied_removable": 0,
            "file_integrity_event_count": (k == "file_integrity").astype(int).values,
            "email_count": is_email.astype(int).values,
            "email_external_count": (is_email & ev["ext_recipient"]).astype(int).values,
            "email_attachment_count": np.where(is_email, ev["n_attach"].fillna(0), 0),
            "email_total_bytes": np.where(is_email, ev["size"].fillna(0), 0.0),
            "http_request_count": (k == "http").astype(int).values,
            "http_after_hours_count": ((k == "http") & off).astype(int).values,
            "removable_device_events": (k == "device").astype(int).values,
            "command_exec_count": (k == "command").astype(int).values,
            "after_hours_event_count": off.astype(int).values,
            "event_count": 1,
        })
        if self.has_labels:
            d["anomalous_event_count"] = (ev["label"].fillna(0) == 1).astype(int).values
        if "file_copied_removable" in self.available and "file_copied_removable" in ev.columns:
            d["file_copied_removable"] = ev["file_copied_removable"].astype(int).values
        keys = ["user_id", "day"]
        part = d.groupby(keys).sum()
        self._acc = part if self._acc is None else self._acc.add(part, fill_value=0)

        ts = ev.assign(user_id=ev["user_id"], day=ev["ts"].dt.floor("D")).groupby(keys)["ts"]
        mn, mx = ts.min(), ts.max()
        self._first = mn if self._first is None else pd.concat([self._first, mn]).groupby(level=[0, 1]).min()
        self._last = mx if self._last is None else pd.concat([self._last, mx]).groupby(level=[0, 1]).max()

    def finalize(self) -> pd.DataFrame:
        cols = ["user_id", "date", *FEATURE_NAMES, "event_count", "anomalous_event_count",
                "first_event_at", "last_event_at"]
        if self._acc is None:
            return pd.DataFrame(columns=cols)
        a = self._acc.copy().astype("float64")   # deterministic dtype regardless of chunking
        a["total_session_duration"] = np.nan
        for n in FEATURE_NAMES:
            if n not in self.available:
                a[n] = np.nan
        if not self.has_labels:
            a["anomalous_event_count"] = np.nan
        a["first_event_at"] = self._first
        a["last_event_at"] = self._last
        a = a.reset_index().rename(columns={"day": "date"})
        a["date"] = pd.to_datetime(a["date"]).dt.date
        a = a.sort_values(["user_id", "date"]).reset_index(drop=True)
        return a[cols]
