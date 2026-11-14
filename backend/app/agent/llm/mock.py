import re
from typing import Any
import uuid
from pydantic import BaseModel
from app.agent.llm.base import LLMClient, LLMResponse
from app.schemas.analysis import InvestigationPlan, PlanStep
from app.schemas.finding import FindingDraft
from app.schemas.tool import ToolCall

class MockLLMClient(LLMClient):
    """
    Deterministic mock LLM client for offline development, integration testing,
    and fallback when no GEMINI_API_KEY is configured.
    Dynamically extracts columns from prompt messages so it works for any CSV dataset.
    """

    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.2
    ) -> LLMResponse:
        last_message = messages[-1]["content"] if messages else ""
        full_text = " ".join([m.get("content", "") for m in messages])

        # Extract column metadata from messages dynamically
        num_cols: list[str] = []
        cat_cols: list[str] = []
        all_cols: list[str] = []

        for m in re.finditer(r"-\s*['\"]([^'\"]+)['\"]\s*\(([^,\)]+)", full_text):
            col_name = m.group(1).strip()
            dtype_desc = m.group(2).lower()
            if col_name not in all_cols:
                all_cols.append(col_name)
            if "num" in dtype_desc and col_name not in num_cols:
                num_cols.append(col_name)
            elif ("cat" in dtype_desc or "bool" in dtype_desc) and col_name not in cat_cols:
                cat_cols.append(col_name)

        # Fallback extract quoted words if regex missed
        if not all_cols:
            for c in re.findall(r"['\"]([a-zA-Z0-9_\-\s]+)['\"]", full_text):
                if c not in ["role", "user", "system", "assistant", "numeric", "categorical", "text", "datetime", "boolean"] and len(c) < 40:
                    if c not in all_cols:
                        all_cols.append(c)

        # 1. Investigation Planning
        if response_schema and issubclass(response_schema, InvestigationPlan):
            steps = [
                PlanStep(
                    id=1,
                    goal="Compute baseline descriptive statistics for all numeric metrics.",
                    hypothesis="Variables show distinct variance and central tendencies.",
                    suggested_tool="calculate_statistics"
                )
            ]
            if cat_cols and num_cols:
                steps.append(
                    PlanStep(
                        id=2,
                        goal=f"Compare {num_cols[0]} across {cat_cols[0]} groups.",
                        hypothesis=f"Significant differences exist in {num_cols[0]} across {cat_cols[0]}.",
                        suggested_tool="group_by_analysis"
                    )
                )
                steps.append(
                    PlanStep(
                        id=3,
                        goal=f"Conduct hypothesis test on {num_cols[0]} across {cat_cols[0]}.",
                        hypothesis=f"Difference in {num_cols[0]} by {cat_cols[0]} is statistically significant.",
                        suggested_tool="statistical_test"
                    )
                )
            if len(num_cols) >= 2:
                steps.append(
                    PlanStep(
                        id=len(steps) + 1,
                        goal=f"Evaluate pairwise correlation between {num_cols[0]} and {num_cols[1]}.",
                        hypothesis=f"{num_cols[0]} correlates with {num_cols[1]}.",
                        suggested_tool="correlation_analysis"
                    )
                )

            plan = InvestigationPlan(steps=steps)
            return LLMResponse(
                content=plan.model_dump_json(),
                structured_data=plan
            )

        # 2. Tool Calling (Function Calling phase)
        if tools:
            # Check what step or query is asked
            if "group_by_analysis" in last_message or "group" in last_message.lower():
                grp = cat_cols[0] if cat_cols else (all_cols[0] if all_cols else "group")
                met = num_cols[0] if num_cols else (all_cols[1] if len(all_cols) > 1 else grp)
                return LLMResponse(
                    content=f"Calling group_by_analysis to compare {met} across {grp}.",
                    tool_calls=[ToolCall(name="group_by_analysis", arguments={"group_column": grp, "metric_column": met})]
                )
            elif "statistical_test" in last_message or "hypothesis" in last_message.lower():
                grp = cat_cols[0] if cat_cols else (all_cols[0] if all_cols else "group")
                val = num_cols[0] if num_cols else (all_cols[1] if len(all_cols) > 1 else grp)
                return LLMResponse(
                    content=f"Running statistical hypothesis test on {val} across {grp}.",
                    tool_calls=[ToolCall(name="statistical_test", arguments={"group_column": grp, "value_column": val})]
                )
            elif "correlation" in last_message.lower():
                cols = num_cols[:2] if len(num_cols) >= 2 else all_cols[:2]
                return LLMResponse(
                    content=f"Running correlation analysis on {cols}.",
                    tool_calls=[ToolCall(name="correlation_analysis", arguments={"columns": cols})]
                )
            else:
                cols = num_cols[:3] if num_cols else all_cols[:3]
                return LLMResponse(
                    content=f"Calculating descriptive statistics on {cols}.",
                    tool_calls=[ToolCall(name="calculate_statistics", arguments={"columns": cols})]
                )

        # 3. Direct Column Questions in Chat
        lower_q = last_message.lower()
        if "which column" in lower_q or "what column" in lower_q or "list the column" in lower_q or "list column" in lower_q or "columns does this" in lower_q:
            if all_cols:
                return LLMResponse(content=f"This dataset has {len(all_cols)} columns: {', '.join(all_cols)}.")

        # 4. Finding Interpretation (Structured output)
        if response_schema:
            return LLMResponse(
                content="Findings generated.",
                structured_data=response_schema
            )

        # General text response
        return LLMResponse(content="Analysis step executed successfully based on verified data.")
