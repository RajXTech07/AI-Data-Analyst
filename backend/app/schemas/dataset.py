from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class ColumnProfile(BaseModel):
    name: str
    dtype: Literal["numeric", "categorical", "datetime", "boolean", "text"]
    storage_type: str = Field(default="text", description="Low-level storage type: integer, decimal, text, date, datetime, time, boolean.")
    semantic_role: str = Field(
        default="category",
        description="Semantic meaning: identifier, category, measure, amount/currency, percentage, rate, count, duration, year, geographic, free text, constant."
    )
    confidence: Literal["high", "medium", "low"] = Field(default="high", description="Confidence level of type and role inference.")
    confidence_reason: str = Field(default="", description="Statistical evidence supporting the inference.")
    null_pct: float
    unique: int
    invalid_count: int = Field(default=0, description="Count of values that failed to parse for this inferred type.")
    invalid_pct: float = Field(default=0.0, description="Percentage of invalid values for this type.")
    invalid_samples: list[str] = Field(default_factory=list, description="Examples of unparseable values.")
    needs_review: bool = Field(default=False, description="Whether this column has ambiguity requiring user review.")
    review_question: str | None = Field(default=None, description="Specific clarifying question for user review.")
    stats: dict[str, Any] | None = None
    top_values: list[dict[str, Any]] | None = None
    flags: list[str] = Field(default_factory=list)

class DatasetProfile(BaseModel):
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]
    duplicate_rows: int
    missing_total_pct: float
    loading_report: dict[str, Any] | None = None
    health_score: float | None = None
    health_formula: str | None = None
    quality_tier: str | None = None
    schema_overrides: dict[str, Any] | None = None

class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    n_rows: int
    n_cols: int
    size_bytes: int
    created_at: datetime

class DatasetPreview(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
