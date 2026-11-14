from typing import Any, Literal
from pydantic import BaseModel, Field

class Filter(BaseModel):
    column: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "notnull", "isnull"]
    value: Any | None = None

class ToolResult(BaseModel):
    ok: bool
    data: dict | list | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    row_count_used: int | None = None
    duration_ms: int | None = None

class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
