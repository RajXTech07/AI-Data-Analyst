from pathlib import Path
from typing import Annotated, Any
import uuid
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.errors import FileTooLarge, NotFoundError, ValidationFailed
from app.db.models.user import User
from app.schemas.anomaly import AnomalyWorkbenchResponse
from app.schemas.dataset import DatasetOut, DatasetPreview, DatasetProfile
from app.services.anomaly_engine import anomaly_engine
from app.services.datasets import dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])

@router.post("/upload", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename:
        raise ValidationFailed("No filename provided")

    content = await file.read()
    dataset = dataset_service.upload_dataset(
        db=db,
        user_id=current_user.id,
        filename=file.filename,
        content=content
    )
    return dataset

@router.post("/sample", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def load_sample_dataset(
    sample_name: str = "movies_messy.csv",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    valid_samples = ["movies_messy.csv", "sales_data.csv", "synthetic_planted.csv"]
    if sample_name not in valid_samples:
        sample_name = "movies_messy.csv"

    base_dirs = [Path("datasets"), Path("../datasets"), Path.cwd() / "datasets"]
    sample_path = None
    for bd in base_dirs:
        p = bd / sample_name
        if p.is_file():
            sample_path = p
            break

    if not sample_path or not sample_path.is_file():
        raise NotFoundError(f"Sample dataset {sample_name} not found")

    content = sample_path.read_bytes()
    dataset = dataset_service.upload_dataset(
        db=db,
        user_id=current_user.id,
        filename=sample_name,
        content=content
    )
    return dataset

@router.get("", response_model=list[DatasetOut])
def list_datasets(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return dataset_service.list_datasets(db=db, user_id=current_user.id, limit=limit)

@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)

@router.get("/{dataset_id}/profile", response_model=DatasetProfile)
def get_dataset_profile(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    return DatasetProfile.model_validate(dataset.profile)

@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
def get_dataset_preview(
    dataset_id: uuid.UUID,
    rows: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    return dataset_service.get_preview(dataset=dataset, rows=rows)

class CleanDatasetRequest(BaseModel):
    selected_fixes: list[str] = Field(default_factory=list, description="List of fix IDs or fix types to apply")

class UpdateSchemaRequest(BaseModel):
    overrides: dict[str, Any] = Field(description="Dictionary mapping column names to override dicts (e.g. {'dtype': 'numeric', 'semantic_role': 'measure'})")

@router.post("/{dataset_id}/schema", response_model=DatasetProfile)
def update_dataset_schema(
    dataset_id: uuid.UUID,
    payload: UpdateSchemaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    return dataset_service.update_schema(db=db, dataset=dataset, overrides=payload.overrides)

@router.get("/{dataset_id}/issues")
def get_dataset_issues(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    return dataset_service.get_issues(dataset)

@router.get("/{dataset_id}/anomalies", response_model=AnomalyWorkbenchResponse)
def get_dataset_anomalies(
    dataset_id: uuid.UUID,
    column: str,
    method: str = "iqr",
    threshold: float | None = None,
    contamination: float = 0.05,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    df = dataset_service.load_dataframe(dataset, cleaned=True)
    return anomaly_engine.detect_anomalies(
        df=df,
        column=column,
        method=method,
        threshold=threshold,
        contamination=contamination,
        dataset_id=str(dataset.id)
    )

@router.post("/{dataset_id}/clean")
def clean_dataset(
    dataset_id: uuid.UUID,
    payload: CleanDatasetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    cleaned_path, changelog = dataset_service.clean_dataset(
        db=db,
        dataset=dataset,
        selected_fixes=payload.selected_fixes
    )
    return {
        "ok": True,
        "dataset_id": dataset.id,
        "changelog": changelog,
        "download_url": f"/api/v1/datasets/{dataset.id}/clean/download"
    }

@router.get("/{dataset_id}/clean/download")
def download_cleaned_dataset(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    cleaned_path = Path(f"{dataset.storage_path}_cleaned.csv")
    target_path = cleaned_path if cleaned_path.is_file() else Path(dataset.storage_path)
    if not target_path.is_file():
        raise NotFoundError("Dataset file not found")
    
    clean_filename = f"{Path(dataset.filename).stem}_cleaned.csv"
    return FileResponse(
        path=str(target_path),
        media_type="text/csv",
        filename=clean_filename
    )

@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset_service.delete_dataset(db=db, dataset_id=dataset_id, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
