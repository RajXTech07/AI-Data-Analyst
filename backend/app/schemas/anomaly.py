from typing import Any, Literal
import uuid
from pydantic import BaseModel, Field

class AnomalyFlaggedRecord(BaseModel):
    row_index: int
    value: Any
    score: float
    classification: Literal["impossible (data error)", "statistical outlier (may be real)", "contextual anomaly (unusual for its group/time)"]
    confidence: Literal["High", "Medium", "Low"]
    reason: str

class AnomalyImpactMetric(BaseModel):
    metric: str
    baseline: float | None
    scenario_without_anomalies: float | None
    absolute_change: float | None
    percentage_change: float | None

class AnomalyImpactComparison(BaseModel):
    column: str
    metrics: list[AnomalyImpactMetric]
    substantive_impact: bool = False
    summary: str

class AnomalyWorkbenchResponse(BaseModel):
    dataset_id: str
    column: str
    method: str
    threshold: float | None
    parameters: dict[str, Any]
    total_evaluated: int
    flagged_count: int
    flagged_percentage: float
    flagged_records: list[AnomalyFlaggedRecord]
    impact_comparison: AnomalyImpactComparison
    available_actions: list[str] = Field(default_factory=lambda: ["keep", "exclude", "mark_as_error", "set_to_missing", "add_note"])
    explain: dict[str, Any] = Field(default_factory=dict)
