# Hybrid User and Entity Behavior Analytics (UEBA) System

A security analytics platform for insider threat detection using machine learning, artificial neural network anomaly detection, and personalized behavioral baselines.

## Overview

This application aggregates enterprise activity logs (from the CERT Insider Threat Dataset r4.2) into user-day behavioral profiles. It evaluates risk through three complementary detection components:
1. **Supervised Threat Classifier (XGBoost / Random Forest)**: Detects known threat patterns against ground truth labels.
2. **Artificial Neural Network (Dense Autoencoder)**: Reconstructs normal activity; flags novel anomalies via reconstruction error.
3. **Personalized Behavioral Baselines**: Quantifies individual deviation from each employee's historical norms.

The signals are combined in a **Hybrid Risk Engine** to generate calibrated risk levels (Low, Medium, High) accompanied by explainable contributing factors.

## Repository Structure

```text
ueba/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # REST API route handlers
│   │   ├── core/               # Settings, configuration, logging
│   │   ├── db/                 # DB session management & engine
│   │   ├── models/             # SQLAlchemy declarative models
│   │   ├── schemas/            # Pydantic v2 schemas
│   │   ├── services/           # Detection, baselines, risk fusion services
│   │   ├── repositories/       # Encapsulated database queries
│   │   └── main.py             # FastAPI entrypoint
│   ├── tests/                  # Pytest test suite
│   ├── alembic/                # Database migrations
│   ├── requirements.txt        # Backend dependencies
│   ├── .env.example            # Environment template
│   └── README.md               # Backend guide
├── frontend/
│   ├── src/
│   │   ├── api/                # Centralized API client
│   │   ├── components/         # Reusable UI components
│   │   ├── layouts/            # Application layout shell
│   │   ├── pages/              # 6 Core security analytics views
│   │   ├── hooks/              # Data fetching & state hooks
│   │   ├── utils/              # Formatting & helper utilities
│   │   ├── styles/             # Scoped CSS stylesheets
│   │   └── App.jsx             # React router & root component
│   ├── public/                 # Static assets
│   ├── package.json            # Frontend dependencies
│   ├── vite.config.js          # Vite build configuration
│   └── .env.example            # Frontend environment template
├── data/
│   ├── raw/                    # CERT dataset archives & CSVs (excluded from Git)
│   ├── processed/              # Aggregated behavioral features & splits
│   └── README.md
├── docs/                       # Architecture, API contracts, and integration docs
├── .gitignore
└── README.md
```

## Quick Start

### Backend Setup
1. Open PowerShell and navigate to `backend/`:
   ```powershell
   cd backend
   ```
2. Set up environment variables:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Run migrations:
   ```powershell
   python -m alembic upgrade head
   ```
5. Start the backend API:
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

### Frontend Setup
1. Open a new terminal and navigate to `frontend/`:
   ```powershell
   cd frontend
   ```
2. Set up environment variables:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Install Node.js dependencies:
   ```powershell
   npm install
   ```
4. Run the development server:
   ```powershell
   npm run dev
   ```
5. Open `http://localhost:5173` in your browser.

## Running Tests
- Backend tests:
  ```powershell
  cd backend
  python -m pytest tests/ -v
  ```
