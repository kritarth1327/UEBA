"""Stable scoring interfaces between the risk engine and the ML / ANN components.

Contract (docs/integration_contracts.md):
  * input  : Mapping[feature_name -> float | None] using names from app.pipeline.schema
  * output : ScoreResult; `score` is normalised to [0, 1] (higher = riskier) when status == OK
  * a scorer never raises into the engine: failures are returned as ScoreStatus.ERROR
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Mapping, Optional, Protocol


class ScoreStatus(str, Enum):
    OK = "ok"
    UNAVAILABLE = "unavailable"   # no artifact / contract file; expected during development
    ERROR = "error"               # artifact present but inference or contract check failed


@dataclass
class ScoreResult:
    status: ScoreStatus
    score: Optional[float] = None          # normalised [0, 1]
    raw: Optional[float] = None            # model-native value (probability / reconstruction error)
    model_version: Optional[str] = None
    detail: Optional[str] = None
    # Optional per-feature attribution (feature -> non-negative weight); enables feature-level explanations
    contributions: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def unavailable(cls, detail: str, version: Optional[str] = None) -> "ScoreResult":
        return cls(ScoreStatus.UNAVAILABLE, detail=detail, model_version=version)

    @classmethod
    def error(cls, detail: str, version: Optional[str] = None) -> "ScoreResult":
        return cls(ScoreStatus.ERROR, detail=detail, model_version=version)

    @classmethod
    def ok(cls, score: float, raw: float, version: str, **kw) -> "ScoreResult":
        if not math.isfinite(score) or not (0.0 <= score <= 1.0):
            return cls.error(f"model produced out-of-range score {score!r}", version)
        return cls(ScoreStatus.OK, score=float(score), raw=float(raw), model_version=version, **kw)


class Scorer(Protocol):
    name: str

    def score(self, features: Mapping[str, Optional[float]]) -> ScoreResult: ...


def safe_score(scorer: Scorer, features: Mapping[str, Optional[float]]) -> ScoreResult:
    try:
        res = scorer.score(features)
        if not isinstance(res, ScoreResult):
            return ScoreResult.error("scorer returned a non-ScoreResult value")
        return res
    except Exception as exc:  # engine must never crash on a model failure
        return ScoreResult.error(f"{type(exc).__name__}: {exc}")
