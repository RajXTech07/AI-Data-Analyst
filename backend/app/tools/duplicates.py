import pandas as pd
from pydantic import BaseModel, Field

from app.schemas.tool import Filter, ToolResult
from app.tools.base import apply_filters, require_columns
from app.tools.registry import tool

class DuplicatesArgs(BaseModel):
    subset: list[str] | None = Field(default=None, description="Subset of columns to consider when identifying duplicates.")
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply before checking.")

@tool(
    name="detect_duplicates",
    description="Detect identical duplicate rows across all or a specified subset of columns."
)
def detect_duplicates(args: DuplicatesArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)
    if args.subset:
        require_columns(d, *args.subset)

    n_rows = len(d)
    if n_rows == 0:
        return ToolResult(
            ok=True,
            data={"duplicate_count": 0, "duplicate_pct": 0.0, "sample_duplicate_rows": []},
            row_count_used=0
        )

    dup_mask = d.duplicated(subset=args.subset, keep=False)
    dup_count = int(d.duplicated(subset=args.subset, keep="first").sum())
    dup_pct = round((dup_count / n_rows) * 100.0, 2)

    sample_rows = []
    if dup_count > 0:
        sample_df = d[dup_mask].head(10)
        sample_rows = sample_df.to_dict(orient="records")

    return ToolResult(
        ok=True,
        data={
            "duplicate_count": dup_count,
            "duplicate_pct": dup_pct,
            "total_rows": n_rows,
            "sample_duplicate_rows": sample_rows,
        },
        row_count_used=n_rows
    )
