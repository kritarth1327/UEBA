import json
import math
from datetime import date, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.baseline import PersonalBaseline
from app.pipeline.baseline_engine import BaselineConfig, compute_baseline, score_deviation
from app.repositories.baseline_repository import BaselineRepository
from app.services.profile_store import load_user_history, list_user_ids_with_profiles


class BaselineService:
    def __init__(self, db: Session, config: Optional[BaselineConfig] = None):
        self.db = db
        self.repo = BaselineRepository(db)
        self.config = config or BaselineConfig(
            min_samples=settings.BASELINE_MIN_SAMPLES,
            max_window_days=settings.BASELINE_MAX_WINDOW_DAYS or None,
            scale_floor=settings.BASELINE_SCALE_FLOOR,
        )

    # ---- generation (writes) ----------------------------------------------------------
    def generate_for_user(self, user_id: str, as_of: Optional[date] = None) -> Dict[str, Any]:
        """Persist the baseline computed from days strictly before `as_of` (default: after the
        user's last observed day). Replaces the active baseline; never duplicates a window."""
        history = load_user_history(self.db, user_id)
        if not history:
            return {"user_id": user_id, "status": "no_history", "persisted": False}
        as_of = as_of or (max(history) + timedelta(days=1))
        res = compute_baseline(history, as_of, self.config)
        out = {"user_id": user_id, "status": res["status"], "as_of": as_of, "sample_size": res["sample_size"],
               "window_start": res["window_start"], "window_end": res["window_end"],
               "unusable_features": res["unusable_features"], "persisted": False}
        if res["status"] != "ok":
            return out
        cfg_json = json.dumps({**self.config.as_dict(), "as_of": str(as_of),
                               "unusable_features": res["unusable_features"]})
        active = self.db.scalars(select(PersonalBaseline).where(
            PersonalBaseline.user_id == user_id, PersonalBaseline.is_active.is_(True))).all()
        for old in active:
            old.is_active = False
        self.db.add(PersonalBaseline(
            user_id=user_id, window_start=res["window_start"], window_end=res["window_end"],
            metrics_json=json.dumps(res["metrics"]), sample_size=res["sample_size"],
            is_active=True, config_json=cfg_json))
        self.db.commit()
        out["persisted"] = True
        return out

    def generate_all(self, as_of: Optional[date] = None) -> List[Dict[str, Any]]:
        return [self.generate_for_user(u, as_of) for u in list_user_ids_with_profiles(self.db)]

    # ---- evaluation (read-only) ----------------------------------------------------------
    def evaluate(self, user_id: str, on: date, observed: Dict[str, Optional[float]],
                 history: Optional[Dict[date, Dict[str, Optional[float]]]] = None) -> Dict[str, Any]:
        """Deviation of `observed` (day `on`) from the baseline built only from days before `on`.
        Uses the persisted active baseline when it ends before `on`; otherwise rebuilds
        point-in-time from stored history so backfills are leak-free."""
        active = self.repo.get_active_by_user(user_id)
        if active and active["window_end"] and active["window_end"] < on and active["metrics"]:
            return {**score_deviation(observed, active["metrics"], self.config), "baseline_source": "persisted"}
        history = history if history is not None else load_user_history(self.db, user_id)
        res = compute_baseline(history, on, self.config)
        if res["status"] != "ok":
            return {"status": res["status"], "aggregate_score": None, "features": [], "skipped": [],
                    "baseline_source": "point_in_time", "sample_size": res["sample_size"]}
        return {**score_deviation(observed, res["metrics"], self.config),
                "baseline_source": "point_in_time", "sample_size": res["sample_size"]}

    def get_user_baseline(self, user_id: str) -> Optional[dict]:
        return self.repo.get_active_by_user(user_id)

    def compare_observed_to_baseline(
        self,
        user_id: str,
        observed: Dict[str, float]
    ) -> Optional[List[Dict[str, Any]]]:
        """Calculates per-metric z-score deviations against the user's personal baseline."""
        baseline = self.get_user_baseline(user_id)
        if not baseline or not baseline.get("metrics"):
            return None

        comparisons = []
        metrics = baseline["metrics"]

        for metric_name, obs_val in observed.items():
            if metric_name in metrics:
                m_info = metrics[metric_name]
                mean = m_info.get("mean", 0.0)
                std = m_info.get("std", 1.0)
                # Safeguard against zero standard deviation
                effective_std = std if std > 1e-4 else 1.0
                z_score = (obs_val - mean) / effective_std
                is_deviant = abs(z_score) >= 2.5

                comparisons.append({
                    "metric_name": metric_name,
                    "observed_value": obs_val,
                    "baseline_mean": mean,
                    "baseline_std": std,
                    "z_score": round(z_score, 2),
                    "is_deviant": is_deviant
                })

        return comparisons
