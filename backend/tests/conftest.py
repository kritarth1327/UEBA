import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Create in-memory SQLite database for isolated test runs
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Yields a clean test database session with tables created."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def test_model_artifacts_unavailable(monkeypatch):
    """Keep integration tests independent of developer-local model artifacts."""
    from app.services.model_interfaces import ScoreResult
    from app.services.ml_threat_service import ml_threat_service
    from app.services.ann_anomaly_service import ann_anomaly_service

    monkeypatch.setattr(
        ml_threat_service,
        "score",
        lambda features: ScoreResult.unavailable(
            "ML model disabled for deterministic tests"
        ),
    )
    monkeypatch.setattr(
        ml_threat_service,
        "is_available",
        lambda: False,
    )
    monkeypatch.setattr(
        ann_anomaly_service,
        "score",
        lambda features: ScoreResult.unavailable(
            "ANN model disabled for deterministic tests"
        ),
    )
    monkeypatch.setattr(
        ann_anomaly_service,
        "is_available",
        lambda: False,
    )
