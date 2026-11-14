from datetime import datetime
from typing import Any, Literal
import uuid
from pydantic import BaseModel, Field

class ScenarioOperationCreate(BaseModel):
    op_type: Literal[
        "filter",
        "exclude_rows",
        "override_value",
        "threshold",
        "imputation",
        "merge_groups",
        "unit_conversion"
    ]
    parameters: dict[str, Any]
    reason: str | None = None

class ScenarioCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    operations: list[ScenarioOperationCreate] = Field(default_factory=list)

class ScenarioOperationOut(BaseModel):
    id: uuid.UUID
    seq: int
    op_type: str
    parameters: dict[str, Any]
    reason: str | None
    created_at: datetime

class ScenarioOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    operations: list[ScenarioOperationOut] = Field(default_factory=list)

class MetricComparison(BaseModel):
    metric_name: str
    baseline_value: float | None
    scenario_value: float | None
    absolute_change: float | None
    percentage_change: float | None
    conclusion_flipped: bool = False
    is_fragile: bool = False
    explanation: str

class ScenarioRecomputeRequest(BaseModel):
    target_columns: list[str] | None = None
    recompute_findings: bool = True
    recompute_correlations: bool = True

class ScenarioComparisonResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    dataset_id: str
    rows_affected: int
    fraction_affected: float
    warning_triggered: bool = False
    metrics: list[MetricComparison]
    fragile_findings: list[str] = Field(default_factory=list)
    scenario_findings: list[dict[str, Any]] = Field(default_factory=list)
    explain: dict[str, Any] = Field(default_factory=dict)
