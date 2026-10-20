from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    dashboard,
    users,
    alerts,
    models,
    system,
    pipeline,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(dashboard.router, tags=["Dashboard"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(alerts.router, tags=["Alerts"])
api_router.include_router(models.router, tags=["Models & Evaluation"])
api_router.include_router(system.router, tags=["System & Pipeline"])
api_router.include_router(pipeline.router, tags=["Pipeline, Baselines & Risk"])
