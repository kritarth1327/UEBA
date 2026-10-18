# CERT Insider Threat Dataset Directory

This directory stores raw and processed data for the Hybrid User and Entity Behavior Analytics (UEBA) System.

## Directory Structure

- `raw/`: Unextracted and extracted CERT Insider Threat Dataset r4.2 archives and log files (`logon.csv`, `file.csv`, `device.csv`, `email.csv`, `http.csv`, `psychometric.csv`, `LDAP/`).
- `processed/`: Processed user-day behavioral feature matrices, normalized datasets, train/val/test splits, baseline reference statistics, and label mappings.

## Data Protection Guidelines

1. **Never commit raw log files or processed feature matrices to version control.** They are excluded via `.gitignore`.
2. **Ground Truth Separation**: CERT answer-keys/scenario labels are strictly for offline evaluation and supervised model ground truth. They must never leak into feature engineering or baseline calculations.
3. **Pipeline Ingestion**: When the CERT r4.2 download completes, extract the CSV files directly into `data/raw/r4.2/`.
