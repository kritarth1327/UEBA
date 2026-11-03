
"""Chunk-safe user-day aggregation of normalized events."""

from __future__ import annotations

from typing import Iterable, Optional, Set

import numpy as np
import pandas as pd

from app.pipeline.schema import FEATURE_NAMES


KINDS = (
    "logon",
    "logoff",
    "failed_logon",
    "file_access",
    "file_integrity",
    "email",
    "http",
    "device",
    "command",
)


class BusinessHours:
    def __init__(
        self,
        start: int = 8,
        end: int = 18,
        weekend_is_after_hours: bool = True,
    ):
        self.start = start
        self.end = end
        self.weekend_is_after_hours = weekend_is_after_hours


def after_hours_mask(
    ts: pd.Series,
    bh: BusinessHours,
) -> pd.Series:
    hour = ts.dt.hour
    off = (hour < bh.start) | (hour >= bh.end)

    if bh.weekend_is_after_hours:
        off = off | (ts.dt.day_of_week >= 5)

    return off


class DailyAggregator:
    def __init__(
        self,
        available: Iterable[str],
        bh: BusinessHours,
        has_labels: bool,
    ):
        self.available: Set[str] = set(available)
        self.bh = bh
        self.has_labels = has_labels

        self._acc: Optional[pd.DataFrame] = None
        self._first: Optional[pd.Series] = None
        self._last: Optional[pd.Series] = None

        # Buffer session boundaries across chunks and source files.
        self._session_events: list[
            tuple[str, pd.Timestamp, str]
        ] = []

    def add_chunk(self, ev: pd.DataFrame) -> None:
        if ev.empty:
            return

        ev = ev.copy()
        ev["ts"] = pd.to_datetime(ev["ts"], errors="coerce")
        ev = ev.dropna(subset=["user_id", "ts", "kind"])

        if ev.empty:
            return

        k = ev["kind"]
        off = after_hours_mask(ev["ts"], self.bh)
        is_email = k == "email"

        d = pd.DataFrame(
            {
                "user_id": ev["user_id"].values,
                "day": ev["ts"].dt.floor("D").values,
                "logon_count": (k == "logon").astype(int).values,
                "after_hours_logons": (
                    (k == "logon") & off
                ).astype(int).values,
                "failed_logon_count": (
                    k == "failed_logon"
                ).astype(int).values,
                "file_access_count": (
                    k == "file_access"
                ).astype(int).values,
                "file_copied_removable": np.nan,
                "file_integrity_event_count": (
                    k == "file_integrity"
                ).astype(int).values,
                "email_count": is_email.astype(int).values,
                "email_external_count": (
                    is_email
                    & ev["ext_recipient"].fillna(False).astype(bool)
                ).astype(int).values,
                "email_attachment_count": np.where(
                    is_email, ev["n_attach"].fillna(0), 0
                ),
                "email_total_bytes": np.where(
                    is_email, ev["size"].fillna(0), 0.0
                ),
                "http_request_count": (
                    k == "http"
                ).astype(int).values,
                "http_after_hours_count": (
                    (k == "http") & off
                ).astype(int).values,
                "removable_device_events": (
                    k == "device"
                ).astype(int).values,
                "command_exec_count": (
                    k == "command"
                ).astype(int).values,
                "after_hours_event_count": off.astype(int).values,
                "event_count": 1,
            }
        )

        if self.has_labels:
            if "label" not in ev.columns:
                d["anomalous_event_count"] = np.nan
            else:
                d["anomalous_event_count"] = (
                    ev["label"].fillna(0) == 1
                ).astype(int).values

        # A known removable-copy event is counted only when the adapter
        # provides the feature column for this event.
        if (
            "file_copied_removable" in self.available
            and "file_copied_removable" in ev.columns
        ):
            d["file_copied_removable"] = (
                ev["file_copied_removable"].fillna(0).astype(float).values
            )

        keys = ["user_id", "day"]
        part = d.groupby(keys).sum(min_count=1)

        if self._acc is None:
            self._acc = part
        else:
            self._acc = self._acc.add(part, fill_value=0)

        grouped_ts = ev.assign(
            day=ev["ts"].dt.floor("D"),
        ).groupby(keys)["ts"]

        mn = grouped_ts.min()
        mx = grouped_ts.max()

        if self._first is None:
            self._first = mn
        else:
            self._first = (
                pd.concat([self._first, mn])
                .groupby(level=[0, 1])
                .min()
            )

        if self._last is None:
            self._last = mx
        else:
            self._last = (
                pd.concat([self._last, mx])
                .groupby(level=[0, 1])
                .max()
            )

        session_rows = ev.loc[
            ev["kind"].isin(["logon", "logoff"]),
            ["user_id", "ts", "kind"],
        ]

        self._session_events.extend(
            (
                str(row.user_id),
                pd.Timestamp(row.ts),
                str(row.kind),
            )
            for row in session_rows.itertuples(index=False)
        )

    def finalize(self) -> pd.DataFrame:
        cols = [
            "user_id",
            "date",
            *FEATURE_NAMES,
            "event_count",
            "anomalous_event_count",
            "first_event_at",
            "last_event_at",
        ]

        if self._acc is None:
            return pd.DataFrame(columns=cols)

        a = self._acc.copy().astype("float64")

        # Features unavailable for this dataset must remain missing.
        for name in FEATURE_NAMES:
            if name not in self.available:
                a[name] = np.nan

        if "file_copied_removable" not in self.available:
            a["file_copied_removable"] = np.nan

        a["total_session_duration"] = np.nan

        session_events = sorted(
            self._session_events,
            key=lambda event: (event[0], event[1]),
        )

        open_sessions: dict[str, pd.Timestamp] = {}
        session_duration: dict[
            tuple[str, pd.Timestamp], float
        ] = {}
        invalid_days: set[
            tuple[str, pd.Timestamp]
        ] = set()
        observed_days: set[
            tuple[str, pd.Timestamp]
        ] = set()

        for user, ts, kind in session_events:
            day = ts.floor("D")
            key = (user, day)
            observed_days.add(key)

            if kind == "logon":
                if user in open_sessions:
                    previous_open = open_sessions.pop(user)
                    invalid_days.add(
                        (user, previous_open.floor("D"))
                    )
                    invalid_days.add(key)

                open_sessions[user] = ts

            elif kind == "logoff":
                opened = open_sessions.pop(user, None)

                if opened is None:
                    invalid_days.add(key)
                    continue

                opened_day = opened.floor("D")

                if opened_day != day:
                    invalid_days.add((user, opened_day))
                    invalid_days.add(key)
                    continue

                duration = (ts - opened).total_seconds()

                if duration < 0:
                    invalid_days.add(key)
                    continue

                session_duration[key] = (
                    session_duration.get(key, 0.0) + duration
                )

        for user, opened in open_sessions.items():
            invalid_days.add((user, opened.floor("D")))

        if "total_session_duration" in self.available:
            for key in observed_days:
                if key not in invalid_days and key in a.index:
                    a.loc[
                        key, "total_session_duration"
                    ] = session_duration.get(key, np.nan)

        for key in invalid_days:
            if key in a.index:
                a.loc[
                    key, "total_session_duration"
                ] = np.nan

        if not self.has_labels:
            a["anomalous_event_count"] = np.nan

        a["first_event_at"] = self._first
        a["last_event_at"] = self._last

        a = a.reset_index().rename(columns={"day": "date"})
        a["date"] = pd.to_datetime(a["date"]).dt.date

        a = (
            a.sort_values(["user_id", "date"])
            .reset_index(drop=True)
        )

        return a[cols]