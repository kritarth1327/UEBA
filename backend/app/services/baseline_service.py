import math
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.repositories.baseline_repository import BaselineRepository


class BaselineService:
    def __init__(self, db: Session):
        self.repo = BaselineRepository(db)

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
