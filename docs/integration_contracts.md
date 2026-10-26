# Shared integration contracts (schema v1.0.0)
Single source of truth: `backend/app/pipeline/schema.py` (`GET /api/v1/features/schema`). Changing a name/order bumps `SCHEMA_VERSION`.

## Features (ordered)
`logon_count, after_hours_logons, failed_logon_count, file_access_count, file_copied_removable, file_integrity_event_count,
email_count, email_external_count, email_attachment_count, email_total_bytes, http_request_count, http_after_hours_count,
removable_device_events, total_session_duration, command_exec_count, after_hours_event_count`
Daily user windows; counts are non-negative; `email_total_bytes` in bytes; `total_session_duration` in seconds.

| Availability | SPEDIA | CERT r4.2 |
|---|---|---|
| failed_logon_count, file_integrity_event_count, command_exec_count | yes | no |
| file_copied_removable | no | CERT `file.csv` proxy when `cert_file_is_removable_copy` is true (the ingestion API default); remains unavailable for datasets that do not document this event |
| total_session_duration | no (needs reliable open/close pairing) | no (not implemented) |

**Missing policy:** unavailable ⇒ `null` in APIs / `NaN` in vectors (`vectorize`). Typed DB columns store 0 for legacy
reasons, so always use `features` / `unavailable_features` from the API. Never treat these as real zeros.

## Labels
`event_count`, `anomalous_event_count` live in their own columns, are SPEDIA-only, and are **never model inputs**.

## Model input / output (ML and ANN owners)
Services expose `score(features: Mapping[str, float|None]) -> ScoreResult` (`app/services/model_interfaces.py`):
`status` ∈ ok/unavailable/error; `score` ∈ [0,1] (higher = riskier); `raw`; `model_version`; optional `contributions` {feature: share}.
Out-of-range/NaN scores are converted to `error`; exceptions never reach the engine.

Each artifact needs a JSON contract sidecar in `MODELS_DIR`; without it the service reports `unavailable` instead of guessing feature order:
* ML — `xgboost_threat_classifier.meta.json`: `{"schema_version","feature_names":[...],"model_version"}`. NaN is passed through (tree models).
* ANN — `autoencoder_threshold.json`: the above plus `"threshold"` (reconstruction error at the calibration point, e.g. p95 of
  *validation* error on normal data) and `"preprocessing": {"log1p":bool,"mean":[...],"scale":[...]}`. ANN errors if a required feature is NaN,
  so train it only on features available for the target dataset. Score = `err/(err+threshold)` (0.5 at threshold; provisional mapping).
* Known risk for the ANN owner: `ann_anomaly_service` loads with `torch.load(..., weights_only=True)`, which will not load a pickled whole model; save a state_dict and rebuild the module, or adjust the loader.

## Risk score
Hybrid score 0–100, levels LOW <40 ≤ MEDIUM <70 ≤ HIGH (provisional, configurable); alert severity adds CRITICAL ≥90.

## Database fields added (migration `a1c4e7d90b21`)
`daily_behavior_profiles(dataset_source, event_count, anomalous_event_count)`, `personal_baselines.config_json`,
`model_predictions(components_json, config_version)`, `alerts.source` + unique(user,date,source), table `ingestion_runs`.
Predictions: `ml_threat_score`/`ann_anomaly_score` = normalised [0,1] (null if unavailable); `baseline_deviation_score` = aggregate robust z (raw, ≥0).
