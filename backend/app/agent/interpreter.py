import json
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.agent.llm.base import LLMClient
from app.agent.prompts import SYSTEM_PROMPT, make_interpreter_prompt
from app.core.logging import logger
from app.db.models.tool_execution import ToolExecution
from app.schemas.finding import FindingDraft

class FindingsContainer(BaseModel):
    findings: list[FindingDraft] = Field(default_factory=list)

def build_execution_summary(executions: list[ToolExecution]) -> str:
    """Builds a structured audit trail summary of all executed tools for the interpreter."""
    lines = []
    for e in executions:
        lines.append(f"--- Execution ID: {e.id} (Tool: {e.tool_name}, Seq: {e.seq}) ---")
        lines.append(f"Arguments: {json.dumps(e.arguments)}")
        if e.ok and e.result:
            result_str = json.dumps(e.result)
            # Truncate overly long result payloads to 1500 chars for prompt safety
            if len(result_str) > 1500:
                result_str = result_str[:1500] + "... [truncated]"
            lines.append(f"Result: {result_str}")
        else:
            lines.append(f"Error: {e.error}")
        lines.append("")
    return "\n".join(lines)

def format_column_name(col: str | None) -> str:
    """Formats raw column names into clean, readable title case without code syntax."""
    if not col:
        return "Unknown"
    return str(col).replace("_", " ").strip().title()

def generate_findings_from_tools(executions: list[ToolExecution]) -> list[FindingDraft]:
    """Fallback deterministic finding generator extracting verified findings from tool outputs."""
    findings = []
    for e in executions:
        if not e.ok or not e.result:
            continue

        if isinstance(e.result, dict):
            if "data" in e.result and isinstance(e.result["data"], dict) and "test" not in e.result and "ranked_pairs" not in e.result:
                data = e.result["data"]
            else:
                data = e.result
        else:
            data = {}

        # 1. Statistical Test Finding
        if e.tool_name == "statistical_test" and isinstance(data, dict):
            test_name = data.get("test", "Statistical test")
            p_val = data.get("p_value", 1.0)
            is_sig = data.get("is_significant", False)
            es_metric = data.get("effect_size_metric", "effect size")
            es_val = data.get("effect_size", 0.0)

            title = f"{format_column_name(test_name)} on Group Distribution"
            obs = (
                f"• Key Finding: Group comparison evaluated via {format_column_name(test_name)}.\n"
                f"• Statistical Metric: Observed p-value of {p_val} with {es_metric} of {es_val}.\n"
                f"• Analysis: {'Differences between evaluated groups are statistically significant.' if is_sig else 'Observed group differences do not reach significance thresholds.'}"
            )
            if is_sig:
                status = "supported"
                interp = "The observed difference between tested groups is statistically significant."
            else:
                status = "inconclusive"
                interp = "The evidence does not meet significance thresholds; differences could be due to random chance."

            findings.append(
                FindingDraft(
                    title=title,
                    observation=obs,
                    interpretation=interp,
                    limitations="Assumes sample represents target population; requires independent confirmation.",
                    hypothesis_status=status,
                    evidence_execution_ids=[e.id]
                )
            )

        # 2. Correlation Finding
        elif e.tool_name == "correlation_analysis" and isinstance(data, dict):
            ranked = data.get("ranked_pairs", [])
            if ranked:
                top = ranked[0]
                col_a = top["column_a"]
                col_b = top["column_b"]
                r = top["correlation"]
                p = top["p_value"]
                direction = top["direction"]
                strength = top["strength"]

                col_a_clean = format_column_name(col_a)
                col_b_clean = format_column_name(col_b)
                title = f"{strength.capitalize()} {direction.capitalize()} Correlation: {col_a_clean} & {col_b_clean}"
                obs = (
                    f"• Key Finding: {strength.capitalize()} {direction} association detected between {col_a_clean} and {col_b_clean}.\n"
                    f"• Correlation Strength: Coefficient r = {r} (p = {p}, n = {top.get('n')}).\n"
                    f"• Practical Context: Higher values of {col_a_clean} tend to co-occur with {direction} values of {col_b_clean}."
                )
                interp = f"Observations of higher {col_a_clean} tend to co-occur with {direction} {col_b_clean}. This association does not establish causality."
                findings.append(
                    FindingDraft(
                        title=title,
                        observation=obs,
                        interpretation=interp,
                        limitations="Correlation measures mathematical association only, not causal mechanisms.",
                        hypothesis_status="supported" if p < 0.05 else "inconclusive",
                        evidence_execution_ids=[e.id]
                    )
                )

        # 3. GroupBy Finding
        elif e.tool_name == "group_by_analysis" and isinstance(data, dict):
            grp_col = data.get("group_column")
            metric_col = data.get("metric_column")
            groups = data.get("groups", [])
            agg = data.get("aggregation", "mean")
            if len(groups) >= 2:
                top_grp = groups[0]
                bot_grp = groups[-1]
                grp_clean = format_column_name(grp_col)
                metric_clean = format_column_name(metric_col)
                title = f"Distribution of {agg.capitalize()} {metric_clean} Across {grp_clean} Groups"
                obs = (
                    f"• Key Finding: Noticeable variation in {metric_clean} across distinct {grp_clean} categories.\n"
                    f"• Top Category: '{top_grp['group']}' recorded highest {metric_clean} of {top_grp['metric_value']}.\n"
                    f"• Baseline Category: '{bot_grp['group']}' recorded {metric_clean} of {bot_grp['metric_value']}."
                )
                findings.append(
                    FindingDraft(
                        title=title,
                        observation=obs,
                        interpretation=f"Substantial categorical divergence observed across {grp_clean} segments.",
                        limitations="Descriptive group comparison; excludes latent confounding factors.",
                        hypothesis_status="descriptive",
                        evidence_execution_ids=[e.id]
                    )
                )

        # 4. Outlier Finding
        elif e.tool_name == "detect_outliers" and isinstance(data, dict):
            outlier_cnt = data.get("outlier_count", 0)
            if outlier_cnt > 0:
                col = data.get("column")
                pct = data.get("outlier_pct")
                col_clean = format_column_name(col)
                title = f"Identified {outlier_cnt} Outliers in {col_clean}"
                obs = (
                    f"• Key Finding: Detected {outlier_cnt} statistical outliers in {col_clean}.\n"
                    f"• Data Scope: Represents {pct}% of valid records in this column.\n"
                    f"• Operational Range: Values fell beyond normal bounds ({data.get('lower_bound')} to {data.get('upper_bound')})."
                )
                findings.append(
                    FindingDraft(
                        title=title,
                        observation=obs,
                        interpretation="Extreme values may represent data entry errors, rare events, or distinct sub-populations.",
                        limitations="Outlier detection was conducted with Tukey IQR boundaries.",
                        hypothesis_status="descriptive",
                        evidence_execution_ids=[e.id]
                    )
                )

        # 5. Missing Values Finding
        elif e.tool_name == "detect_missing_values" and isinstance(data, dict):
            col_summary = data.get("columns", [])
            missing_cols = [c for c in col_summary if c.get("missing_count", 0) > 0]
            if missing_cols:
                top_m = max(missing_cols, key=lambda x: x.get("missing_count", 0))
                m_col = format_column_name(top_m.get("column", "Unknown"))
                m_cnt = top_m.get("missing_count", 0)
                m_pct = top_m.get("missing_pct", 0.0)
                title = f"Missing Data Assessment for {m_col}"
                obs = (
                    f"• Key Finding: Unrecorded entries identified in {m_col}.\n"
                    f"• Data Coverage: {m_cnt} missing records ({m_pct}% of total records).\n"
                    f"• Data Quality Impact: High missingness requires imputation or separate unknown category."
                )
                findings.append(
                    FindingDraft(
                        title=title,
                        observation=obs,
                        interpretation=f"Missingness in {m_col} may stem from optional user input or unrecorded events.",
                        limitations="Rows with missing values may require filtering prior to modeling.",
                        hypothesis_status="descriptive",
                        evidence_execution_ids=[e.id]
                    )
                )

    return findings

def write_findings(
    executions: list[ToolExecution],
    llm: LLMClient
) -> list[FindingDraft]:
    """Generates evidence-backed findings from tool executions via LLM with deterministic fallback."""
    if not executions:
        return []

    summary = build_execution_summary(executions)
    prompt = make_interpreter_prompt(summary)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    try:
        response = llm.generate(
            messages=messages,
            response_schema=FindingsContainer,
            temperature=0.2
        )

        if response.structured_data and isinstance(response.structured_data, FindingsContainer) and response.structured_data.findings:
            logger.info(f"LLM generated {len(response.structured_data.findings)} findings")
            return response.structured_data.findings
    except Exception as e:
        logger.warning(f"LLM finding synthesis encountered error ({str(e)}), using deterministic findings synthesizer.")

    # Fallback to deterministic generator
    logger.info("Using deterministic finding synthesizer from tool executions")
    return generate_findings_from_tools(executions)
