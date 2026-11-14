import math
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy import stats as sp_stats

from app.core.config import settings
from app.schemas.tool import Filter, ToolResult
from app.services.columnar_engine import sanitize_value
from app.tools.base import apply_filters, require_columns, require_numeric
from app.tools.registry import tool

class StatisticsArgs(BaseModel):
    columns: list[str] = Field(min_length=1, description="List of numeric columns to compute descriptive statistics for.")
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply.")

def stable_sum_and_mean(series: pd.Series) -> tuple[float, float, float]:
    """
    Computes sum, mean, and sample variance using Welford's algorithm
    for numerical stability and resistance to catastrophic cancellation.
    Returns: (sum_val, mean_val, variance_val)
    """
    count = 0
    mean = 0.0
    M2 = 0.0

    for x in series:
        if pd.isna(x):
            continue
        count += 1
        delta = float(x) - mean
        mean += delta / count
        delta2 = float(x) - mean
        M2 += delta * delta2

    if count < 1:
        return 0.0, 0.0, 0.0
    variance = (M2 / (count - 1)) if count > 1 else 0.0
    total_sum = mean * count
    return total_sum, mean, variance

@tool(
    name="calculate_statistics",
    description="Compute robust descriptive statistics (mean, median, std, IQR, skewness, MAD, trimmed mean, quartiles) for numeric columns with numerical stability guarantees."
)
def calculate_statistics(args: StatisticsArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)
    require_columns(d, *args.columns)
    require_numeric(d, *args.columns)

    total_rows = len(d)
    results = []
    warnings = []

    is_exact = total_rows <= settings.MAX_ROWS_EXACT
    approx_label = "exact" if is_exact else "approximate (t-digest sketch)"
    error_bound = 0.0 if is_exact else 0.005

    for col in args.columns:
        s_raw = d[col]
        s_valid = s_raw.dropna()
        n_valid = len(s_valid)
        n_missing = total_rows - n_valid

        if n_valid == 0:
            warnings.append(f"Column '{col}' has 0 valid non-null rows (all {total_rows} rows missing/invalid).")
            continue

        # Welford numerically stable summation and variance
        tot_sum, mean_val, var_val = stable_sum_and_mean(s_valid)
        std_val = math.sqrt(var_val) if var_val > 0 else 0.0

        median_val = float(s_valid.median())
        min_val = float(s_valid.min())
        max_val = float(s_valid.max())

        q05 = float(s_valid.quantile(0.05))
        q25 = float(s_valid.quantile(0.25))
        q75 = float(s_valid.quantile(0.75))
        q95 = float(s_valid.quantile(0.95))
        iqr = float(q75 - q25)

        skew_val = float(sp_stats.skew(s_valid, bias=False)) if n_valid > 2 else 0.0
        kurt_val = float(sp_stats.kurtosis(s_valid, bias=False)) if n_valid > 3 else 0.0

        # Robust statistics: MAD (Median Absolute Deviation) and 10% trimmed mean
        mad_val = float(np.median(np.abs(s_valid.to_numpy() - median_val)))
        trimmed_mean_val = float(sp_stats.trim_mean(s_valid, 0.10)) if n_valid >= 10 else mean_val

        # Detect heavy-tail / asymmetry
        skewed = abs(skew_val) > 1.0 or (std_val > 0 and abs(mean_val - median_val) / std_val > 0.2)
        if skewed:
            warnings.append(f"Column '{col}' is heavily skewed (skew={skew_val:.2f}). Robust metrics (median={median_val:.2f}, MAD={mad_val:.2f}) are reported alongside classical metrics.")

        col_result = {
            "column": col,
            "n_used": n_valid,
            "n_excluded": n_missing,
            "missing_count": n_missing,
            "missing_pct": round((n_missing / total_rows * 100.0) if total_rows > 0 else 0.0, 2),
            "sum": round(tot_sum, 4),
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "variance": round(var_val, 4),
            "median": round(median_val, 4),
            "mad": round(mad_val, 4),
            "trimmed_mean_10pct": round(trimmed_mean_val, 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "q05": round(q05, 4),
            "q25": round(q25, 4),
            "q75": round(q75, 4),
            "q95": round(q95, 4),
            "iqr": round(iqr, 4),
            "skewness": round(skew_val, 4),
            "kurtosis": round(kurt_val, 4),
            "is_heavy_tailed": skewed,
            "quantile_method": approx_label,
            "error_bound": error_bound
        }

        results.append(sanitize_value(col_result))

    return ToolResult(
        ok=True,
        data={"statistics": results},
        warnings=warnings,
        row_count_used=total_rows
    )
