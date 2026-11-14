from typing import Any
import pandas as pd
from pydantic import BaseModel, Field

from app.schemas.tool import ToolResult
from app.services.datasets import profile_dataframe
from app.tools.base import require_columns
from app.tools.registry import tool

class ProfileDatasetArgs(BaseModel):
    columns: list[str] | None = Field(default=None, description="Optional subset of columns to profile.")

@tool(
    name="profile_dataset",
    description="Get a high-level statistical overview of the dataset: shape, column types, missing rates, unique counts, and basic metrics."
)
def profile_dataset(args: ProfileDatasetArgs, df: pd.DataFrame) -> ToolResult:
    target_df = df
    if args.columns:
        require_columns(df, *args.columns)
        target_df = df[args.columns]

    profile = profile_dataframe(target_df)
    return ToolResult(
        ok=True,
        data=profile.model_dump(),
        row_count_used=len(target_df)
    )
