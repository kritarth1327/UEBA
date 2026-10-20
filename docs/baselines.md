# Personal behavioural baselines
**Generation** (`baseline_engine.compute_baseline`, `BaselineService.generate_*`) and **evaluation** (`score_deviation`, `BaselineService.evaluate`) are separate.
* Statistics per feature from days **strictly before** the day judged (`window_end < day`), trailing window (default 90 d): n, mean, std, median, MAD, q25, q75, max. Missing values are skipped, never zero-filled.
* Deviation: robust z = (x − median) / max(1.4826·MAD, or std if MAD = 0, `scale_floor`). |z| capped at 10; features with no baseline/observation are skipped.
  Aggregate = mean of the top-3 positive z (only increases are treated as risky).
* Safe cases: zero variance → scale floor (1 event); fewer than `min_samples` days per feature → feature unusable; no/insufficient history → status `no_history`/`insufficient_history`/`no_baseline` (no score, not 0); new users get nothing until enough history.
* Update policy: `POST /pipeline/baselines/generate` builds a new snapshot (default `as_of` = day after last observation), deactivates the old one. Backfill scoring rebuilds each day's baseline point-in-time from stored profiles so history is never leaky; live scoring uses the persisted baseline only if it ends before the day.
* **All numbers are PROVISIONAL** (min 14 days, window 90, floor 1.0, flag |z| ≥ 2.5, top-3, saturation z = 5): not tuned on labelled data.
* Limitations: a baseline built from all history is contaminated by attacks already in it (irene's SPEDIA history is 85% anomalous events); no weekday/weekend split (too few samples); overlapping features make z-scores correlated.
