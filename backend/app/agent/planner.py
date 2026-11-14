from app.agent.llm.base import LLMClient
from app.agent.prompts import SYSTEM_PROMPT, make_planning_prompt
from app.core.logging import logger
from app.schemas.analysis import InvestigationPlan, PlanStep
from app.schemas.dataset import DatasetProfile

def build_compact_profile(profile: DatasetProfile) -> str:
    """Builds a token-efficient summary of the dataset profile for the LLM prompt."""
    lines = [
        f"Rows: {profile.n_rows}, Columns: {profile.n_cols}",
        f"Duplicate Rows: {profile.duplicate_rows}, Total Missing: {profile.missing_total_pct}%",
        "\nColumns:"
    ]
    for c in profile.columns:
        desc = f"- '{c.name}' ({c.dtype}, nulls: {c.null_pct}%, unique: {c.unique})"
        if c.stats and c.dtype == "numeric":
            desc += f" -> mean: {c.stats.get('mean')}, std: {c.stats.get('std')}, min: {c.stats.get('min')}, max: {c.stats.get('max')}"
        elif c.top_values and c.dtype in ["categorical", "boolean"]:
            top_strs = [f"{item['value']} ({item['count']})" for item in c.top_values[:3]]
            desc += f" -> top: [{', '.join(top_strs)}]"
        lines.append(desc)
    return "\n".join(lines)

def make_plan(
    profile: DatasetProfile,
    question: str | None,
    llm: LLMClient
) -> InvestigationPlan:
    """Generates a structured investigation plan based on the profile and optional user question."""
    compact_summary = build_compact_profile(profile)
    planning_prompt = make_planning_prompt(compact_summary, question)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": planning_prompt}
    ]

    try:
        response = llm.generate(
            messages=messages,
            response_schema=InvestigationPlan,
            temperature=0.2
        )

        if response.structured_data and isinstance(response.structured_data, InvestigationPlan):
            plan = response.structured_data
            logger.info(f"Generated plan with {len(plan.steps)} steps")
            return plan
    except Exception as e:
        logger.warning(f"LLM plan generation failed ({str(e)}), falling back to deterministic plan.")

    # Fallback default plan if structured data parsing failed
    logger.warning("Falling back to default deterministic investigation plan")
    num_cols = [c.name for c in profile.columns if c.dtype == "numeric"]
    cat_cols = [c.name for c in profile.columns if c.dtype in ["categorical", "boolean"]]

    steps = [
        PlanStep(
            id=1,
            goal="Inspect baseline descriptive statistics for all numeric metrics.",
            hypothesis="Numeric variables exhibit substantial variance.",
            suggested_tool="calculate_statistics",
            columns=num_cols[:4] if num_cols else []
        )
    ]
    if len(num_cols) >= 2:
        steps.append(
            PlanStep(
                id=2,
                goal=f"Analyze correlation between {num_cols[0]} and {num_cols[1]}.",
                hypothesis=f"{num_cols[0]} correlates with {num_cols[1]}.",
                suggested_tool="correlation_analysis",
                columns=num_cols[:4],
                method="pearson"
            )
        )
    if cat_cols and num_cols:
        steps.append(
            PlanStep(
                id=3,
                goal=f"Compare {num_cols[0]} across {cat_cols[0]} categories.",
                hypothesis=f"{num_cols[0]} differs significantly across {cat_cols[0]}.",
                suggested_tool="group_by_analysis",
                group_column=cat_cols[0],
                metric_column=num_cols[0],
                aggregation="mean"
            )
        )
        steps.append(
            PlanStep(
                id=4,
                goal=f"Run formal hypothesis test comparing {num_cols[0]} by {cat_cols[0]}.",
                hypothesis=f"Difference in {num_cols[0]} across {cat_cols[0]} is statistically significant.",
                suggested_tool="statistical_test",
                group_column=cat_cols[0],
                value_column=num_cols[0],
                test_type="auto"
            )
        )
    return InvestigationPlan(steps=steps)
