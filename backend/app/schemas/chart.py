from typing import Any, Literal
import uuid
from pydantic import BaseModel, Field
from app.schemas.tool import Filter

class ChartEncoding(BaseModel):
    column: str | None = None
    role: Literal["measure", "dimension", "time", "category", "color", "size", "facet"] | None = None
    units: str | None = None
    title: str | None = None

class ChartEncodings(BaseModel):
    x: ChartEncoding | None = None
    y: ChartEncoding | None = None
    color: ChartEncoding | None = None
    size: ChartEncoding | None = None
    facet: ChartEncoding | None = None

class ChartScale(BaseModel):
    x: Literal["linear", "log"] = "linear"
    y: Literal["linear", "log"] = "linear"

class ChartSort(BaseModel):
    by: Literal["value", "category", "natural"] = "value"
    order: Literal["asc", "desc"] = "desc"

class ChartEditableMetadata(BaseModel):
    allowed_types: list[str] = Field(default_factory=lambda: ["bar", "line", "scatter", "histogram", "box", "heatmap"])
    allowed_aggregations: list[str] = Field(default_factory=lambda: ["mean", "sum", "median", "count", "min", "max", "std"])
    allowed_columns: dict[str, list[str]] = Field(default_factory=dict)
    can_change_scale: bool = True
    can_change_bins: bool = True

class ChartSpec(BaseModel):
    id: str
    type: Literal["bar", "line", "scatter", "histogram", "box", "violin", "heatmap", "stacked_bar", "hexbin"]
    title: str
    data: list[dict[str, Any]]
    encodings: ChartEncodings
    aggregation: str | None = None
    filters: list[Filter] = Field(default_factory=list)
    sort: ChartSort | None = None
    bins: int | None = None
    scale: ChartScale = Field(default_factory=ChartScale)
    thresholds: list[dict[str, Any]] = Field(default_factory=list)
    data_version: str = "cleaned"
    rows_used: int = 0
    rows_excluded: int = 0
    sampled: bool = False
    sampling_method: str | None = None
    source_calc_id: str | None = None
    editable: ChartEditableMetadata = Field(default_factory=ChartEditableMetadata)
    plotly_spec: dict[str, Any] = Field(default_factory=dict)

class ChartEditRequest(BaseModel):
    title: str | None = None
    chart_type: str | None = None
    x: str | None = None
    y: str | None = None
    color: str | None = None
    size: str | None = None
    facet: str | None = None
    aggregation: str | None = None
    bins: int | None = None
    time_frequency: str | None = None
    sort: ChartSort | None = None
    top_n: int | None = None
    scale: ChartScale | None = None
    filters: list[Filter] | None = None
    thresholds: list[dict[str, Any]] | None = None

class ChartSelectionRequest(BaseModel):
    selected_points: list[int] | None = None
    ranges: dict[str, list[float]] | None = None
    filters: list[Filter] | None = None

class ChartSelectionResponse(BaseModel):
    row_count: int
    summary_statistics: dict[str, Any]
    top_categories: dict[str, list[dict[str, Any]]]
    preview: list[dict[str, Any]]
    available_actions: list[str] = Field(default_factory=lambda: ["exclude", "label_anomaly", "filter_to"])
    explain: dict[str, Any] = Field(default_factory=dict)
