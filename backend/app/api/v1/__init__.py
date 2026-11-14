from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.analyses import router as analyses_router
from app.api.v1.reports import router as reports_router
from app.api.v1.charts import router as charts_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.metrics import router as metrics_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(analyses_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(charts_router)
api_v1_router.include_router(scenarios_router)
api_v1_router.include_router(metrics_router)

__all__ = ["api_v1_router"]
