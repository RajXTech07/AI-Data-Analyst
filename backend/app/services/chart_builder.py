import math
from typing import Any
import uuid
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import InvalidColumnError, UnsupportedChartError
from app.core.logging import logger
from app.db.models.chart import Chart
from app.db.models.chart_version import ChartVersion
from app.schemas.chart import (
    ChartEditableMetadata,
    ChartEditRequest,
    ChartEncoding,
    ChartEncodings,
    ChartScale,
    ChartSelectionRequest,
    ChartSelectionResponse,
    ChartSort,
    ChartSpec,
)
from app.schemas.tool import Filter
from app.services.columnar_engine import sanitize_value

PROJECT_PALETTE = [
    "#4F46E5",  # Signal Indigo
    "#0D9488",  # Evidence Teal
    "#D97706",  # Amber
    "#DB2777",  # Magenta
    "#2563EB",  # Blue
    "#65A30D",  # Lime
    "#64748B",  # Quiet Slate (for Other)
]

def is_identifier(col_name: str, series: pd.Series) -> bool:
    c_lower = col_name.lower()
    if any(k in c_lower for k in ["_id", "id", "uuid", "guid", "ssn", "code", "key", "phone"]):
        n = len(series.dropna())
        if n > 20 and series.nunique() / n >= 0.8:
            return True
    return False

class ChartBuilderService:
    """
    Builds, validates, downsamples, and edits renderer-neutral chart specifications
    with complete adherence to statistical correctness, semantic roles, and Plotly export.
    """

    @staticmethod
    def build_chart_spec(
        df: pd.DataFrame,
        chart_id: str | None = None,
        chart_type: str = "bar",
        x: str | None = None,
        y: str | None = None,
        color: str | None = None,
        size: str | None = None,
        facet: str | None = None,
        title: str | None = None,
        aggregation: str | None = None,
        bins: int | None = None,
        scale: ChartScale | None = None,
        sort: ChartSort | None = None,
        filters: list[Filter] | None = None,
        thresholds: list[dict[str, Any]] | None = None,
        data_version: str = "cleaned",
        source_calc_id: str | None = None
    ) -> ChartSpec:
        chart_id = chart_id or str(uuid.uuid4())
        filters = filters or []
        thresholds = thresholds or []
        scale = scale or ChartScale()
        sort = sort or ChartSort()

        from app.tools.base import apply_filters
        d = apply_filters(df, filters)
        total_initial_rows = len(d)

        if total_initial_rows == 0:
            raise UnsupportedChartError(
                "Cannot render chart: 0 data rows match the specified filters.",
                suggested_alternative="Remove or widen one or more filter conditions."
            )

        # Identifier guardrails
        for c in [y]:
            if c and c in d.columns and is_identifier(c, d[c]):
                raise InvalidColumnError(
                    f"Column '{c}' is an identifier/code, not a continuous numeric measure.",
                    suggested_alternative="Select a continuous quantitative metric column for the metric axis."
                )

        referenced_cols = [c for c in [x, y, color, size, facet] if c and c in d.columns]
        if referenced_cols:
            clean_d = d.dropna(subset=referenced_cols)
            rows_excluded = total_initial_rows - len(clean_d)
            d = clean_d
        else:
            rows_excluded = 0

        if len(d) == 0:
            raise UnsupportedChartError(
                "Cannot render chart: All rows contain missing values in the plotted axes.",
                suggested_alternative="Choose columns with valid non-null records."
            )

        # Constant check on primary measure
        if y and y in d.columns and pd.api.types.is_numeric_dtype(d[y]):
            if len(d) > 3 and d[y].std() == 0.0:
                logger.info(f"Column '{y}' is constant (zero variance).")

        # Downsample / server-side aggregation for big datasets
        sampled = False
        sampling_method = None
        max_pts = min(settings.MAX_PLOT_POINTS, 2500)

        if len(d) > max_pts:
            if chart_type in ("scatter", "line", "box", "histogram"):
                # Deterministic reservoir sample
                d = d.sample(n=max_pts, random_state=42)
                sampled = True
                sampling_method = f"deterministic_reservoir_sample_{max_pts}"

        title_text = title or f"{chart_type.capitalize()} Analysis"
        fig: go.Figure
        data_records: list[dict[str, Any]] = []

        # 1. Bar Chart
        if chart_type == "bar":
            if not x or x not in d.columns:
                raise InvalidColumnError("Bar chart requires a valid categorical 'x' column.")

            # Top N + Other grouping
            x_series = d[x].astype(str)
            top_cats = list(x_series.value_counts().head(settings.MAX_GROUPS_DEFAULT - 1).index)
            collapsed_x = x_series.apply(lambda v: v if v in top_cats else "Other")
            d_work = d.copy()
            d_work[x] = collapsed_x

            agg_fn = aggregation or "mean"
            if y and y in d.columns:
                grouped = d_work.groupby(x, dropna=True)[y].agg(agg_fn).reset_index()
                grouped.columns = [x, y]
                if sort.by == "value":
                    grouped = grouped.sort_values(y, ascending=(sort.order == "asc"))
                data_records = grouped.to_dict(orient="records")
                fig = px.bar(
                    grouped, x=x, y=y, color=x,
                    color_discrete_sequence=PROJECT_PALETTE,
                    title=title_text
                )
            else:
                counts = d_work[x].value_counts().reset_index()
                counts.columns = [x, "count"]
                if sort.by == "value":
                    counts = counts.sort_values("count", ascending=(sort.order == "asc"))
                data_records = counts.to_dict(orient="records")
                fig = px.bar(
                    counts, x=x, y="count", color=x,
                    color_discrete_sequence=PROJECT_PALETTE,
                    title=title_text
                )

            # Ensure bar charts start at zero strictly per Part 2.2
            fig.update_yaxes(rangemode="tozero")

        # 2. Line Chart
        elif chart_type == "line":
            if not x or not y:
                raise InvalidColumnError("Line chart requires both 'x' (time/order) and 'y' (metric) columns.")
            d_sorted = d.sort_values(x)
            data_records = d_sorted[[x, y]].to_dict(orient="records")
            fig = px.line(
                d_sorted, x=x, y=y, color=color,
                color_discrete_sequence=PROJECT_PALETTE,
                title=title_text
            )

        # 3. Scatter Plot
        elif chart_type == "scatter":
            if not x or not y:
                raise InvalidColumnError("Scatter plot requires both 'x' and 'y' continuous metric columns.")
            cols_to_keep = [x, y] + ([color] if color and color in d.columns else [])
            data_records = d[cols_to_keep].head(500).to_dict(orient="records")
            fig = px.scatter(
                d, x=x, y=y, color=color, size=size,
                color_discrete_sequence=PROJECT_PALETTE,
                title=title_text
            )

        # 4. Histogram
        elif chart_type == "histogram":
            metric_col = x or y
            if not metric_col:
                raise InvalidColumnError("Histogram requires a numeric metric column.")
            n_bins = bins or 30
            # Precompute histogram bins server-side
            counts, bin_edges = np.histogram(d[metric_col].dropna(), bins=n_bins)
            for i in range(len(counts)):
                data_records.append({
                    "bin_start": round(float(bin_edges[i]), 4),
                    "bin_end": round(float(bin_edges[i + 1]), 4),
                    "count": int(counts[i])
                })
            fig = px.histogram(
                d, x=metric_col, color=color, nbins=n_bins,
                color_discrete_sequence=PROJECT_PALETTE,
                title=title_text
            )
            fig.update_yaxes(rangemode="tozero")

        # 5. Box Plot
        elif chart_type == "box":
            metric_col = y or x
            if not metric_col:
                raise InvalidColumnError("Box plot requires a numeric column.")
            cols = [metric_col] + ([x] if x and x != metric_col else [])
            data_records = d[cols].head(500).to_dict(orient="records")
            fig = px.box(
                d, x=x if x != metric_col else None, y=metric_col, color=color,
                color_discrete_sequence=PROJECT_PALETTE,
                title=title_text
            )

        # 6. Heatmap
        elif chart_type == "heatmap":
            num_cols = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c]) and not is_identifier(c, d[c])]
            if len(num_cols) < 2:
                raise UnsupportedChartError("Heatmap requires at least 2 non-identifier numeric columns.")
            corr = d[num_cols].corr()
            data_records = corr.reset_index().to_dict(orient="records")
            fig = px.imshow(
                corr, text_auto=True, aspect="auto",
                color_continuous_scale="RdBu_r",
                title=title_text
            )

        else:
            raise UnsupportedChartError(f"Unsupported chart type '{chart_type}'. Allowed: bar, line, scatter, histogram, box, heatmap")

        # Apply Log / Linear Scale
        if scale.x == "log":
            fig.update_xaxes(type="log")
        if scale.y == "log":
            fig.update_yaxes(type="log")

        # Apply Threshold Annotations
        for t in thresholds:
            val = t.get("value")
            label = t.get("label", "Threshold")
            if val is not None:
                fig.add_hline(
                    y=val,
                    line_dash="dash",
                    line_color="#B91C1C",
                    annotation_text=label,
                    annotation_position="bottom right"
                )

        fig.update_layout(
            template="plotly_white",
            margin=dict(l=40, r=40, t=50, b=40),
            hovermode="closest"
        )

        plotly_json = sanitize_value(fig.to_plotly_json())

        # Construct validated renderer-neutral spec
        all_numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        all_categoric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]

        editable_meta = ChartEditableMetadata(
            allowed_columns={
                "metric": all_numeric,
                "dimension": all_categoric,
                "all": list(df.columns)
            }
        )

        encodings = ChartEncodings(
            x=ChartEncoding(column=x, role="dimension" if x in all_categoric else "measure", title=x),
            y=ChartEncoding(column=y, role="measure" if y in all_numeric else "dimension", title=y),
            color=ChartEncoding(column=color, role="color", title=color) if color else None,
            size=ChartEncoding(column=size, role="size", title=size) if size else None,
            facet=ChartEncoding(column=facet, role="facet", title=facet) if facet else None,
        )

        return ChartSpec(
            id=chart_id,
            type=chart_type,
            title=title_text,
            data=sanitize_value(data_records),
            encodings=encodings,
            aggregation=aggregation,
            filters=filters,
            sort=sort,
            bins=bins,
            scale=scale,
            thresholds=thresholds,
            data_version=data_version,
            rows_used=len(d),
            rows_excluded=rows_excluded,
            sampled=sampled,
            sampling_method=sampling_method,
            source_calc_id=source_calc_id,
            editable=editable_meta,
            plotly_spec=plotly_json
        )

    @staticmethod
    def edit_chart(
        db: Session,
        chart: Chart,
        edit_req: ChartEditRequest,
        df: pd.DataFrame
    ) -> tuple[ChartSpec, dict[str, Any]]:
        """
        Applies partial edits to a chart specification, recomputes on full data,
        saves a version snapshot in chart_versions, and returns (new_spec, diff).
        """
        curr_spec = chart.spec or {}
        if isinstance(curr_spec, str):
            import json
            try:
                curr_spec = json.loads(curr_spec)
            except Exception:
                curr_spec = {}
        if not isinstance(curr_spec, dict):
            curr_spec = {}
        enc = curr_spec.get("encodings", {}) if isinstance(curr_spec.get("encodings"), dict) else {}
        x_obj = enc.get("x")
        y_obj = enc.get("y")
        color_obj = enc.get("color")
        before_snapshot = {
            "chart_type": chart.chart_type,
            "title": chart.title,
            "x": x_obj.get("column") if isinstance(x_obj, dict) else None,
            "y": y_obj.get("column") if isinstance(y_obj, dict) else None,
            "color": color_obj.get("column") if isinstance(color_obj, dict) else None,
            "aggregation": curr_spec.get("aggregation"),
            "bins": curr_spec.get("bins"),
        }

        # Merge requested changes
        new_type = edit_req.chart_type or chart.chart_type
        new_title = edit_req.title or chart.title
        new_x = edit_req.x if edit_req.x is not None else before_snapshot["x"]
        new_y = edit_req.y if edit_req.y is not None else before_snapshot["y"]
        new_color = edit_req.color if edit_req.color is not None else before_snapshot["color"]
        new_agg = edit_req.aggregation if edit_req.aggregation is not None else before_snapshot["aggregation"]
        new_bins = edit_req.bins if edit_req.bins is not None else before_snapshot["bins"]
        new_scale = edit_req.scale or ChartScale()
        new_sort = edit_req.sort or ChartSort()
        new_filters = edit_req.filters if edit_req.filters is not None else [Filter(**f) for f in curr_spec.get("filters", [])]
        new_thresholds = edit_req.thresholds if edit_req.thresholds is not None else curr_spec.get("thresholds", [])

        # Recompute on full data
        new_spec = ChartBuilderService.build_chart_spec(
            df=df,
            chart_id=str(chart.id),
            chart_type=new_type,
            x=new_x,
            y=new_y,
            color=new_color,
            title=new_title,
            aggregation=new_agg,
            bins=new_bins,
            scale=new_scale,
            sort=new_sort,
            filters=new_filters,
            thresholds=new_thresholds,
            data_version=curr_spec.get("data_version", "cleaned")
        )

        diff = {
            "before": before_snapshot,
            "after": {
                "chart_type": new_type,
                "x": new_x,
                "y": new_y,
                "color": new_color,
                "aggregation": new_agg,
                "bins": new_bins
            },
            "changed_keys": [
                k for k in ["chart_type", "x", "y", "color", "aggregation", "bins"]
                if before_snapshot.get(k) != locals().get(f"new_{k}")
            ]
        }

        # Save version snapshot
        from app.services.type_inference import sanitize_for_json
        next_version = (chart.current_version or 1) + 1
        serialized_spec = sanitize_for_json(new_spec.model_dump())
        serialized_diff = sanitize_for_json(diff)

        version_record = ChartVersion(
            chart_id=chart.id,
            version=next_version,
            spec=serialized_spec,
            diff=serialized_diff,
            description=f"Edited {', '.join(diff['changed_keys'])}" if diff['changed_keys'] else "Chart update"
        )
        db.add(version_record)

        chart.chart_type = new_type
        chart.title = new_title
        chart.spec = serialized_spec
        chart.current_version = next_version
        db.commit()
        db.refresh(chart)

        return new_spec, diff

    @staticmethod
    def reset_chart(db: Session, chart: Chart, df: pd.DataFrame | None = None) -> ChartSpec:
        """Restores chart to original Version 1 spec."""
        v1 = db.query(ChartVersion).filter(ChartVersion.chart_id == chart.id, ChartVersion.version == 1).first()
        if not v1:
            raw_spec = chart.spec or {}
            if isinstance(raw_spec, str):
                import json
                raw_spec = json.loads(raw_spec)
            return ChartSpec.model_validate(raw_spec)
        chart.spec = v1.spec
        chart.chart_type = v1.spec.get("type", chart.chart_type)
        chart.title = v1.spec.get("title", chart.title)
        chart.current_version = 1
        db.commit()
        db.refresh(chart)
        return ChartSpec.model_validate(chart.spec)

    @staticmethod
    def inspect_selection(
        df: pd.DataFrame,
        spec: dict[str, Any],
        sel_req: ChartSelectionRequest
    ) -> ChartSelectionResponse:
        """
        Analyzes a user-brushed or point-selected region on a chart,
        returning row count, summary statistics, top categories, and preview.
        """
        enc = spec.get("encodings", {})
        x_col = enc.get("x", {}).get("column") if isinstance(enc.get("x"), dict) else None
        y_col = enc.get("y", {}).get("column") if isinstance(enc.get("y"), dict) else None

        sub = df.copy()

        # Apply bounding box range filters
        if sel_req.ranges:
            if x_col and x_col in sub.columns:
                x_range = sel_req.ranges.get("x") or sel_req.ranges.get(x_col)
                if x_range and len(x_range) == 2:
                    sub = sub[(sub[x_col] >= x_range[0]) & (sub[x_col] <= x_range[1])]
            if y_col and y_col in sub.columns:
                y_range = sel_req.ranges.get("y") or sel_req.ranges.get(y_col)
                if y_range and len(y_range) == 2:
                    sub = sub[(sub[y_col] >= y_range[0]) & (sub[y_col] <= y_range[1])]
        elif sel_req.selected_points:
            valid_indices = [idx for idx in sel_req.selected_points if idx in sub.index]
            sub = sub.loc[valid_indices]

        n_selected = len(sub)
        num_cols = [c for c in sub.columns if pd.api.types.is_numeric_dtype(sub[c])]
        cat_cols = [c for c in sub.columns if not pd.api.types.is_numeric_dtype(sub[c])]

        summary_stats = {}
        for c in num_cols[:5]:
            s = sub[c].dropna()
            if len(s) > 0:
                summary_stats[c] = {
                    "mean": round(float(s.mean()), 4),
                    "median": round(float(s.median()), 4),
                    "min": round(float(s.min()), 4),
                    "max": round(float(s.max()), 4),
                    "std": round(float(s.std(ddof=1)), 4) if len(s) > 1 else 0.0
                }

        top_cats = {}
        for c in cat_cols[:3]:
            top_cats[c] = [
                {"category": str(k), "count": int(v)}
                for k, v in sub[c].value_counts().head(5).items()
            ]

        preview = sub.head(10).replace({np.nan: None}).to_dict(orient="records")

        explain = {
            "selected_rows": n_selected,
            "fraction_of_dataset": round(n_selected / len(df), 4) if len(df) > 0 else 0.0,
            "axes_brushed": [c for c in [x_col, y_col] if c]
        }

        return ChartSelectionResponse(
            row_count=n_selected,
            summary_statistics=sanitize_value(summary_stats),
            top_categories=top_cats,
            preview=sanitize_value(preview),
            available_actions=["exclude", "label_anomaly", "filter_to"],
            explain=explain
        )

chart_builder_service = ChartBuilderService()
