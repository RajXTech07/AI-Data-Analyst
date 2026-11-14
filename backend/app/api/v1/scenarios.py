import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.errors import NotFoundError
from app.db.models.dataset import Dataset
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.schemas.scenario import (
    ScenarioComparisonResponse,
    ScenarioCreateRequest,
    ScenarioOut,
    ScenarioRecomputeRequest,
)
from app.services.datasets import dataset_service
from app.services.scenario_engine import scenario_engine

router = APIRouter(tags=["scenarios"])

@router.post("/datasets/{dataset_id}/scenarios", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def create_dataset_scenario(
    dataset_id: uuid.UUID,
    payload: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db, dataset_id, current_user.id)
    return scenario_engine.create_scenario(db, dataset, payload)

@router.get("/datasets/{dataset_id}/scenarios", response_model=list[ScenarioOut])
def list_dataset_scenarios(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db, dataset_id, current_user.id)
    scenarios = db.query(Scenario).filter(Scenario.dataset_id == dataset.id).all()
    return scenarios

@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise NotFoundError(f"Scenario {scenario_id} not found")
    return scenario

@router.post("/scenarios/{scenario_id}/recompute", response_model=ScenarioComparisonResponse)
def recompute_scenario_comparison(
    scenario_id: uuid.UUID,
    payload: ScenarioRecomputeRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise NotFoundError(f"Scenario {scenario_id} not found")
    return scenario_engine.recompute_scenario(db, scenario, payload)
