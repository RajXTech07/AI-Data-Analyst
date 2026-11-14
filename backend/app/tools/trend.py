from typing import Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy import stats as sp_stats

from app.core.errors import ToolArgumentError
from app.schemas.tool import Filter, ToolResult
from app.tools.base import apply_filters, require_columns, require_numeric
from app.tools.registry import tool

class TrendArgs(BaseModel):
    date_column: str = Field(description="Date or timestamp column.")
    metric_column: str = Field(description="Numeric metric to analyze over time.")
    freq: Literal["D", "W", "ME", "QE", "YE"] = Field(
        default="ME",
        description="Aggregation interval: D (daily), W (weekly), ME (monthly), QE (quarterly), YE (yearly)."
    )
    aggregation: Literal["mean", "sum", "median"] = Field(default="mean", description="Aggregation method.")
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply.")

@tool(
    name="trend_analysis",
    description="Analyze time series patterns and trends: resamples by frequency, computes direction, slope, and percentage changes."
)
def trend_analysis(args: TrendArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)
    require_columns(d, args.date_column, args.metric_column)
    require_numeric(d, args.metric_column)

    clean_d = d[[args.date_column, args.metric_column]].dropna()
    if len(clean_d) < 3:
        return ToolResult(
            ok=False,
            error=f"Need at least 3 non-null records for trend analysis. Found: {len(clean_d)}",
            row_count_used=len(d)
        )

    # Parse dates
    try:
        parsed_dates = pd.to_datetime(clean_d[args.date_column], errors="coerce", format="mixed")
    except Exception as e:
        raise ToolArgumentError(f"Could not parse column '{args.date_column}' as dates: {str(e)}")

    valid_mask = parsed_dates.notna()
    if valid_mask.sum() < 3:
        raise ToolArgumentError(f"Fewer than 3 valid dates in '{args.date_column}'.")

    sub_df = pd.DataFrame({
        "ds": parsed_dates[valid_mask],
        "y": clean_d.loc[valid_mask, args.metric_column]
    }).sort_values("ds").set_index("ds")

    resampled = sub_df["y"].resample(args.freq).agg(args.aggregation).dropna()

    if len(resampled) < 2:
        return ToolResult(
            ok=True,
            data={"points": [], "summary": "Insufficient points at specified frequency."},
            warnings=["Data span is too short for the chosen frequency."],
            row_count_used=len(d)
        )

    # Calculate linear slope
    x_numeric = np.arange(len(resampled))
    y_vals = resampled.values.astype(float)
    slope, intercept, r_value, p_value, std_err = sp_stats.linregress(x_numeric, y_vals)

    first_val = float(y_vals[0])
    last_val = float(y_vals[-1])
    pct_change = round(((last_val - first_val) / abs(first_val) * 100.0) if first_val != 0 else 0.0, 2)

    direction = "upward" if slope > 0 else "downward" if slope < 0 else "flat"
    is_significant = p_value < 0.05

    points = [
        {"date": str(idx.date() if hasattr(idx, "date") else idx), "value": round(float(v), 4)}
        for idx, v in resampled.items()
    ]

    return ToolResult(
        ok=True,
        data={
            "date_column": args.date_column,
            "metric_column": args.metric_column,
            "frequency": args.freq,
            "aggregation": args.aggregation,
            "num_periods": len(resampled),
            "start_date": str(resampled.index[0]),
            "end_date": str(resampled.index[-1]),
            "pct_change": pct_change,
            "linear_slope": round(float(slope), 4),
            "r_squared": round(float(r_value ** 2), 4),
            "p_value": float(f"{p_value:.4e}"),
            "trend_direction": direction,
            "is_statistically_significant": is_significant,
            "points": points
        },
        row_count_used=len(d)
    )


