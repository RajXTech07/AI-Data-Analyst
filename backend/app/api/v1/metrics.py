from fastapi import APIRouter
from app.core.config import settings
from app.services.calc_cache import calc_cache
from app.services.columnar_engine import get_process_memory_mb

router = APIRouter(prefix="/metrics", tags=["observability"])

@router.get("")
def get_system_metrics():
    current_rss_mb = get_process_memory_mb()
    budget_mb = settings.MEMORY_BUDGET_MB

    return {
        "status": "healthy" if current_rss_mb < budget_mb else "degraded",
        "memory": {
            "rss_mb": round(current_rss_mb, 2),
            "budget_mb": budget_mb,
            "utilization_pct": round((current_rss_mb / budget_mb * 100.0) if budget_mb else 0.0, 2),
            "within_budget": current_rss_mb <= budget_mb
        },
        "limits": {
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "max_rows_exact": settings.MAX_ROWS_EXACT,
            "tool_timeout_seconds": settings.TOOL_TIMEOUT_SECONDS,
            "max_plot_points": settings.MAX_PLOT_POINTS
        },
        "cache": {
            "cached_entries": len(calc_cache._cache)
        }
    }
