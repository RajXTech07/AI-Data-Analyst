import math
from typing import Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy import stats as sp_stats

from app.schemas.tool import Filter, ToolResult
from app.services.columnar_engine import sanitize_value
from app.tools.base import apply_filters, require_columns, require_numeric
from app.tools.registry import tool

class CorrelationArgs(BaseModel):
    columns: list[str] | None = Field(default=None, description="Subset of numeric columns to correlate. Defaults to all non-identifier numeric columns.")
    method: Literal["pearson", "spearman", "kendall"] = Field(default="pearson", description="Correlation method: 'pearson' (linear), 'spearman' (rank/monotonic), or 'kendall' (tau rank concordant).")
    min_periods: int = Field(default=10, description="Minimum non-null paired observations required.")
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply.")

def is_identifier_column(col_name: str, series: pd.Series) -> bool:
    """Detects if a column is an ID or code that should not be correlated."""
    c_lower = col_name.lower()
    if any(k in c_lower for k in ["_id", "id", "uuid", "guid", "ssn", "code", "key", "index", "phone"]):
        # Check if nearly all values are unique
        n = len(series.dropna())
        if n > 10 and series.nunique() / n > 0.8:
            return True
    return False

@tool(
    name="correlation_analysis",
    description="Calculate pairwise correlation coefficients (Pearson, Spearman, or Kendall) with p-values, reporting n per pair and handling constant columns cleanly."
)
def correlation_analysis(args: CorrelationArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)
    total_rows = len(d)

    if args.columns:
        require_columns(d, *args.columns)
        require_numeric(d, *args.columns)
        candidate_cols = args.columns
    else:
        candidate_cols = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]

    # Exclude identifier columns
    num_cols = [c for c in candidate_cols if not is_identifier_column(c, d[c])]

    if len(num_cols) < 2:
        return ToolResult(
            ok=False,
            error=f"Need at least 2 non-identifier numeric columns for correlation analysis. Valid numeric columns: {num_cols}",
            row_count_used=total_rows
        )

    sub_df = d[num_cols]
    pairs = []
    matrix: dict[str, dict[str, float | None]] = {c: {} for c in num_cols}
    warnings = []

    for i in range(len(num_cols)):
        col1 = num_cols[i]
        for j in range(len(num_cols)):
            col2 = num_cols[j]
            if i == j:
                matrix[col1][col2] = 1.0
                continue

            # Pairwise complete valid observations
            valid = sub_df[[col1, col2]].dropna()
            n_pair = len(valid)

            if n_pair < args.min_periods:
                matrix[col1][col2] = None
                continue

            x = valid[col1]
            y = valid[col2]

            # Check for constant column (zero variance/std)
            std_x = x.std(ddof=1) if n_pair > 1 else 0.0
            std_y = y.std(ddof=1) if n_pair > 1 else 0.0

            if std_x == 0.0 or std_y == 0.0:
                # Per Part 1.2: return null, not NaN/inf
                matrix[col1][col2] = None
                if i < j:
                    warnings.append(f"Pair ('{col1}', '{col2}') contains a constant column (variance=0); correlation is undefined (null).")
                continue

            try:
                if args.method == "pearson":
                    res = sp_stats.pearsonr(x, y)
                    r_val = float(res.statistic)
                    p_val = float(res.pvalue)
                elif args.method == "spearman":
                    res = sp_stats.spearmanr(x, y)
                    r_val = float(res.statistic)
                    p_val = float(res.pvalue)
                else:  # kendall
                    res = sp_stats.kendalltau(x, y)
                    r_val = float(res.statistic)
                    p_val = float(res.pvalue)
            except Exception:
                matrix[col1][col2] = None
                continue

            if math.isnan(r_val) or math.isinf(r_val):
                matrix[col1][col2] = None
                continue

            matrix[col1][col2] = round(r_val, 4)

            # Record upper triangle for ranked pairs
            if i < j:
                abs_r = abs(r_val)
                if abs_r >= 0.7:
                    strength = "strong"
                elif abs_r >= 0.4:
                    strength = "moderate"
                elif abs_r >= 0.2:
                    strength = "weak"
                else:
                    strength = "negligible"

                pairs.append({
                    "column_a": col1,
                    "column_b": col2,
                    "correlation": round(r_val, 4),
                    "abs_correlation": round(abs_r, 4),
                    "p_value": float(f"{p_val:.4e}"),
                    "n_used": n_pair,
                    "n_excluded": total_rows - n_pair,
                    "strength": strength,
                    "direction": "positive" if r_val > 0 else "negative"
                })

    pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)

    return ToolResult(
        ok=True,
        data=sanitize_value({
            "matrix": matrix,
            "ranked_pairs": pairs,
            "pairs": pairs,
            "top_pair": pairs[0] if pairs else None,
            "method": args.method,
            "columns": num_cols
        }),
        warnings=warnings,
        row_count_used=total_rows
    )
