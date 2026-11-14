import pandas as pd
from pydantic import BaseModel, Field

from app.schemas.tool import Filter, ToolResult
from app.tools.base import apply_filters, require_columns
from app.tools.registry import tool

class MissingValuesArgs(BaseModel):
    columns: list[str] | None = Field(default=None, description="Columns to inspect for missing values. Defaults to all.")
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply before checking.")

@tool(
    name="detect_missing_values",
    description="Detect missing (null / NaN) values across columns, reporting counts, percentages, and total affected rows."
)
def detect_missing_values(args: MissingValuesArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)
    cols = args.columns or list(d.columns)
    require_columns(d, *cols)

    target_df = d[cols]
    n_rows = len(target_df)

    if n_rows == 0:
        return ToolResult(
            ok=True,
            data={"columns": [], "total_rows_with_missing": 0, "total_missing_cells": 0},
            row_count_used=0
        )

    missing_counts = target_df.isna().sum()
    rows_with_missing = int(target_df.isna().any(axis=1).sum())
    total_missing = int(missing_counts.sum())

    col_stats = []
    for col in cols:
        count = int(missing_counts[col])
        pct = round((count / n_rows) * 100.0, 2)
        col_stats.append({
            "column": col,
            "missing_count": count,
            "missing_pct": pct,
        })

    col_stats.sort(key=lambda x: x["missing_count"], reverse=True)

    return ToolResult(
        ok=True,
        data={
            "columns": col_stats,
            "total_rows_with_missing": rows_with_missing,
            "total_missing_cells": total_missing,
            "pct_rows_affected": round((rows_with_missing / n_rows) * 100.0, 2)
        },
        row_count_used=n_rows
    )
