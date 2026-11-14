import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.errors import NotFoundError
from app.db.models.analysis import Analysis
from app.db.models.chart import Chart
from app.db.models.chart_version import ChartVersion
from app.db.models.dataset import Dataset
from app.db.models.user import User
from app.schemas.chart import (
    ChartEditRequest,
    ChartSelectionRequest,
    ChartSelectionResponse,
    ChartSpec,
)
from app.services.chart_builder import chart_builder_service
from app.services.datasets import dataset_service

router = APIRouter(prefix="/charts", tags=["charts"])

@router.get("/{chart_id}")
def get_chart(
    chart_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chart = db.get(Chart, chart_id)
    if not chart:
        raise NotFoundError(f"Chart {chart_id} not found")

    return {
        "id": chart.id,
        "analysis_id": chart.analysis_id,
        "chart_type": chart.chart_type,
        "title": chart.title,
        "current_version": chart.current_version,
        "spec": chart.spec
    }

@router.post("/{chart_id}/edit")
def edit_chart_spec(
    chart_id: uuid.UUID,
    payload: ChartEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chart = db.get(Chart, chart_id)
    if not chart:
        raise NotFoundError(f"Chart {chart_id} not found")

    analysis = db.get(Analysis, chart.analysis_id)
    dataset = db.get(Dataset, analysis.dataset_id) if analysis else None
    if not dataset:
        raise NotFoundError("Underlying dataset for chart not found")

    df = dataset_service.load_dataframe(dataset, cleaned=True)
    new_spec, diff = chart_builder_service.edit_chart(db, chart, payload, df)

    return {
        "chart_id": str(chart.id),
        "version": chart.current_version,
        "spec": new_spec.model_dump(),
        "diff": diff
    }

@router.post("/{chart_id}/selection", response_model=ChartSelectionResponse)
def inspect_chart_selection(
    chart_id: uuid.UUID,
    payload: ChartSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chart = db.get(Chart, chart_id)
    if not chart:
        raise NotFoundError(f"Chart {chart_id} not found")

    analysis = db.get(Analysis, chart.analysis_id)
    dataset = db.get(Dataset, analysis.dataset_id) if analysis else None
    if not dataset:
        raise NotFoundError("Underlying dataset for chart not found")

    df = dataset_service.load_dataframe(dataset, cleaned=True)
    return chart_builder_service.inspect_selection(df, chart.spec, payload)

@router.post("/{chart_id}/reset")
def reset_chart_to_original(
    chart_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chart = db.get(Chart, chart_id)
    if not chart:
        raise NotFoundError(f"Chart {chart_id} not found")

    # Fetch version 1
    v1 = db.query(ChartVersion).filter(ChartVersion.chart_id == chart_id, ChartVersion.version == 1).first()
    if not v1:
        # If no explicit v1 stored, current is base
        return {"message": "Chart is already at base version", "version": chart.current_version}

    chart.spec = v1.spec
    chart.chart_type = v1.spec.get("type", chart.chart_type)
    chart.title = v1.spec.get("title", chart.title)
    chart.current_version = 1
    db.commit()
    db.refresh(chart)

    return {
        "message": "Reset chart to original version 1",
        "chart_id": str(chart.id),
        "version": 1,
        "spec": chart.spec
    }

@router.get("/{chart_id}/versions")
def list_chart_versions(
    chart_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chart = db.get(Chart, chart_id)
    if not chart:
        raise NotFoundError(f"Chart {chart_id} not found")

    versions = db.query(ChartVersion).filter(ChartVersion.chart_id == chart_id).order_by(ChartVersion.version.asc()).all()
    return [
        {
            "version": v.version,
            "created_at": v.created_at,
            "diff": v.diff,
            "description": v.description
        }
        for v in versions
    ]
