from typing import Annotated, Literal
import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.errors import NotFoundError
from app.db.models.report import Report
from app.db.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/{report_id}")
def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Report).where(Report.id == report_id)
    report = db.scalar(stmt)
    if not report:
        raise NotFoundError(f"Report {report_id} not found")
    return {"id": report.id, "analysis_id": report.analysis_id, "format": report.format, "created_at": report.created_at}

@router.get("/{report_id}/download")
def download_report(
    report_id: uuid.UUID,
    format: Annotated[Literal["pdf", "html"], Query()] = "html",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Report).where(Report.id == report_id)
    report = db.scalar(stmt)
    if not report:
        raise NotFoundError(f"Report {report_id} not found")

    media_type = "application/pdf" if format == "pdf" else "text/html"
    return FileResponse(
        path=report.storage_path,
        media_type=media_type,
        filename=f"report_{report_id}.{format}"
    )
