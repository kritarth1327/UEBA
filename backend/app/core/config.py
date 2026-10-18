import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load .env file from backend root or current directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()


class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "UEBA Threat Detection API")
    API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ueba.db")

    # CORS origins as list
    _cors_str: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    )
    CORS_ORIGINS: List[str] = [origin.strip() for origin in _cors_str.split(",") if origin.strip()]

    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR.parent / "data")))
    RAW_DATA_DIR: Path = Path(os.getenv("RAW_DATA_DIR", str(BASE_DIR.parent / "data" / "raw")))
    PROCESSED_DATA_DIR: Path = Path(os.getenv("PROCESSED_DATA_DIR", str(BASE_DIR.parent / "data" / "processed")))
    MODELS_DIR: Path = Path(os.getenv("MODELS_DIR", str(BASE_DIR / "artifacts")))


settings = Settings()
