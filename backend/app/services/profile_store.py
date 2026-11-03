"""Read helpers that turn persisted user-day profiles into schema-named feature dicts."""
from __future__ import annotations

import json
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.behavior import DailyBehaviorProfile
from app.pipeline.schema import FEATURE_NAMES, TYPED_COLUMN_FEATURES


def features_of(p: DailyBehaviorProfile) -> Dict[str, Optional[float]]:
    """Unavailable features -> None (never a fabricated 0)."""
    if p.features_json:
        try:
            f = json.loads(p.features_json).get("features")
            if isinstance(f, dict):
                return {n: f.get(n) for n in FEATURE_NAMES}
        except (ValueError, AttributeError):
            pass
    # Legacy rows with only typed columns
    out: Dict[str, Optional[float]] = {n: None for n in FEATURE_NAMES}
    for n in TYPED_COLUMN_FEATURES:
        out[n] = getattr(p, n)
    return out


def load_user_history(db: Session, user_id: str) -> Dict[date, Dict[str, Optional[float]]]:
    rows = db.scalars(select(DailyBehaviorProfile).where(DailyBehaviorProfile.user_id == user_id)
                      .order_by(DailyBehaviorProfile.date))
    return {r.date: features_of(r) for r in rows}


def list_user_ids_with_profiles(db: Session) -> List[str]:
    return list(db.scalars(select(DailyBehaviorProfile.user_id).distinct().order_by(DailyBehaviorProfile.user_id)))
