from contextlib import asynccontextmanager
import platform
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Initializing UEBA Backend Service...")
    # Ensure necessary folders exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Connected database URL: {settings.DATABASE_URL}")
    yield
    logger.info("Shutting down UEBA Backend Service.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Hybrid User and Entity Behavior Analytics (UEBA) System for Insider Threat Detection",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_local_only(request: Request, call_next):
    if settings.LOCAL_ONLY:
        client_host = request.client.host if request.client else None
        if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "This demonstration service accepts local connections only."},
            )
    return await call_next(request)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception during {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected server error occurred. Please consult backend logs.",
            "path": request.url.path
        }
    )


# Mount versioned API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
def root_status():
    return {
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "api_docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
        "python_version": platform.python_version()
    }
