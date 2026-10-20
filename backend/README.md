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
