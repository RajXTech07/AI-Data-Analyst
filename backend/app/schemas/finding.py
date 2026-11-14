from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class StatEvidence(BaseModel):
    test: str | None = None
    statistic: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    n: int | None = None
    assumptions: dict[str, Any] | None = None

class FindingDraft(BaseModel):
    title: str = Field(max_length=160)
    observation: str
    interpretation: str
    limitations: str
    hypothesis_status: Literal["supported", "rejected", "inconclusive", "descriptive"]
    evidence_execution_ids: list[UUID] = Field(min_length=1)

class FindingOut(FindingDraft):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    statistical_evidence: StatEvidence = Field(default_factory=StatEvidence)
    confidence: Literal["low", "medium", "high"] = "medium"
    chart_ids: list[UUID] = Field(default_factory=list)
