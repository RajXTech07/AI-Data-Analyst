import math
from typing import Any
import uuid
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.db.models.dataset import Dataset
from app.db.models.scenario import Scenario, ScenarioOperation
from app.schemas.scenario import (
    MetricComparison,
    ScenarioComparisonResponse,
    ScenarioCreateRequest,
    ScenarioOperationCreate,
    ScenarioRecomputeRequest,
)
from app.services.columnar_engine import sanitize_value
from app.services.datasets import dataset_service

class ScenarioEngine:
    """
    Manages non-destructive What-If Scenarios layered over cleaned datasets.
    Recomputes statistical findings, tracks metric deltas, and performs
    sensitivity analysis to detect fragile findings.
    """

    @staticmethod
    def create_scenario(
        db: Session,
        dataset: Dataset,
        request: ScenarioCreateRequest
    ) -> Scenario:
        scenario = Scenario(
            dataset_id=dataset.id,
            name=request.name,
            description=request.description
        )
        db.add(scenario)
        db.flush()

        for idx, op in enumerate(request.operations):
            op_record = ScenarioOperation(
                scenario_id=scenario.id,
                seq=idx + 1,
                op_type=op.op_type,
                parameters=op.parameters,
                reason=op.reason
            )
            db.add(op_record)

        db.commit()
        db.refresh(scenario)
        return scenario

    @staticmethod
    def apply_scenario_operations(
        baseline_df: pd.DataFrame,
        operations: list[ScenarioOperation] | list[ScenarioOperationCreate]
    ) -> tuple[pd.DataFrame, int]:
        """
        Applies a list of scenario operations in sequence onto the baseline DataFrame.
        Returns: (scenario_df, rows_affected_count)
        """
        df = baseline_df.copy()
        initial_count = len(df)
        modified_rows = set()

        for op in operations:
            op_type = op.op_type
            params = op.parameters

            # 1. Row Filter
            if op_type == "filter":
                col = params.get("column")
                operator = params.get("operator", "eq")
                val = params.get("value")
                if col in df.columns:
                    before_idx = set(df.index)
                    if operator == "eq":
                        df = df[df[col] == val]
                    elif operator == "gt":
                        df = df[df[col] > float(val)]
                    elif operator == "lt":
                        df = df[df[col] < float(val)]
                    elif operator == "gte":
                        df = df[df[col] >= float(val)]
                    elif operator == "lte":
                        df = df[df[col] <= float(val)]
                    elif operator == "ne":
                        df = df[df[col] != val]
                    after_idx = set(df.index)
                    modified_rows.update(before_idx - after_idx)

            # 2. Exclude Specific Rows
            elif op_type == "exclude_rows":
                rows_to_drop = params.get("row_indices", [])
                valid_drops = [idx for idx in rows_to_drop if idx in df.index]
                if valid_drops:
                    df = df.drop(index=valid_drops)
                    modified_rows.update(valid_drops)

            # 3. Override Cell Values
            elif op_type == "override_value":
                overrides = params.get("overrides", [])  # list of {row_index, column, new_value}
                for item in overrides:
                    r_idx = item.get("row_index")
                    col = item.get("column")
                    val = item.get("new_value")
                    if r_idx in df.index and col in df.columns:
                        df.loc[r_idx, col] = np.nan if val is None else val
                        modified_rows.add(r_idx)

            # 4. Imputation Method
            elif op_type == "imputation":
                col = params.get("column")
                method = params.get("method", "median")
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    null_idx = set(df[df[col].isna()].index)
                    if null_idx:
                        fill_val = float(df[col].median()) if method == "median" else float(df[col].mean())
                        df[col] = df[col].fillna(fill_val)
                        modified_rows.update(null_idx)

            # 5. Merge / Relabel Groups
            elif op_type == "merge_groups":
                col = params.get("column")
                mapping = params.get("mapping", {})  # {"Old": "New"}
                if col in df.columns and mapping:
                    changed = df[df[col].isin(mapping.keys())].index
                    df[col] = df[col].replace(mapping)
                    modified_rows.update(changed)

            # 6. Unit Conversion (Scale factor)
            elif op_type == "unit_conversion":
                col = params.get("column")
                factor = float(params.get("factor", 1.0))
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col] * factor
                    modified_rows.update(df.index)

        return df, len(modified_rows)

    @staticmethod
    def recompute_scenario(
        db: Session,
        scenario: Scenario,
        req: ScenarioRecomputeRequest | None = None
    ) -> ScenarioComparisonResponse:
        dataset = scenario.dataset
        baseline_df = dataset_service.load_dataframe(dataset, cleaned=True)
        scenario_df, rows_affected = ScenarioEngine.apply_scenario_operations(baseline_df, scenario.operations)

        total_rows = len(baseline_df)
        fraction_affected = round(rows_affected / total_rows, 4) if total_rows > 0 else 0.0
        warning_triggered = fraction_affected > 0.20  # Warn if > 20% rows changed

        numeric_cols = [c for c in baseline_df.columns if pd.api.types.is_numeric_dtype(baseline_df[c])]
        target_cols = req.target_columns if req and req.target_columns else numeric_cols[:4]

        comparisons: list[MetricComparison] = []
        fragile_findings: list[str] = []
        scenario_findings: list[dict[str, Any]] = []

        # 1. Compare Central Tendency Metrics
        for col in target_cols:
            if col not in baseline_df.columns or col not in scenario_df.columns:
                continue

            b_series = baseline_df[col].dropna()
            s_series = scenario_df[col].dropna()

            b_mean = float(b_series.mean()) if len(b_series) > 0 else None
            s_mean = float(s_series.mean()) if len(s_series) > 0 else None

            if b_mean is not None and s_mean is not None:
                abs_chg = s_mean - b_mean
                pct_chg = round((abs_chg / abs(b_mean) * 100.0) if b_mean != 0 else 0.0, 2)
                flipped = abs(pct_chg) > 10.0
                is_fragile = flipped and (fraction_affected < 0.05)

                if is_fragile:
                    fragile_findings.append(f"Mean of '{col}' shifted {pct_chg:+.1f}% under minimal scenario modification (< 5% rows).")

                comparisons.append(
                    MetricComparison(
                        metric_name=f"{col} (Mean)",
                        baseline_value=round(b_mean, 4),
                        scenario_value=round(s_mean, 4),
                        absolute_change=round(abs_chg, 4),
                        percentage_change=pct_chg,
                        conclusion_flipped=flipped,
                        is_fragile=is_fragile,
                        explanation=f"Mean shifted by {pct_chg:+.1f}% from baseline under scenario '{scenario.name}'."
                    )
                )

        # 2. Compare Pairwise Correlations & Detect Hypothesis Flips
        if len(target_cols) >= 2:
            col_a, col_b = target_cols[0], target_cols[1]
            b_pair = baseline_df[[col_a, col_b]].dropna()
            s_pair = scenario_df[[col_a, col_b]].dropna()

            if len(b_pair) >= 5 and len(s_pair) >= 5:
                r_base, p_base = sp_stats.pearsonr(b_pair[col_a], b_pair[col_b])
                r_scen, p_scen = sp_stats.pearsonr(s_pair[col_a], s_pair[col_b])

                # Check if statistical significance flipped!
                base_sig = p_base < 0.05
                scen_sig = p_scen < 0.05
                flipped = (base_sig != scen_sig)

                abs_r_chg = float(r_scen - r_base)
                pct_r_chg = round((abs_r_chg / abs(r_base) * 100.0) if r_base != 0 else 0.0, 2)

                if flipped:
                    status_change = "no longer statistically significant" if not scen_sig else "became statistically significant"
                    fragile_findings.append(f"Fragile finding: Correlation between '{col_a}' and '{col_b}' {status_change} (p: {p_base:.3e} -> {p_scen:.3e}).")

                comparisons.append(
                    MetricComparison(
                        metric_name=f"Correlation({col_a}, {col_b})",
                        baseline_value=round(float(r_base), 4),
                        scenario_value=round(float(r_scen), 4),
                        absolute_change=round(abs_r_chg, 4),
                        percentage_change=pct_r_chg,
                        conclusion_flipped=flipped,
                        is_fragile=flipped,
                        explanation=f"Pearson correlation changed from r={r_base:.2f} (p={p_base:.3e}) to r={r_scen:.2f} (p={p_scen:.3e})."
                    )
                )

                scenario_findings.append({
                    "title": f"Scenario: {scenario.name} — Correlation Shift",
                    "relationship": f"{col_a} vs {col_b}",
                    "scenario_correlation": round(float(r_scen), 4),
                    "baseline_correlation": round(float(r_base), 4),
                    "significance_flipped": flipped
                })

        explain = {
            "scenario_name": scenario.name,
            "rows_affected": rows_affected,
            "percentage_rows_affected": round(fraction_affected * 100.0, 2),
            "safety_warning": "Scenario modifies > 20% of dataset rows. Inferences may reflect a non-representative cohort." if warning_triggered else "Modifications within standard parameter bounds.",
            "fragile_count": len(fragile_findings)
        }

        return ScenarioComparisonResponse(
            scenario_id=str(scenario.id),
            scenario_name=scenario.name,
            dataset_id=str(dataset.id),
            rows_affected=rows_affected,
            fraction_affected=fraction_affected,
            warning_triggered=warning_triggered,
            metrics=comparisons,
            fragile_findings=fragile_findings,
            scenario_findings=scenario_findings,
            explain=explain
        )

scenario_engine = ScenarioEngine()
