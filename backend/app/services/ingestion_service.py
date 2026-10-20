"""Dataset ingestion: adapter -> chunked aggregation -> idempotent upsert of user-day profiles."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.behavior import DailyBehaviorProfile
from app.models.ingestion import IngestionRun
from app.models.user import User
from app.pipeline.adapters.base import IngestStats, file_fingerprint
from app.pipeline.adapters.cert import CertR42Adapter
from app.pipeline.adapters.spedia import SpediaAdapter
from app.pipeline.features import BusinessHours, DailyAggregator
from app.pipeline.schema import (CERT_R42, FEATURE_NAMES, SCHEMA_VERSION, SPEDIA, FEATURE_BY_NAME)

SUPPORTED = (SPEDIA, CERT_R42)


class IngestionError(Exception):
    """Raised for caller-fixable problems (unknown dataset, missing file, path outside raw dir)."""


def resolve_raw_path(path: Optional[str], default: Path, raw_root: Path, allow_outside: bool = False) -> Path:
    """Resolve an input path. API callers are confined to RAW_DATA_DIR; the CLI may opt out."""
    p = Path(path) if path else default
    if path and not p.is_absolute():
        p = raw_root / p
    p = p.resolve()
    if not allow_outside and not p.is_relative_to(raw_root.resolve()):
        raise IngestionError("path must be inside the configured raw data directory")
    return p


def _num(v) -> Optional[float]:
    if v is None:
        return None
    f = float(v)
    return None if math.isnan(f) else f


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def _adapter(self, dataset: str, cert_file_is_removable_copy: bool):
        if dataset == SPEDIA:
            return SpediaAdapter(settings.INTERNAL_EMAIL_DOMAINS)
        if dataset == CERT_R42:
            return CertR42Adapter(settings.INTERNAL_EMAIL_DOMAINS, cert_file_is_removable_copy)
        raise IngestionError(f"unsupported dataset '{dataset}'; supported: {', '.join(SUPPORTED)}")

    def ingest(self, dataset: str, path: Optional[str] = None, force: bool = False,
               chunksize: Optional[int] = None, allow_outside_raw_dir: bool = False,
               cert_file_is_removable_copy: bool = False) -> Dict[str, Any]:
        adapter = self._adapter(dataset, cert_file_is_removable_copy)
        default = settings.SPEDIA_FILE if dataset == SPEDIA else settings.CERT_R42_DIR
        src = resolve_raw_path(path, default, settings.RAW_DATA_DIR, allow_outside_raw_dir)
        if not src.exists():
            raise IngestionError(f"dataset source not found: {src.name}")
        files = [src] if src.is_file() else adapter.source_files(src) if dataset == CERT_R42 else []
        if not files:
            raise IngestionError("no ingestible files found at the given path")

        bh = BusinessHours(settings.BUSINESS_HOURS_START, settings.BUSINESS_HOURS_END,
                           adapter.weekend_is_after_hours)
        cfg = {"schema": SCHEMA_VERSION, "dataset": dataset,
               "bh": [bh.start, bh.end, bh.weekend_is_after_hours],
               "internal": list(settings.INTERNAL_EMAIL_DOMAINS), "cert_removable": cert_file_is_removable_copy}
        fp = hashlib.sha256((file_fingerprint(files) + json.dumps(cfg, sort_keys=True)).encode()).hexdigest()

        prior = self.db.scalars(select(IngestionRun).where(
            IngestionRun.fingerprint == fp, IngestionRun.status == "completed")).first()
        if prior and not force:
            report = json.loads(prior.report_json or "{}")
            report.update({"skipped": True, "reason": "identical source + configuration already ingested",
                           "run_id": prior.id})
            return report

        run = IngestionRun(dataset=dataset, fingerprint=fp, source_path=src.name,
                           schema_version=SCHEMA_VERSION, status="running")
        self.db.add(run); self.db.commit()
        try:
            report = self._run(adapter, dataset, src, bh, chunksize or settings.INGEST_CHUNK_SIZE)
            run.status, run.report_json = "completed", json.dumps(report, default=str)
            run.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            report.update({"skipped": False, "run_id": run.id})
            return report
        except Exception as exc:
            self.db.rollback()
            logger.error(f"ingestion run {run.id} failed: {exc}", exc_info=True)
            run = self.db.get(IngestionRun, run.id)
            run.status, run.error = "failed", f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            raise

    def _run(self, adapter, dataset: str, src: Path, bh: BusinessHours, chunksize: int) -> Dict[str, Any]:
        stats = IngestStats()
        agg = DailyAggregator(adapter.available, bh, adapter.has_labels)
        for ev in adapter.iter_events(src, chunksize, stats):
            agg.add_chunk(ev)
        days = agg.finalize()
        if days.empty:
            raise IngestionError("no valid events after validation; nothing to ingest")
        counts = self._upsert(dataset, days)
        unavailable = [n for n in FEATURE_NAMES if n not in adapter.available]
        rep = {
            "dataset": dataset, "schema_version": SCHEMA_VERSION, **stats.as_dict(),
            "users": int(days["user_id"].nunique()), "user_days": int(len(days)),
            "date_range": [str(days["date"].min()), str(days["date"].max())],
            "unavailable_features": unavailable,
            **counts,
            "users_below_baseline_min_days": sorted(
                days.groupby("user_id").size().loc[lambda s: s < settings.BASELINE_MIN_SAMPLES].index.tolist()),
        }
        if adapter.has_labels:
            g = days.groupby("user_id")[["event_count", "anomalous_event_count"]].sum()
            rep["users_with_only_labelled_anomalous_events"] = sorted(
                g.index[g["anomalous_event_count"] >= g["event_count"]].tolist())
            rep["label_summary"] = {"events": int(days["event_count"].sum()),
                                    "anomalous_events": int(days["anomalous_event_count"].sum())}
        return rep

    def _upsert(self, dataset: str, days: pd.DataFrame) -> Dict[str, int]:
        """Single transaction (committed by caller). Re-ingesting updates rows in place."""
        existing_users = set(self.db.scalars(select(User.user_id)))
        new_users = [u for u in days["user_id"].unique() if u not in existing_users]
        self.db.add_all(User(user_id=u) for u in new_users)
        self.db.flush()

        have = {(r.user_id, r.date): r for r in self.db.scalars(
            select(DailyBehaviorProfile).where(DailyBehaviorProfile.user_id.in_(days["user_id"].unique().tolist())))}
        inserted = updated = conflicts = 0
        for row in days.to_dict("records"):
            feats = {n: _num(row[n]) for n in FEATURE_NAMES}
            unavailable = [n for n, v in feats.items() if v is None]
            payload = {
                "schema_version": SCHEMA_VERSION, "dataset_source": dataset,
                "features": feats, "unavailable_features": unavailable,
                "first_event_at": str(row["first_event_at"]), "last_event_at": str(row["last_event_at"]),
            }
            cols = {n: (0 if feats[n] is None else (int(feats[n]) if FEATURE_BY_NAME[n].dtype == "int" else feats[n]))
                    for n in FEATURE_NAMES if FEATURE_BY_NAME[n].db_column}
            lab = _num(row["anomalous_event_count"])
            vals = dict(cols, dataset_source=dataset, event_count=int(row["event_count"]),
                        anomalous_event_count=None if lab is None else int(lab),
                        features_json=json.dumps(payload))
            cur = have.get((row["user_id"], row["date"]))
            if cur is None:
                self.db.add(DailyBehaviorProfile(user_id=row["user_id"], date=row["date"], **vals)); inserted += 1
            elif cur.dataset_source not in (None, dataset):
                conflicts += 1   # never overwrite another dataset's user-day
            else:
                for k, v in vals.items():
                    setattr(cur, k, v)
                updated += 1
        return {"users_created": len(new_users), "profiles_inserted": inserted,
                "profiles_updated": updated, "profiles_conflicting_dataset": conflicts}
