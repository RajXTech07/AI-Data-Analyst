from typing import Literal
import pandas as pd
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.tool import Filter, ToolResult
from app.services.columnar_engine import sanitize_value
from app.tools.base import apply_filters, require_columns, require_numeric
from app.tools.registry import tool

class GroupByArgs(BaseModel):
    group_column: str = Field(description="Categorical column to group by.")
    metric_column: str = Field(description="Numeric column to aggregate.")
    aggregation: Literal["mean", "median", "sum", "count", "std"] = Field(
        default="mean",
        description="Aggregation function to compute."
    )
    max_groups: int = Field(
        default=20,
        description="Maximum number of groups to return before grouping the tail into an explicit 'Other' bucket."
    )
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply.")

@tool(
    name="group_by_analysis",
    description="Aggregate a numeric metric column by a categorical group column with capped categories, explicit 'Other' bucket, and exact total preservation."
)
def group_by_analysis(args: GroupByArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)
    require_columns(d, args.group_column, args.metric_column)
    require_numeric(d, args.metric_column)

    total_rows = len(d)
    clean_d = d[[args.group_column, args.metric_column]].dropna()
    total_valid = len(clean_d)
    rows_excluded = total_rows - total_valid

    if total_valid == 0:
        return ToolResult(
            ok=True,
            data={"groups": [], "aggregation": args.aggregation, "total_rows": 0, "n_excluded": rows_excluded},
            warnings=["No rows remained after dropping missing values in group/metric columns."],
            row_count_used=total_rows
        )

    # Compute overall grand total and mean
    grand_sum = float(clean_d[args.metric_column].sum())
    overall_mean = float(clean_d[args.metric_column].mean())

    warnings = []
    # Check for rate/percentage aggregation trap
    met_lower = args.metric_column.lower()
    if any(k in met_lower for k in ["%", "rate", "pct", "percent", "ratio", "proportion"]) and args.aggregation in ["mean", "sum"]:
        warnings.append("Aggregating rates or percentages without subgroup population weights can produce mathematical distortion (Simpson's Paradox).")

    grouped = clean_d.groupby(args.group_column)[args.metric_column]
    agg_series = grouped.agg(args.aggregation)
    count_series = grouped.count()
    sum_series = grouped.sum()

    total_unique_groups = len(agg_series)
    max_g = args.max_groups or settings.MAX_GROUPS_DEFAULT

    all_groups = []
    small_sample_groups = []

    for grp_val in agg_series.index:
        val = float(agg_series[grp_val])
        cnt = int(count_series[grp_val])
        grp_sum = float(sum_series[grp_val])
        if cnt < 5:
            small_sample_groups.append(str(grp_val))
        all_groups.append({
            "group": str(grp_val),
            "metric_value": round(val, 4),
            "count": cnt,
            "grp_sum": grp_sum,
            "percentage_share": round((grp_sum / grand_sum * 100.0) if grand_sum != 0 else 0.0, 2)
        })

    if small_sample_groups:
        warnings.append(f"Subgroups {small_sample_groups[:3]} have very small sample size (n < 5). Compare with caution.")

    # Sort descending by metric value
    all_groups.sort(key=lambda x: x["metric_value"], reverse=True)

    if total_unique_groups <= max_g:
        results = all_groups
        capped = False
    else:
        capped = True
        top_groups = all_groups[: max_g - 1]
        tail_groups = all_groups[max_g - 1 :]

        other_count = sum(g["count"] for g in tail_groups)
        other_sum = sum(g["grp_sum"] for g in tail_groups)

        if args.aggregation in ("mean", "avg"):
            other_metric_val = (other_sum / other_count) if other_count > 0 else 0.0
        elif args.aggregation == "sum":
            other_metric_val = other_sum
        elif args.aggregation == "count":
            other_metric_val = other_count
        else:
            other_metric_val = (other_sum / other_count) if other_count > 0 else 0.0

        other_entry = {
            "group": f"Other ({len(tail_groups)} categories)",
            "metric_value": round(float(other_metric_val), 4),
            "count": other_count,
            "grp_sum": other_sum,
            "percentage_share": round((other_sum / grand_sum * 100.0) if grand_sum != 0 else 0.0, 2)
        }

        results = top_groups + [other_entry]
        warnings.append(f"Capped {total_unique_groups} groups to {max_g}. The remaining {len(tail_groups)} groups were aggregated into 'Other' preserving exact totals.")

    # Strip internal grp_sum field from output
    clean_results = []
    for g in results:
        g_clean = {k: v for k, v in g.items() if k != "grp_sum"}
        clean_results.append(g_clean)

    return ToolResult(
        ok=True,
        data=sanitize_value({
            "group_column": args.group_column,
            "metric_column": args.metric_column,
            "aggregation": args.aggregation,
            "groups": clean_results,
            "num_groups": len(clean_results),
            "total_groups": total_unique_groups,
            "capped": capped,
            "grand_sum": round(grand_sum, 4),
            "overall_mean": round(overall_mean, 4),
            "n_used": total_valid,
            "n_excluded": rows_excluded
        }),
        warnings=warnings,
        row_count_used=total_rows
    )
