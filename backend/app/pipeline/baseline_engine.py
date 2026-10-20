"""Pure (database-free) personal-baseline maths.

Generation (`compute_baseline`) and evaluation (`score_deviation`) are separate functions.
The history passed to `compute_baseline` is filtered to dates STRICTLY BEFORE `as_of`, so the
observation being judged can never contaminate the baseline that judges it.

All numeric defaults are PROVISIONAL (not tuned on labelled data); see docs/baselines.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional

import numpy as np

from app.pipeline.schema import FEATURE_NAMES

MAD_TO_SIGMA = 1.4826  # consistency constant: MAD * 1.4826 ~ sigma for normal data


@dataclass(frozen=True)
class BaselineConfig:
    version: str = "baseline-v1-provisional"
    min_samples: int = 14            # PROVISIONAL: minimum observed days per feature
    max_window_days: Optional[int] = 90   # PROVISIONAL: trailing window; None = all history
    scale_floor: float = 1.0         # PROVISIONAL: smallest scale (1 event) so zero-variance features stay finite
    z_cap: float = 10.0              # clip |z| so one feature cannot dominate arithmetic
    deviation_flag_z: float = 2.5    # PROVISIONAL: |z| >= this flags a feature as deviant
    top_k: int = 3                   # aggregate = mean of the k largest positive deviations

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clean(values: Iterable[Optional[float]]) -> np.ndarray:
    a = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    return a[np.isfinite(a)]


def compute_baseline(
    history: Mapping[date, Mapping[str, Optional[float]]],
    as_of: date,
    cfg: BaselineConfig = BaselineConfig(),
    feature_names: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Baseline from days strictly before `as_of` (and inside the trailing window).

    Returns {status, window_start, window_end, sample_size, metrics, unusable_features}.
    status: "ok" | "insufficient_history" | "no_history".
    """
    if feature_names is None:   # features actually observed in the history window
        feature_names = [n for n in FEATURE_NAMES if any(n in h for h in history.values())] + sorted(
            {k for h in history.values() for k in h} - set(FEATURE_NAMES))
    feature_names = list(feature_names)
    lo = as_of - timedelta(days=cfg.max_window_days) if cfg.max_window_days else None
    days = sorted(d for d in history if d < as_of and (lo is None or d >= lo))
    if not days:
        return {"status": "no_history", "window_start": None, "window_end": None,
                "sample_size": 0, "metrics": {}, "unusable_features": list(feature_names)}

    metrics: Dict[str, Dict[str, float]] = {}
    unusable: List[str] = []
    for name in feature_names:
        v = _clean(history[d].get(name) for d in days)
        if len(v) < cfg.min_samples:
            unusable.append(name)
            continue
        med = float(np.median(v))
        metrics[name] = {
            "n": int(len(v)),
            "mean": float(v.mean()),
            "std": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
            "median": med,
            "mad": float(np.median(np.abs(v - med))),
            "q25": float(np.percentile(v, 25)),
            "q75": float(np.percentile(v, 75)),
            "max": float(v.max()),
        }
    status = "ok" if metrics else "insufficient_history"
    return {"status": status, "window_start": days[0], "window_end": days[-1],
            "sample_size": len(days), "metrics": metrics, "unusable_features": unusable}


def _scale(m: Mapping[str, float], cfg: BaselineConfig) -> tuple[float, bool]:
    mad = m.get("mad") or 0.0
    scale = MAD_TO_SIGMA * mad if mad > 0 else (m.get("std") or 0.0)
    floored = scale < cfg.scale_floor
    return max(scale, cfg.scale_floor), floored


def score_deviation(
    observed: Mapping[str, Optional[float]],
    metrics: Optional[Mapping[str, Mapping[str, float]]],
    cfg: BaselineConfig = BaselineConfig(),
) -> Dict[str, Any]:
    """Robust z per feature: (x - median) / max(1.4826*MAD | std, scale_floor).

    Only increases are risk-relevant; `aggregate_score` is the mean of the `top_k` largest
    positive z-scores. Features with no baseline or no observation are skipped, never zero-filled.
    """
    if not metrics:
        return {"status": "no_baseline", "aggregate_score": None, "features": [], "skipped": []}
    feats, skipped = [], []
    for name, m in metrics.items():
        x = observed.get(name)
        if x is None or (isinstance(x, float) and math.isnan(x)):
            skipped.append(name)
            continue
        scale, floored = _scale(m, cfg)
        center = m.get("median", m.get("mean", 0.0))
        z = float(np.clip((float(x) - center) / scale, -cfg.z_cap, cfg.z_cap))
        feats.append({
            "feature": name, "observed": float(x), "baseline_center": center,
            "baseline_scale": scale, "z_score": round(z, 3),
            "is_deviant": z >= cfg.deviation_flag_z, "scale_floored": floored,
        })
    if not feats:
        return {"status": "no_comparable_features", "aggregate_score": None, "features": [], "skipped": skipped}
    pos = sorted((f["z_score"] for f in feats if f["z_score"] > 0), reverse=True)[: cfg.top_k]
    agg = float(np.mean(pos)) if pos else 0.0
    feats.sort(key=lambda f: f["z_score"], reverse=True)
    return {"status": "ok", "aggregate_score": round(agg, 3), "features": feats, "skipped": skipped}
