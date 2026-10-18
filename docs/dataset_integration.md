# CERT Insider Threat Dataset r4.2 Integration Guide

This guide describes how the CERT Insider Threat Dataset r4.2 connects to this UEBA system once download completes.

## 1. Dataset Overview

The CERT dataset r4.2 contains synthetic enterprise log activity for insider threat detection research:
- `logon.csv`: User logon and logoff events (`id`, `date`, `user`, `pc`, `activity`).
- `device.csv`: USB and removable storage connect/disconnect events (`id`, `date`, `user`, `pc`, `activity`).
- `file.csv`: File operations on removable storage (`id`, `date`, `user`, `pc`, `filename`, `content`).
- `email.csv`: Internal and external email transmissions (`id`, `date`, `user`, `pc`, `to`, `cc`, `bcc`, `from`, `size`, `attachments`, `content`).
- `http.csv`: Web browsing activity (`id`, `date`, `user`, `pc`, `url`, `content`).
- `LDAP/`: Organization hierarchy snapshots by month (`user_id`, `name`, `email`, `role`, `department`, `supervisor`).
- `answers/`: Ground truth insider threat scenarios (exfiltration, sabotage, intellectual property theft). **Restricted to offline evaluation only.**

## 2. Ingestion & Preprocessing Steps

1. **Extraction**:
   Extract raw archive into `data/raw/r4.2/`. Verify expected files are present.
2. **Schema Verification & Date Range Alignment**:
   Run the schema check script to ensure all columns match expected formats and timestamps are parsed in ISO 8601 UTC.
3. **Daily Feature Aggregation**:
   Aggregate raw logs per `(user, date)` into `DailyBehaviorProfile`:
   - `logon_count`, `after_hours_logons` (events before 08:00 or after 18:00 or weekends)
   - `file_access_count`, `file_copied_removable`
   - `email_count`, `email_external_count`, `email_attachment_count`
   - `http_request_count`, `http_after_hours_count`
   - `removable_device_events`
   - Cross-source derived indicators (e.g. after-hours file copy + external email)
4. **Personalized Baseline Calculation**:
   Compute rolling mean and standard deviation on historical training window (e.g. first 90 days of normal activity).
5. **Model Training & Artifact Generation**:
   - Fit XGBoost & Random Forest on training split with ground truth labels.
   - Fit Dense Autoencoder on normal training profiles only.
   - Save model checkpoints to `backend/artifacts/`.
6. **Populate Storage & Run Ingestion**:
   Execute the ingestion service to load users, daily profiles, baseline metrics, model predictions, and alerts into the database.
