# UEBA Backend Service

FastAPI-powered backend for User and Entity Behavior Analytics (UEBA), handling user investigations, daily behavioral profile aggregation, personal baselines, anomaly and threat model inference, and alert management.

## Python Compatibility

- **Python Version**: 3.14.7 (Active)
- **Dependency Status**: All core libraries (FastAPI, SQLAlchemy, Pydantic, Alembic, NumPy, Pandas, Scikit-learn, XGBoost, PyTorch, psycopg2) have verified prebuilt binary cp314 wheels.

## Directory Structure

```text
backend/
├── alembic/                # Database migrations
├── app/
│   ├── api/v1/endpoints/   # REST API endpoints (health, dashboard, users, alerts, models, system)
│   ├── core/               # Configuration settings & logging
│   ├── db/                 # Database session & Base model
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic validation schemas
│   ├── repositories/       # Database access abstractions
│   ├── services/           # Detection & analytical service layer
│   └── main.py             # FastAPI entrypoint
├── tests/                  # Pytest test suite
├── alembic.ini             # Alembic configuration
├── requirements.txt        # Dependency definitions
└── README.md
```

## Running the Backend

1. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
2. Apply database migrations:
   ```powershell
   python -m alembic upgrade head
   ```
3. Start the development server:
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
4. Access the interactive API docs at `http://127.0.0.1:8000/docs`.

The default `LOCAL_ONLY=true` setting rejects non-local client connections. This
MVP has no authentication layer; do not set `LOCAL_ONLY=false` or expose the
service through a network boundary without adding authentication and access
controls.

## Running Tests

Execute the comprehensive test suite with:
```powershell
python -m pytest tests/ -v
```

## Pipeline (ingest -> baselines -> score)
```bash
cd backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
python scripts/audit_spedia.py /path/to/logs_SPEDIA_annotated_en.csv          # optional leakage/quality audit
python scripts/run_pipeline.py all --dataset spedia --path /path/to/logs_SPEDIA_annotated_en.csv
python -m pytest -q
python -m uvicorn app.main:app --port 8000
```
Raw data stays out of Git (`data/raw/*` is ignored). To use the API ingest endpoint, place the file at `data/raw/spedia/` (or set `SPEDIA_FILE`).
See `docs/dataset_selection.md`, `docs/integration_contracts.md`, `docs/baselines.md`, `docs/risk_engine.md`.

The API can run ingestion, scoring, prediction persistence, and alert upserts in
one explicit operation by sending `"score_after_ingest": true` to
`POST /api/v1/pipeline/ingest`. The default remains `false` for compatibility.
For CERT profiles, unavailable `total_session_duration` is preserved as
unavailable in the stored feature payload but is explicitly zero-filled at the
ANN scoring boundary before `log1p` and the saved scaler. Other missing or
non-finite ANN features remain errors. This zero policy is a candidate
assumption, not a claim about historical training.

### Reproducible ANN candidate training

The missing historical ANN training program is not reproduced. The replacement
trainer matches the production dense-autoencoder architecture and feature order,
uses chronological splits, fits `log1p` and `StandardScaler` on training rows
only, early-stops on validation loss, and calibrates the threshold from the
validation 99th percentile only. `total_session_duration` is unavailable in the
CERT feature table, so training requires an explicit policy; historical handling
is unknown. Candidate outputs are written under `backend/ann_candidates/`, never
to `backend/artifacts/`.

For example, after dependencies are installed:

```powershell
python backend/scripts/train_dense_autoencoder.py --total-session-duration-policy zero
```

The demonstrated local workflow uses `logs_SPEDIA_annotated_en.csv`, which
produces 13 normalized users and 181 user-day profiles in the included local
demonstration database. The separate CERT supervised model is trained and
evaluated from CERT r4.2 data using incident-window proxy labels. Those metrics
do not establish validated real-world insider-threat detection performance.
