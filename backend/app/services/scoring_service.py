
"""Scores persisted user-day profiles with the hybrid engine; persists predictions and alerts."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.alert import Alert
from app.models.behavior import DailyBehaviorProfile
from app.models.prediction import ModelPrediction
from app.services.baseline_service import BaselineService
from app.services.hybrid_risk_service import HybridRiskService, hybrid_risk_service
from app.services.model_interfaces import Scorer
from app.services.cert_supervised_service import cert_supervised_service
from app.services.profile_store import features_of, list_user_ids_with_profiles, load_user_history

ALERT_SOURCE = "hybrid_risk"


class ScoringService:
    def __init__(
        self,
        db: Session,
        engine: Optional[HybridRiskService] = None,
        ml_scorer: Optional[Scorer] = None,
        ann_scorer: Optional[Scorer] = None,
        cert_scorer: Optional[Scorer] = None,
    ):
        self.db = db
        self.engine = engine or hybrid_risk_service
        self.baselines = BaselineService(db)
        self.ml, self.ann = ml_scorer, ann_scorer
        self.cert = cert_scorer or cert_supervised_service

    # ---- ad hoc (nothing persisted) ---------------------------------------------------------
    def assess_features(self, user_id: str, on: date, features: Dict[str, Optional[float]]) -> Optional[Dict[str, Any]]:
        base = self.baselines.evaluate(user_id, on, features)
        if (
            base.get("status") != "ok"
            and self.ml is None
            and self.ann is None
            and not self.cert.is_available()
        ):
            return None
        result = self.engine.assess(features, base, self.ml, self.ann, self.cert)
        if result is not None:
            result["baseline"] = {k: base.get(k) for k in ("status", "baseline_source", "aggregate_score", "sample_size")}
        return result

    # ---- batch (persisted) ----------------------------------------------------------------------
    def score_range(self, user_id: Optional[str] = None, start: Optional[date] = None,
                    end: Optional[date] = None) -> Dict[str, Any]:
        users = [user_id] if user_id else list_user_ids_with_profiles(self.db)
        summary = {"users_processed": 0, "days_scored": 0, "days_without_signal": 0,
                   "predictions_written": 0, "alerts_upserted": 0, "errors": []}
        for uid in users:
            try:
                self._score_user(uid, start, end, summary)
                self.db.commit()
                summary["users_processed"] += 1
            except Exception as exc:  # isolate one user's failure; roll back only that user
                self.db.rollback()
                logger.error(f"scoring failed for {uid}: {exc}", exc_info=True)
                summary["errors"].append({"user_id": uid, "error": f"{type(exc).__name__}: {exc}"})
        return summary

    def _score_user(self, uid: str, start, end, summary) -> None:
        history = load_user_history(self.db, uid)
        q = select(DailyBehaviorProfile).where(DailyBehaviorProfile.user_id == uid)
        if start:
            q = q.where(DailyBehaviorProfile.date >= start)
        if end:
            q = q.where(DailyBehaviorProfile.date <= end)
        for prof in self.db.scalars(q.order_by(DailyBehaviorProfile.date)).all():
            feats = features_of(prof)
            base = self.baselines.evaluate(uid, prof.date, feats, history)
            if (
                base.get("status") != "ok"
                and self.ml is None
                and self.ann is None
                and not self.cert.is_available()
            ):
                summary["days_scored"] += 1
                summary["days_without_signal"] += 1
                continue
            res = self.engine.assess(feats, base, self.ml, self.ann, self.cert)
            summary["days_scored"] += 1
            if res is None:
                summary["days_without_signal"] += 1
                continue
            self._save_prediction(uid, prof.date, res, base)
            summary["predictions_written"] += 1
            if self._upsert_alert(uid, prof.date, res):
                summary["alerts_upserted"] += 1

    def _comp(self, res, name) -> Optional[Dict[str, Any]]:
        return next((c for c in res["components"] if c["name"] == name), None)

    def _save_prediction(self, uid: str, day: date, res: Dict[str, Any], base: Dict[str, Any]) -> None:
        ml, ann, bl = (self._comp(res, n) for n in ("ml_threat", "ann_anomaly", "baseline_deviation"))
        ok = lambda c: c if c and c["status"] == "ok" else None  # noqa: E731
        row = self.db.scalars(select(ModelPrediction).where(
            ModelPrediction.user_id == uid, ModelPrediction.date == day)).first()
        if row is None:
            row = ModelPrediction(user_id=uid, date=day); self.db.add(row)
        row.ml_threat_score = ok(ml) and ml["normalized"]
        row.ann_anomaly_score = ok(ann) and ann["normalized"]
        row.baseline_deviation_score = ok(bl) and bl["raw"]
        row.hybrid_risk_score = res["hybrid_risk_score"]
        row.risk_level = res["risk_level"]
        row.contributing_factors_json = json.dumps([
            {k: f[k] for k in ("feature", "description", "observed_value", "contribution_weight", "baseline_value")}
            for f in res["contributing_factors"]])
        row.components_json = json.dumps({
            "components": res["components"], "contributing_components": res["contributing_components"],
            "unavailable_components": res["unavailable_components"],
            "baseline_only_cap_applied": res["baseline_only_cap_applied"],
            "config_provisional": res["config_provisional"],
            "baseline_source": base.get("baseline_source"), "baseline_sample_size": base.get("sample_size"),
        }, default=str)
        row.config_version = res["config_version"]
        row.model_version = self.engine.version
        row.evaluated_at = datetime.now(timezone.utc)

    def _upsert_alert(self, uid: str, day: date, res: Dict[str, Any]) -> bool:
        score = res["hybrid_risk_score"]
        min_level = self.engine.config.alert_min_level
        if res["risk_level"] == "LOW" or (min_level == "HIGH" and res["risk_level"] != "HIGH"):
            return False
        top = [f["feature"] for f in res["contributing_factors"][:3]]
        reason = f"{res['risk_level']} hybrid risk ({score:.1f}/100)" + (f"; drivers: {', '.join(top)}" if top else "")
        evidence = json.dumps({
            "components": [{k: c[k] for k in ("name", "status", "normalized", "effective_weight", "points")}
                           for c in res["components"]],
            "unavailable_components": res["unavailable_components"],
            "factors": res["contributing_factors"], "config_version": res["config_version"],
            "config_provisional": res["config_provisional"],
        }, default=str)
        alert = self.db.scalars(select(Alert).where(
            Alert.user_id == uid, Alert.date == day, Alert.source == ALERT_SOURCE)).first()
        if alert is None:
            alert = Alert(user_id=uid, date=day, source=ALERT_SOURCE, status="OPEN",
                          severity="LOW", reason=reason)
            self.db.add(alert)
        # analyst-set status/notes are preserved on re-score
        alert.severity = self.engine.severity_for(score)
        alert.reason = reason[:255]
        alert.risk_score = score
        alert.evidence_json = evidence
        return True
