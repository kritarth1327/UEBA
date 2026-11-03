# Hybrid risk engine
score = 100 × Σ wᵢ·sᵢ over **available** components (weights re-normalised over available ones). sᵢ ∈ [0,1]: ML probability; ANN `err/(err+threshold)`; baseline `min(1, aggregate_z / 5)`.
* Defaults (**PROVISIONAL, unvalidated**): ML 0.45, ANN 0.35, baseline 0.20; MEDIUM ≥ 40, HIGH ≥ 70, CRITICAL (alerts) ≥ 90. Override with `RISK_CONFIG_PATH` JSON; set `provisional: false` and a new `version` only after evaluation.
* Unavailable/errored components are listed (`status`, `detail`), contribute 0 weight, and appear as `null` — not as zero. No usable component ⇒ no prediction stored.
* Baseline-only evidence is capped at 69.0 (below HIGH) because it is uncalibrated against labels.
* Double counting: baseline and ANN read the same daily features, so they are correlated. Mitigations are limited to the baseline-only cap and one explanation entry per feature listing all `sources`; no statistical de-correlation is applied.
* Persisted per day: scores, `components_json` (status, normalised score, effective weight, points), `config_version`. Alerts: one per (user, date, source); re-scoring keeps analyst status/notes.
