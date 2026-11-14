from typing import Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.schemas.tool import Filter, ToolResult
from app.services.columnar_engine import sanitize_value
from app.tools.base import apply_filters, require_columns, require_numeric
from app.tools.registry import tool

class OutliersArgs(BaseModel):
    column: str = Field(description="Numeric column to inspect for outliers.")
    method: Literal["iqr", "zscore", "mad"] = Field(
        default="iqr",
        description="Detection method: 'iqr' (Tukey fences), 'zscore' (parametric standard deviations), or 'mad' (median absolute deviation)."
    )
    threshold: float = Field(
        default=1.5,
        description="Multiplier threshold: 1.5 for standard IQR (or 3.0 for extreme), 3.0 for Z-score, 3.5 for MAD."
    )
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply.")

@tool(
    name="detect_outliers",
    description="Detect statistical outliers in a numeric column using Tukey's IQR fences, Z-scores, or MAD, reporting bounds, count, and extreme records."
)
def detect_outliers(args: OutliersArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)
    require_columns(d, args.column)
    require_numeric(d, args.column)

    total_rows = len(d)
    series = d[args.column].dropna()
    n = len(series)
    rows_excluded = total_rows - n

    if n < 4:
        return ToolResult(
            ok=True,
            data={
                "column": args.column,
                "outlier_count": 0,
                "outlier_pct": 0.0,
                "samples": [],
                "n_used": n,
                "n_excluded": rows_excluded
            },
            warnings=["At least 4 non-null observations are required for outlier detection."],
            row_count_used=total_rows
        )

    if args.method == "iqr":
        q25 = float(series.quantile(0.25))
        q75 = float(series.quantile(0.75))
        iqr = q75 - q25
        lower_bound = q25 - (args.threshold * iqr)
        upper_bound = q75 + (args.threshold * iqr)
        outlier_mask = (series < lower_bound) | (series > upper_bound)
    elif args.method == "zscore":
        mean = float(series.mean())
        std = float(series.std(ddof=1))
        if std == 0:
            return ToolResult(
                ok=True,
                data={
                    "column": args.column,
                    "outlier_count": 0,
                    "outlier_pct": 0.0,
                    "samples": [],
                    "n_used": n,
                    "n_excluded": rows_excluded
                },
                warnings=["Standard deviation is zero (constant column); no outliers can be computed."],
                row_count_used=total_rows
            )
        z_scores = (series - mean).abs() / std
        lower_bound = mean - (args.threshold * std)
        upper_bound = mean + (args.threshold * std)
        outlier_mask = z_scores > args.threshold
    else:  # mad (Median Absolute Deviation)
        median = float(series.median())
        mad = float(np.median(np.abs(series.to_numpy() - median)))
        if mad == 0:
            # Scaled MAD is 0 when > 50% of values are identical
            mad = float(series.std(ddof=1)) * 0.6745 if series.std(ddof=1) > 0 else 1.0

        # Modified Z-score: 0.6745 * (x - median) / MAD
        mod_z = 0.6745 * (series - median).abs() / mad
        thresh = args.threshold if args.threshold > 2.0 else 3.5
        lower_bound = median - (thresh * mad / 0.6745)
        upper_bound = median + (thresh * mad / 0.6745)
        outlier_mask = mod_z > thresh

    outlier_series = series[outlier_mask]
    outlier_count = int(outlier_mask.sum())
    outlier_pct = round((outlier_count / n) * 100.0, 2)

    samples = []
    if outlier_count > 0:
        # Get up to 10 most extreme values
        distance_from_center = (outlier_series - series.median()).abs()
        sorted_indices = distance_from_center.sort_values(ascending=False).head(10).index
        for idx in sorted_indices:
            val = float(series.loc[idx])
            samples.append({
                "row_index": int(idx),
                "value": round(val, 4),
                "deviation_type": "high" if val > upper_bound else "low"
            })

    return ToolResult(
        ok=True,
        data=sanitize_value({
            "column": args.column,
            "method": args.method,
            "threshold": args.threshold,
            "total_valid_rows": n,
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
            "outlier_count": outlier_count,
            "outlier_pct": outlier_pct,
            "samples": samples,
            "n_used": n,
            "n_excluded": rows_excluded
        }),
        row_count_used=total_rows
    )
