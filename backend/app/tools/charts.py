from typing import Literal
import pandas as pd
from pydantic import BaseModel, Field

from app.core.errors import InvalidColumnError, ToolArgumentError, UnsupportedChartError
from app.schemas.tool import Filter, ToolResult
from app.tools.registry import tool

class ChartArgs(BaseModel):
    chart_type: Literal["bar", "line", "scatter", "histogram", "box", "heatmap"] = Field(
        description="Type of chart to generate: bar, line, scatter, histogram, box, or heatmap."
    )
    x: str | None = Field(default=None, description="Column for the X-axis.")
    y: str | None = Field(default=None, description="Column for the Y-axis.")
    color: str | None = Field(default=None, description="Optional column to encode with color/category.")
    title: str | None = Field(default=None, description="Chart title.")
    use_cleaned: bool = Field(default=True, description="Whether to plot from cleaned data copy.")
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply.")

@tool(
    name="generate_chart",
    description="Generate interactive Plotly visualization specifications (bar, line, scatter, histogram, box, heatmap) directly from dataset rows with semantic safeguards."
)
def generate_chart(args: ChartArgs, df: pd.DataFrame) -> ToolResult:
    try:
        from app.services.chart_builder import ChartBuilderService
        chart_spec = ChartBuilderService.build_chart_spec(
            df=df,
            chart_type=args.chart_type,
            x=args.x,
            y=args.y,
            color=args.color,
            title=args.title,
            filters=args.filters,
            data_version="cleaned" if args.use_cleaned else "raw"
        )

        warnings = []
        if chart_spec.rows_excluded > 0:
            warnings.append(f"Excluded {chart_spec.rows_excluded} row(s) with missing values in plotted columns.")
        if chart_spec.sampled:
            warnings.append(f"Chart data was downsampled using {chart_spec.sampling_method} for client rendering.")

        source_label = "Cleaned Copy" if args.use_cleaned else "Raw Dataset"

        return ToolResult(
            ok=True,
            data={
                "chart_id": chart_spec.id,
                "chart_type": chart_spec.type,
                "title": chart_spec.title,
                "spec": chart_spec.plotly_spec,
                "chart_spec": chart_spec.model_dump(),
                "data_source": source_label,
                "rows_plotted": chart_spec.rows_used,
                "rows_excluded": chart_spec.rows_excluded,
                "sampled": chart_spec.sampled,
                "sampling_method": chart_spec.sampling_method
            },
            warnings=warnings,
            row_count_used=chart_spec.rows_used
        )
    except (InvalidColumnError, UnsupportedChartError) as e:
        raise ToolArgumentError(str(e))
    except Exception as e:
        if isinstance(e, ToolArgumentError):
            raise
        raise ToolArgumentError(f"Failed to generate Plotly figure: {str(e)}")

