"""CERT Insider Threat r4.2 adapter.

Built from the documented r4.2 CSV layout (logon, device, file, email, http). NOT yet run against
the real multi-GB files in this environment (the dataset is unavailable here); covered by small
fixtures only. Verify column names / date format against the real files before a full run.
Content columns (file content, email body, URL, page content) are never read.
CERT r4.2 has no per-event labels: ground truth (answers/) is user-level and is not loaded here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from app.pipeline.adapters.base import IngestStats, has_external_recipient, normalize_user
from app.pipeline.schema import CERT_R42, available_features

DATE_FORMAT = "%m/%d/%Y %H:%M:%S"
FILES = ("logon.csv", "device.csv", "file.csv", "email.csv", "http.csv")
_COLS = {
    "logon.csv": ["id", "date", "user", "activity"],
    "device.csv": ["id", "date", "user", "activity"],
    "file.csv": ["id", "date", "user"],
    "email.csv": ["id", "date", "user", "to", "cc", "bcc", "size", "attachments"],
    "http.csv": ["id", "date", "user"],
}


def _count_attachments(s: pd.Series) -> pd.Series:
    num = pd.to_numeric(s, errors="coerce")
    listed = s.fillna("").astype(str).str.count(";") + s.fillna("").astype(str).str.strip().ne("").astype(int)
    return num.fillna(listed.where(num.isna()))


class CertR42Adapter:
    name = CERT_R42
    has_labels = False
    # Conventional enterprise assumption; verify against the real r4.2 weekend activity before relying on it.
    weekend_is_after_hours = True

    def __init__(self, internal_domains=("dtaa.com",), file_is_removable_copy: bool = False):
        """`file_is_removable_copy`: set True only after confirming file.csv rows are removable-media
        copies in the dataset documentation; otherwise file_copied_removable stays unavailable."""
        self.internal_domains = tuple(internal_domains)
        self.file_is_removable_copy = file_is_removable_copy
        self.available = available_features(CERT_R42, ["file_copied_removable"] if file_is_removable_copy else None)

    def source_files(self, directory) -> list[Path]:
        d = Path(directory)
        return [d / f for f in FILES if (d / f).exists()]

    def iter_events(self, directory, chunksize: int, stats: IngestStats) -> Iterator[pd.DataFrame]:
        d = Path(directory)
        for fname in FILES:
            p = d / fname
            if not p.exists():
                stats.missing_sources.append(fname)
                continue
            reader = pd.read_csv(p, usecols=_COLS[fname], chunksize=chunksize, dtype=str,
                                 on_bad_lines="skip", encoding_errors="replace")
            for raw in reader:
                stats.rows_read += len(raw)
                ev = self._normalise(fname, raw, stats)
                if ev is not None and not ev.empty:
                    stats.rows_accepted += len(ev)
                    yield ev

    def _normalise(self, fname: str, df: pd.DataFrame, stats: IngestStats) -> Optional[pd.DataFrame]:
        dup = df["id"].duplicated()
        stats.reject("duplicate_event_id", dup.sum()); df = df[~dup]
        ts = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
        bad = ts.isna(); stats.reject("bad_timestamp", bad.sum())
        df, ts = df[~bad], ts[~bad]
        user = normalize_user(df["user"], domain_prefix=True)
        nou = user.isna(); stats.reject("missing_user", nou.sum())
        df, ts, user = df[~nou], ts[~nou], user[~nou]

        n = len(df)
        kind = pd.Series("", index=df.index, dtype="object")
        n_attach = pd.Series(float("nan"), index=df.index); size = n_attach.copy()
        ext = pd.Series(False, index=df.index)
        if fname in ("logon.csv", "device.csv"):
            act = df["activity"].str.strip().str.lower()
            if fname == "logon.csv":
                kind = act.map({"logon": "logon", "logoff": "logoff"})
            else:
                kind = act.map({"connect": "device", "disconnect": "device"})
            unk = kind.isna(); stats.reject("unrecognised_event_type", unk.sum())
            df, ts, user, kind = df[~unk], ts[~unk], user[~unk], kind[~unk]
            n_attach, size, ext = n_attach[~unk], size[~unk], ext[~unk]
        elif fname == "file.csv":
            kind[:] = "file_access"
        elif fname == "http.csv":
            kind[:] = "http"
        elif fname == "email.csv":
            kind[:] = "email"
            n_attach = _count_attachments(df["attachments"])
            size = pd.to_numeric(df["size"], errors="coerce")
            joined = df["to"].fillna("") + ";" + df["cc"].fillna("") + ";" + df["bcc"].fillna("")
            ext = has_external_recipient(joined, self.internal_domains)
        out = pd.DataFrame({
            "user_id": user.astype(str).values, "ts": ts.values, "kind": kind.values,
            "n_attach": n_attach.values, "size": size.values, "ext_recipient": ext.values,
            "label": pd.array([pd.NA] * len(user), dtype="Int8"),
        })
        if self.file_is_removable_copy:
            out["file_copied_removable"] = (out["kind"] == "file_access").astype(int)
        return out
