# API Contracts (v1)

Base URL: `/api/v1`

## Health & System
- `GET /api/v1/health`
  - Response: `{ status: "ok" | "degraded", database: "connected" | "disconnected", timestamp: string }`
- `GET /api/v1/system/status`
  - Response: Detailed operational status including database connectivity, CERT dataset file availability, processing pipeline readiness, and model readiness.

## Dashboard
- `GET /api/v1/dashboard/overview`
  - Response: Aggregated statistics from persisted database records:
    - `total_users`: integer
    - `assessed_users`: integer
    - `alerts_by_severity`: `{ critical: int, high: int, medium: int, low: int }`
    - `risk_distribution`: `{ high: int, medium: int, low: int, unassessed: int }`
    - `recent_alerts`: array of Alert objects
    - `highest_risk_users`: array of User Risk summaries
    - `dataset_ready`: boolean
    - `models_ready`: boolean

## Users & Investigation
- `GET /api/v1/users`
  - Query parameters: `page`, `page_size`, `search`, `department`, `min_risk`, `max_risk`, `sort_by`, `sort_dir`
  - Response: Paginated list of users with latest risk score, assessment date, alert count.
- `GET /api/v1/users/{user_id}`
  - Response: User profile metadata, department, role, supervisor, active status.
- `GET /api/v1/users/{user_id}/behavior`
  - Query parameters: `start_date`, `end_date`
  - Response: List of daily behavioral profiles (logons, file accesses, emails, devices, http).
- `GET /api/v1/users/{user_id}/risk`
  - Query parameters: `start_date`, `end_date`
  - Response: Risk evaluation history, component breakdown (ML score, ANN score, Baseline deviation, Hybrid score, Risk level, Contributing factors).

## Alerts & Triage
- `GET /api/v1/alerts`
  - Query parameters: `page`, `page_size`, `severity`, `status`, `search`, `start_date`, `end_date`
  - Response: Paginated alerts with status, reason, risk score, detected timestamp.
- `GET /api/v1/alerts/{alert_id}`
  - Response: Alert details, evidence metrics, contributing factors, related user.
- `PATCH /api/v1/alerts/{alert_id}`
  - Request body: `{ status: "open" | "investigating" | "resolved" | "dismissed", notes?: string }`
  - Response: Updated Alert object.

## Models & Evaluation
- `GET /api/v1/models/status`
  - Response: Readiness, artifact paths, and versions for Random Forest, XGBoost, Autoencoder, and Hybrid Engine.
- `GET /api/v1/models/evaluation`
  - Response: Model evaluation results (precision, recall, f1, roc_auc, confusion matrix) when real experiments have been run; clear unavailable status otherwise.

## Pipeline, baselines and risk (added)
All JSON. Errors: 404 unknown user/file, 400 path outside raw dir/unsupported source, 422 validation.
- `GET /features/schema` — shared feature contract.
- `POST /pipeline/ingest` `{dataset:"spedia"|"cert_r42", path?, force?, cert_file_is_removable_copy?}` → ingestion report (rows read/accepted/rejected by reason, users, user_days, date_range, `unavailable_features`, `users_below_baseline_min_days`, label summary, `skipped` when the identical source+config was already ingested). For CERT, `cert_file_is_removable_copy` defaults to `true` and derives the documented file-event proxy; set it to `false` when that interpretation is not valid. `path` is relative to the raw data dir. Synchronous; use `scripts/run_pipeline.py` for very large inputs.
- `POST /pipeline/baselines/generate` `{user_id?, as_of?}` → `{results:[{user_id,status,persisted,sample_size,window_*,unusable_features}], persisted, skipped}`.
- `GET /users/{user_id}/baseline` → `{has_baseline, baseline}` for the user's active persisted baseline.
- `POST /pipeline/score` `{user_id?, start_date?, end_date?}` → `{users_processed, days_scored, days_without_signal, predictions_written, alerts_upserted, errors}`.
- `POST /risk/evaluate` `{user_id, date, features:{name:number|null}}` → `{assessed, hybrid_risk_score, risk_level, components[], unavailable_components[], contributing_factors[], baseline, config_version, config_provisional}`; nothing persisted; unknown feature names → 422.
- `GET /risk/config`, `GET /pipeline/runs`, `GET /pipeline/summary`.
- Changed: `GET /users/{id}/behavior` profiles now carry flat `features` (null = unavailable), `unavailable_features`, `dataset_source`; `GET /users/{id}/risk` predictions carry `components` and `config_version`; baseline metrics include `n`, `mad`, `max` and `config`.
