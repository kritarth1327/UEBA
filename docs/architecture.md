# UEBA System Architecture

## Overview

The Hybrid User and Entity Behavior Analytics (UEBA) System for Insider Threat Detection is designed to detect anomalous and potentially malicious insider activity using enterprise audit logs (CERT Insider Threat Dataset r4.2). The system integrates three complementary detection signals into a unified hybrid risk engine:

1. **Supervised Threat Model (XGBoost / Random Forest)**: Trained on historical labeled threat scenarios and normal baseline activity to identify known threat patterns (e.g. data exfiltration via removable drives, abnormal privilege escalation, off-hours spikes).
2. **Artificial Neural Network Anomaly Detector (Dense Autoencoder)**: Trained exclusively on normal behavioral profiles. High reconstruction error flags unseen, zero-day, or stealthy deviations without requiring prior labels.
3. **Personalized Behavioral Baseline**: Computes longitudinal moving statistics (mean, variance, robust IQR) for each specific user to quantify how much today's activity deviates from that user's own historical normal.

```
+-----------------------------------------------------------------------------------------+
|                                    Enterprise Logs                                      |
|            Logon/Logoff | File Access | Device (USB) | Email Volume | HTTP Web          |
+-----------------------------------------------------------------------------------------+
                                             │
                                             ▼
+-----------------------------------------------------------------------------------------+
|                              Behavioral Feature Pipeline                                |
|    • Clean & map timestamps to user identities                                          |
|    • Daily aggregation into User-Day Behavioral Profiles                                |
|    • Derived metrics (after-hours ratios, external transfers, multi-source indicators)  |
+-----------------------------------------------------------------------------------------+
                       │                                  │
                       ▼                                  ▼
      +---------------------------------+  +-------------------------------+
      |  Personal Baseline Comparator   |  |   ML & Deep Learning Pipeline |
      |  • Historical mean / std dev    |  |   • XGBoost / Random Forest   |
      |  • Per-user anomaly score       |  |   • Dense Autoencoder (ANN)   |
      +---------------------------------+  +-------------------------------+
                       │                                  │
                       └─────────────────┬────────────────┘
                                         ▼
                      +-------------------------------------+
                      |          Hybrid Risk Engine         |
                      |  • Calibrated signal fusion         |
                      |  • Categorized Risk (Low/Med/High)  |
                      |  • Explainable contributing factors |
                      +-------------------------------------+
                                         │
                                         ▼
                      +-------------------------------------+
                      |       Storage & Alerting Layer      |
                      |  • PostgreSQL / SQLite Persistence  |
                      |  • Actionable alert queue           |
                      +-------------------------------------+
                                         │
                                         ▼
                      +-------------------------------------+
                      |           FastAPI REST API          |
                      |  • Dashboard aggregates & KPI       |
                      |  • User investigation endpoints     |
                      |  • Alert management & triage        |
                      |  • Model readiness & status checks  |
                      +-------------------------------------+
                                         │
                                         ▼
                      +-------------------------------------+
                      |     React Security Analyst UI       |
                      |  • Overview Dashboard & Metrics     |
                      |  • User Directory & Search          |
                      |  • Deep User Investigation Console  |
                      |  • Alert Triage Queue               |
                      |  • Model & Evaluation Insights      |
                      |  • System Health & Readiness        |
                      +-------------------------------------+
```

## Service Boundaries

The backend strictly separates:
- **API Endpoints (`app/api/v1`)**: Request validation, HTTP routing, response serialization.
- **Service Layer (`app/services`)**: Business logic, hybrid score calculation, risk thresholding, alert triggering.
- **Repository Layer (`app/repositories`)**: Encapsulated database queries and transactions.
- **Database Models (`app/models`)**: Declarative SQLAlchemy models.
- **Schemas (`app/schemas`)**: Pydantic v2 data contracts.
- **Core (`app/core`)**: Settings, logging, security, configuration.
