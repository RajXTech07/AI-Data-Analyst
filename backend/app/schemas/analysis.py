from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.tool import Filter

class AnalyzeOptions(BaseModel):
    exclude_incomplete_rows: bool = False
    filters: list[Filter] = Field(default_factory=list)

class AnalyzeRequest(BaseModel):
    question: str | None = Field(default=None, max_length=1000)
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)

class PlanStep(BaseModel):
    id: int
    goal: str
    hypothesis: str | None = None
    suggested_tool: str | None = None
    columns: list[str] = Field(default_factory=list, description="Target column names for calculate_statistics, correlation, or missing")
    group_column: str | None = Field(default=None, description="Categorical group column for group_by or statistical_test")
    metric_column: str | None = Field(default=None, description="Numeric metric column for group_by_analysis")
    value_column: str | None = Field(default=None, description="Primary numeric column for statistical_test or trend_analysis")
    method: str | None = Field(default=None, description="Analysis method (e.g. pearson, spearman, iqr)")
    aggregation: str | None = Field(default=None, description="Aggregation function (mean, median, sum)")
    date_column: str | None = Field(default=None, description="Temporal column for trend_analysis")
    test_type: str | None = Field(default=None, description="Test type for statistical_test (auto, t_test, mann_whitney, anova, chi_square)")

    @property
    def tool_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if self.columns:
            args["columns"] = self.columns
        if self.group_column:
            args["group_column"] = self.group_column
        if self.metric_column:
            args["metric_column"] = self.metric_column
        if self.value_column:
            args["value_column"] = self.value_column
        if self.method:
            args["method"] = self.method
        if self.aggregation:
            args["aggregation"] = self.aggregation
        if self.date_column:
            args["date_column"] = self.date_column
        if self.test_type:
            args["test_type"] = self.test_type
        return args

class InvestigationPlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list, max_length=12)

class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    question: str | None = None
    plan: InvestigationPlan | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

class SteerRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)

class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

class StructuredAnswer(BaseModel):
    answer: str
    key_points: list[str] = Field(default_factory=list)
    numbers: list[dict[str, Any]] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    next_questions: list[str] = Field(default_factory=list)
    calc_ids: list[str] = Field(default_factory=list)
    data_version: str = "cleaned"
    confidence: str = "high"

class ChatMessageResponse(BaseModel):
    message_id: UUID
    role: str
    content: str
    structured_answer: StructuredAnswer | None = None
    tool_execution_ids: list[str] = Field(default_factory=list)
