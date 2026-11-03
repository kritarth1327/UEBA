# Dataset selection: SPEDIA vs CERT r4.2

Evidence from `backend/scripts/audit_spedia.py` run on `logs_SPEDIA_annotated_en.csv` (reproducible).

## SPEDIA facts (verified, not assumed)
| Item | Value |
|---|---|
| Rows / columns | 72,250 / 24; no duplicate rows or ids; 0 bad timestamps |
| Coverage | 2025-03-06 → 2025-03-30 (25 days) |
| User strings | 17 raw → 13 after normalising (`root(uid=0)`→`root`); 1,372 events (1.9%) have no user |
| Activities | http 21,723; email 18,203; file 12,405; command 10,114; session 5,399; device 4,406 |
| Labels | Anomaly=1: 41,541 (57.5%); 0: 30,709 |
| Users with benign history | camilo, humberto, irene, olaya, root (25 days each). delia, gdm, impresora, luis, nuria, ubuntu, wazuh appear **only** in anomalous events |

## Leakage (critical)
* **`Anomaly == 1` exactly when `Agent_name` is not a `*_simulation` agent** (verified on all 72,250 rows). The label records
  *which log source produced the event* (benign simulator vs. attack-run hosts), not a judged behaviour. `Agent_name`
  (including `attacker_*` names) and, indirectly, `User` (7 users never appear benign) are label proxies.
  The adapter never reads `Agent_name`, and `User` must not be a model input.
* Wazuh `Level`/`Description` are rule-engine outputs (Level 12 occurs only in anomalous rows). They are excluded to avoid
  circular detection. Content columns (`Full_log`, `Content`, `Url`, `Command`, `Filename`, `Path`, `From`) are never read.
* Labels are event-level, simulated/annotated attacks overlaid on a benign simulation, not real insider behaviour.
* Anomalies concentrate late (23–30 Mar; 30 Mar is 93% anomalous), so a chronological split puts almost all positives in
  the test period; a random split leaks routine across days. Grouped-by-user splits are impossible for 7 of 13 entities.
* `Timestamp` is used as-is: host syslog text differs from `Timestamp` by 0 or +1 h depending on host, so no tz conversion is safe.
* Benign simulated users are active on weekends exactly like weekdays (1,234 vs 1,226 events/day), so weekends are **not**
  after-hours for this adapter (configurable). Applying the CERT-style rule produced false deviations on benign weekend days.

## Decision
| Capability | SPEDIA | CERT r4.2 |
|---|---|---|
| Supervised training at user-day level | **Weak**: 4–5 users × 25 days, label = provenance | Intended primary (≈1000 users, ~500 days, 70 insiders) — *not verifiable here, dataset absent* |
| ANN trained on normal behaviour | Only ~100 benign user-days | Suitable |
| Personal baselines | Short (25 d; min 14 d leaves ≤11 scored days/user) | Suitable |
| Realism | Simulated + annotated | Synthetic but widely used |
| Extra signals | Commands, failed logons, file-integrity | logon/device/file/email/http only |

**CERT r4.2 remains the intended primary dataset for model training/evaluation; SPEDIA is a secondary, integration-and-demo
dataset** whose extra signals (commands, failed logons) are kept in the shared schema. Both go through separate adapters
into one schema. The existing repo had **no CERT ingestion code** (docs only); a CERT adapter now exists but has only been
tested on small fixtures built from the documented layout (the real files were not available), so verify column names,
date format, and the `file.csv` removable-media semantics on first real run.
This is a recommendation based on dataset properties, not on measured model results — none exist yet.
