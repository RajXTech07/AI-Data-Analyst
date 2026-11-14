from typing import Any
import numpy as np
import pandas as pd
from app.core.errors import ToolArgumentError
from app.schemas.tool import Filter, ToolResult

def require_columns(df: pd.DataFrame, *columns: str) -> None:
    """Verifies that all specified columns exist in the DataFrame."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        available = list(df.columns)
        raise ToolArgumentError(
            f"Column(s) {missing} not found in dataset. Available columns: {available}",
            details={"missing_columns": missing, "available_columns": available}
        )

def require_numeric(df: pd.DataFrame, *columns: str) -> None:
    """Verifies that the specified columns have numeric data types."""
    require_columns(df, *columns)
    non_numeric = [c for c in columns if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        details = {c: str(df[c].dtype) for c in non_numeric}
        raise ToolArgumentError(
            f"Column(s) {non_numeric} must be numeric, but have types: {details}",
            details={"non_numeric_columns": details}
        )

def apply_filters(df: pd.DataFrame, filters: list[Filter] | None) -> pd.DataFrame:
    """
    Safely applies structured filters to a DataFrame without eval() or df.query().
    Returns a copy/slice of the DataFrame.
    """
    if not filters:
        return df

    mask = pd.Series(True, index=df.index)

    for f in filters:
        require_columns(df, f.column)
        col_series = df[f.column]

        if f.op == "eq":
            mask &= (col_series == f.value)
        elif f.op == "ne":
            mask &= (col_series != f.value)
        elif f.op == "gt":
            mask &= (col_series > f.value)
        elif f.op == "gte":
            mask &= (col_series >= f.value)
        elif f.op == "lt":
            mask &= (col_series < f.value)
        elif f.op == "lte":
            mask &= (col_series <= f.value)
        elif f.op == "in":
            vals = f.value if isinstance(f.value, list) else [f.value]
            mask &= (col_series.isin(vals))
        elif f.op == "notnull":
            mask &= (col_series.notna())
        elif f.op == "isnull":
            mask &= (col_series.isna())
        else:
            raise ToolArgumentError(f"Unsupported filter operator: '{f.op}'")

    return df[mask]

from app.services.type_inference import sanitize_for_json
