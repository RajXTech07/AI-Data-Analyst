from typing import Annotated
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.config import settings

router = APIRouter(tags=["health"])

@router.get("/health", status_code=status.HTTP_200_OK)
@router.get("/healthz", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "ok"}

@router.get("/readyz", status_code=status.HTTP_200_OK)
def readiness_check(db: Annotated[Session, Depends(get_db)]):
    checks = {"database": "ok", "storage": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    if not settings.resolved_storage_path.is_dir():
        checks["storage"] = "error: storage directory missing"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content={"status": "ready" if all_ok else "unready", "checks": checks})
