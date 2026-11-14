import math
from typing import Any, Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy import stats as sp_stats

from app.core.errors import ToolArgumentError
from app.schemas.tool import Filter, ToolResult
from app.tools.base import apply_filters, require_columns, require_numeric
from app.tools.registry import tool

class StatTestArgs(BaseModel):
    test_type: Literal[
        "auto",
        "two_group_comparison",
        "multi_group_comparison",
        "correlation",
        "categorical_independence",
    ] = Field(
        default="auto",
        description="Type of test to run. 'auto' selects the most appropriate test based on data types and distribution."
    )
    group_column: str | None = Field(default=None, description="Categorical column for grouping or first categorical column.")
    value_column: str | None = Field(default=None, description="Numeric metric column or first variable.")
    second_column: str | None = Field(default=None, description="Second numeric or categorical column for paired tests.")
    filters: list[Filter] = Field(default_factory=list, description="Row filters to apply.")

def check_normality(series: pd.Series) -> tuple[bool, str, float]:
    """
    Checks normality of a series using Shapiro-Wilk (n <= 5000) or D'Agostino-Pearson.
    Bounds huge series to a 5,000 observation sample with fixed seed for determinism and speed.
    Returns: (is_normal, test_name, p_value)
    """
    s = series.dropna()
    n = len(s)
    if n < 3:
        return False, "insufficient_sample", 0.0
    if n > 5000:
        s = s.sample(5000, random_state=42)
        n = 5000

    if n <= 5000 and n <= 500:
        stat, p = sp_stats.shapiro(s)
        test_name = "shapiro_wilk"
    else:
        stat, p = sp_stats.normaltest(s)
        test_name = "dagostino_pearson"
    return bool(p >= 0.05), test_name, float(p)

@tool(
    name="statistical_test",
    description="Run rigorous statistical hypothesis tests (Welch t-test, Mann-Whitney U, ANOVA, Kruskal-Wallis, Chi-square) with automatic assumption checking and effect sizes."
)
def statistical_test(args: StatTestArgs, df: pd.DataFrame) -> ToolResult:
    d = apply_filters(df, args.filters)

    # Determine test type if set to auto
    resolved_type = args.test_type
    if resolved_type == "auto":
        if args.group_column and args.value_column:
            require_columns(d, args.group_column, args.value_column)
            if pd.api.types.is_numeric_dtype(d[args.value_column]):
                n_groups = d[args.group_column].dropna().nunique()
                resolved_type = "two_group_comparison" if n_groups <= 2 else "multi_group_comparison"
            else:
                resolved_type = "categorical_independence"
                args.second_column = args.value_column
        elif args.value_column and args.second_column:
            require_columns(d, args.value_column, args.second_column)
            both_num = pd.api.types.is_numeric_dtype(d[args.value_column]) and pd.api.types.is_numeric_dtype(d[args.second_column])
            resolved_type = "correlation" if both_num else "categorical_independence"
        else:
            raise ToolArgumentError("Must specify at least (group_column and value_column) or (value_column and second_column).")

    # 1. Two-Group Comparison
    if resolved_type == "two_group_comparison":
        if not args.group_column or not args.value_column:
            raise ToolArgumentError("two_group_comparison requires 'group_column' and 'value_column'.")
        require_columns(d, args.group_column, args.value_column)
        require_numeric(d, args.value_column)

        sub = d[[args.group_column, args.value_column]].dropna()
        groups = list(sub[args.group_column].unique())
        if len(groups) < 2:
            return ToolResult(
                ok=False,
                error=f"Need at least 2 distinct groups in '{args.group_column}'. Found: {groups}",
                row_count_used=len(d)
            )

        g1_name, g2_name = str(groups[0]), str(groups[1])
        s1 = sub[sub[args.group_column] == groups[0]][args.value_column]
        s2 = sub[sub[args.group_column] == groups[1]][args.value_column]

        n1, n2 = len(s1), len(s2)
        if n1 < 3 or n2 < 3:
            return ToolResult(
                ok=False,
                error=f"Each group needs at least 3 non-null values. Group '{g1_name}': n={n1}, '{g2_name}': n={n2}",
                row_count_used=len(d)
            )

        norm1, test_name1, p_norm1 = check_normality(s1)
        norm2, test_name2, p_norm2 = check_normality(s2)
        both_normal = norm1 and norm2

        assumptions = {
            "normality_group_1": {"normal": norm1, "test": test_name1, "p_value": round(p_norm1, 4)},
            "normality_group_2": {"normal": norm2, "test": test_name2, "p_value": round(p_norm2, 4)},
            "n_group_1": n1,
            "n_group_2": n2,
            "equal_variance": False
        }

        if both_normal and n1 >= 20 and n2 >= 20:
            # Welch's t-test (robust against unequal variances)
            res = sp_stats.ttest_ind(s1, s2, equal_var=False)
            test_used = "welch_t_test"
            reason = "Parametric Welch t-test chosen because both groups are normally distributed."
            stat_val = float(res.statistic)
            p_val = float(res.pvalue)

            # Cohen's d effect size
            s_pooled = math.sqrt(((s1.var(ddof=1) * (n1 - 1)) + (s2.var(ddof=1) * (n2 - 1))) / (n1 + n2 - 2))
            effect_size = (s1.mean() - s2.mean()) / s_pooled if s_pooled > 0 else 0.0
            effect_metric = "cohens_d"
        else:
            # Mann-Whitney U test (non-parametric)
            res = sp_stats.mannwhitneyu(s1, s2, alternative="two-sided")
            test_used = "mann_whitney_u"
            reason = "Non-parametric Mann-Whitney U chosen due to non-normality or small sample size (n < 20)."
            stat_val = float(res.statistic)
            p_val = float(res.pvalue)

            # Rank-biserial correlation effect size: 1 - (2*U / (n1*n2))
            effect_size = 1.0 - (2.0 * stat_val) / (n1 * n2)
            effect_metric = "rank_biserial_r"

        diff_means = float(s1.mean() - s2.mean())
        abs_es = abs(effect_size)
        es_label = "large" if abs_es >= 0.8 else "medium" if abs_es >= 0.5 else "small" if abs_es >= 0.2 else "negligible"

        # 95% Confidence Interval for difference in means
        se_diff = math.sqrt((s1.var(ddof=1) / n1) + (s2.var(ddof=1) / n2)) if n1 > 1 and n2 > 1 else 0.0
        if se_diff > 0:
            df_welch = ((s1.var(ddof=1)/n1 + s2.var(ddof=1)/n2)**2) / (
                ((s1.var(ddof=1)/n1)**2)/(n1-1) + ((s2.var(ddof=1)/n2)**2)/(n2-1)
            ) if (n1 > 1 and n2 > 1) else 1.0
            t_crit = float(sp_stats.t.ppf(0.975, df=max(1.0, df_welch)))
            ci_lower = round(diff_means - t_crit * se_diff, 4)
            ci_upper = round(diff_means + t_crit * se_diff, 4)
        else:
            ci_lower = round(diff_means, 4)
            ci_upper = round(diff_means, 4)

        warnings = []
        if (n1 + n2) > 100_000:
            warnings.append("Sample size exceeds 100,000: p-values may be overly sensitive to trivial shifts. Rely on effect size.")

        return ToolResult(
            ok=True,
            data={
                "test": test_used,
                "selection_reason": reason,
                "groups": {
                    g1_name: {"mean": round(float(s1.mean()), 4), "median": round(float(s1.median()), 4), "std": round(float(s1.std(ddof=1)), 4), "n": n1},
                    g2_name: {"mean": round(float(s2.mean()), 4), "median": round(float(s2.median()), 4), "std": round(float(s2.std(ddof=1)), 4), "n": n2},
                },
                "difference_in_means": round(diff_means, 4),
                "ci_95": [ci_lower, ci_upper],
                "confidence_interval": {"lower": ci_lower, "upper": ci_upper, "level": 0.95},
                "statistic": round(stat_val, 4),
                "p_value": float(f"{p_val:.4e}"),
                "is_significant": bool(p_val < 0.05),
                "effect_size": round(float(effect_size), 4),
                "effect_size_metric": effect_metric,
                "effect_magnitude": es_label,
                "total_n": n1 + n2,
                "assumptions": assumptions,
            },
            warnings=warnings,
            row_count_used=len(d)
        )

    # 2. Multi-Group Comparison (ANOVA / Kruskal-Wallis)
    elif resolved_type == "multi_group_comparison":
        if not args.group_column or not args.value_column:
            raise ToolArgumentError("multi_group_comparison requires 'group_column' and 'value_column'.")
        require_columns(d, args.group_column, args.value_column)
        require_numeric(d, args.value_column)

        sub = d[[args.group_column, args.value_column]].dropna()
        group_names = list(sub[args.group_column].unique())
        if len(group_names) < 3:
            raise ToolArgumentError(f"multi_group_comparison requires 3+ groups. Found {len(group_names)}: {group_names}")

        samples = [sub[sub[args.group_column] == g][args.value_column] for g in group_names]
        group_details = {}
        all_normal = True

        for g, s in zip(group_names, samples):
            norm, test_name, p_norm = check_normality(s)
            if not norm or len(s) < 15:
                all_normal = False
            group_details[str(g)] = {
                "mean": round(float(s.mean()), 4),
                "median": round(float(s.median()), 4),
                "std": round(float(s.std(ddof=1)), 4) if len(s) > 1 else 0.0,
                "n": len(s),
                "normal": norm
            }

        if all_normal:
            f_stat, p_val = sp_stats.f_oneway(*samples)
            test_used = "one_way_anova"
            reason = "Parametric One-Way ANOVA chosen because distributions satisfy normality."
            # Eta-squared
            ss_total = float(((sub[args.value_column] - sub[args.value_column].mean()) ** 2).sum())
            ss_between = float(sum(len(s) * ((s.mean() - sub[args.value_column].mean()) ** 2) for s in samples))
            eta_squared = ss_between / ss_total if ss_total > 0 else 0.0
            effect_size = eta_squared
            effect_metric = "eta_squared"
        else:
            h_stat, p_val = sp_stats.kruskal(*samples)
            test_used = "kruskal_wallis"
            reason = "Non-parametric Kruskal-Wallis H test chosen because one or more groups violate normality."
            # Epsilon-squared: (H - k + 1) / (n - k)
            n_tot = len(sub)
            k = len(group_names)
            eps_sq = (h_stat - k + 1) / (n_tot - k) if n_tot > k else 0.0
            effect_size = max(0.0, float(eps_sq))
            effect_metric = "epsilon_squared"
            f_stat = h_stat

        return ToolResult(
            ok=True,
            data={
                "test": test_used,
                "selection_reason": reason,
                "groups": group_details,
                "statistic": round(float(f_stat), 4),
                "p_value": float(f"{p_val:.4e}"),
                "is_significant": bool(p_val < 0.05),
                "effect_size": round(float(effect_size), 4),
                "effect_size_metric": effect_metric,
                "total_n": len(sub),
            },
            row_count_used=len(d)
        )

    # 3. Correlation Test
    elif resolved_type == "correlation":
        col1 = args.value_column or args.group_column
        col2 = args.second_column
        if not col1 or not col2:
            raise ToolArgumentError("correlation requires two columns.")
        require_columns(d, col1, col2)
        require_numeric(d, col1, col2)

        sub = d[[col1, col2]].dropna()
        n = len(sub)
        if n < 5:
            return ToolResult(ok=False, error=f"Need at least 5 paired points. Found: {n}", row_count_used=len(d))

        norm1, _, p_n1 = check_normality(sub[col1])
        norm2, _, p_n2 = check_normality(sub[col2])

        if norm1 and norm2 and n >= 20:
            res = sp_stats.pearsonr(sub[col1], sub[col2])
            test_used = "pearson_correlation"
            reason = "Pearson correlation test selected for bivariate normal distribution."
        else:
            res = sp_stats.spearmanr(sub[col1], sub[col2])
            test_used = "spearman_rank_correlation"
            reason = "Spearman rank correlation selected due to non-normality or rank-monotonicity."

        r_val = float(res.statistic)
        p_val = float(res.pvalue)

        return ToolResult(
            ok=True,
            data={
                "test": test_used,
                "selection_reason": reason,
                "column_a": col1,
                "column_b": col2,
                "statistic": round(r_val, 4),
                "p_value": float(f"{p_val:.4e}"),
                "is_significant": bool(p_val < 0.05),
                "effect_size": round(abs(r_val), 4),
                "effect_size_metric": "correlation_coefficient",
                "n": n,
            },
            warnings=["Correlation does not imply causation."],
            row_count_used=len(d)
        )

    # 4. Categorical Independence (Chi-square)
    elif resolved_type == "categorical_independence":
        col1 = args.group_column or args.value_column
        col2 = args.second_column
        if not col1 or not col2:
            raise ToolArgumentError("categorical_independence requires two columns.")
        require_columns(d, col1, col2)

        sub = d[[col1, col2]].dropna()
        if len(sub) < 10:
            return ToolResult(ok=False, error="Need at least 10 observations for categorical test.", row_count_used=len(d))

        table = pd.crosstab(sub[col1], sub[col2])
        chi2, p_val, dof, expected = sp_stats.chi2_contingency(table)

        # Assumptions check: expected frequencies < 5
        min_expected = float(expected.min())
        pct_under_5 = float((expected < 5).sum() / expected.size * 100.0)

        # Cramér's V: sqrt(chi2 / (n * min(r-1, k-1)))
        n_obs = len(sub)
        r, k = table.shape
        denom = n_obs * min(r - 1, k - 1)
        cramers_v = math.sqrt(chi2 / denom) if denom > 0 else 0.0

        warnings = []
        if pct_under_5 > 20:
            warnings.append(f"{pct_under_5:.1f}% of contingency cells have expected frequency < 5.")

        return ToolResult(
            ok=True,
            data={
                "test": "chi_square_independence",
                "selection_reason": "Chi-square test of independence for cross-tabulated categorical variables.",
                "column_a": col1,
                "column_b": col2,
                "statistic": round(float(chi2), 4),
                "p_value": float(f"{p_val:.4e}"),
                "degrees_of_freedom": int(dof),
                "is_significant": bool(p_val < 0.05),
                "effect_size": round(float(cramers_v), 4),
                "effect_size_metric": "cramers_v",
                "total_n": n_obs,
                "min_expected_frequency": round(min_expected, 2),
            },
            warnings=warnings,
            row_count_used=len(d)
        )

    else:
        raise ToolArgumentError(f"Unsupported test type: '{resolved_type}'")
