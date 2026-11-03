from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

_UID_SUFFIX = re.compile(r"\(uid=\d+\)\s*$", re.IGNORECASE)


@dataclass
class IngestStats:
    rows_read: int = 0
    rows_accepted: int = 0
    rejected: Counter = field(default_factory=Counter)   # reason -> count
    missing_sources: List[str] = field(default_factory=list)

    def reject(self, reason: str, n: int) -> None:
        if n:
            self.rejected[reason] += int(n)

    @property
    def rows_rejected(self) -> int:
        return sum(self.rejected.values())

    def as_dict(self) -> Dict:
        return {
            "rows_read": self.rows_read,
            "rows_accepted": self.rows_accepted,
            "rows_rejected": self.rows_rejected,
            "rejected_by_reason": dict(self.rejected),
            "missing_sources": list(self.missing_sources),
        }


def normalize_user(s: pd.Series, domain_prefix: bool = False) -> pd.Series:
    """Trim, lowercase, drop '(uid=N)' suffix and optional 'DOMAIN/' prefix. Blank -> <NA>.

    No fuzzy matching: near-duplicates (e.g. typos) are kept distinct on purpose.
    """
    u = s.astype("string").str.strip()
    u = u.str.replace(_UID_SUFFIX, "", regex=True).str.strip()
    if domain_prefix:
        u = u.str.replace(r"^[^/\\]+[/\\]", "", regex=True)
    u = u.str.lower()
    return u.mask(u.str.len().fillna(0) == 0)


def has_external_recipient(joined: pd.Series, internal_domains: Iterable[str]) -> pd.Series:
    internal = {d.lower() for d in internal_domains}
    doms = joined.fillna("").str.findall(r"@([^;,\s>]+)")
    return doms.apply(lambda ds: any(d.lower() not in internal for d in ds)).astype(bool)


def file_fingerprint(paths: Iterable[Path], full_hash_limit: int = 1 << 30) -> str:
    """Stable content fingerprint. Full SHA-256 below `full_hash_limit` bytes, else
    size + head/tail digest (documented as a fast, non-cryptographic-completeness check)."""
    h = hashlib.sha256()
    for p in sorted(Path(x) for x in paths):
        size = p.stat().st_size
        h.update(p.name.encode()); h.update(str(size).encode())
        with open(p, "rb") as f:
            if size <= full_hash_limit:
                for blk in iter(lambda: f.read(1 << 20), b""):
                    h.update(blk)
            else:
                h.update(f.read(1 << 20)); f.seek(-(1 << 20), 2); h.update(f.read(1 << 20))
    return h.hexdigest()
