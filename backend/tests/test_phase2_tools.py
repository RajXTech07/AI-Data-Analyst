import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy import stats as sp_stats

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.tools import REGISTRY, list_tools, llm_tool_schemas, run_tool

@pytest.fixture
def synthetic_df():
    csv_path = Path(__file__).resolve().parent.parent.parent / "datasets" / "synthetic_planted.csv"
    assert csv_path.exists(), f"Synthetic dataset not found at {csv_path}"
    return pd.read_csv(csv_path)

@pytest.fixture
def student_df():
    csv_path = Path(__file__).resolve().parent.parent.parent / "datasets" / "student_performance.csv"
    assert csv_path.exists(), f"Student dataset not found at {csv_path}"
    return pd.read_csv(csv_path)

def test_registry_registration():
    expected_tools = {
        "profile_dataset",
        "detect_missing_values",
        "detect_duplicates",
        "calculate_statistics",
        "group_by_analysis",
        "correlation_analysis",
        "detect_outliers",
        "trend_analysis",
        "statistical_test",
        "generate_chart",
    }
    registered = set(REGISTRY.keys())
    assert expected_tools.issubset(registered), f"Missing tools: {expected_tools - registered}"

    schemas = llm_tool_schemas()
    assert len(schemas) >= 10
    for s in schemas:
        assert "name" in s
        assert "description" in s
        assert "parameters" in s

def test_profile_dataset(synthetic_df):
    result = run_tool("profile_dataset", {}, synthetic_df)
    assert result.ok is True
    assert result.data["n_rows"] == 23
    assert result.data["n_cols"] == 6
    assert len(result.data["columns"]) == 6

def test_detect_missing_values(synthetic_df):
    result = run_tool("detect_missing_values", {}, synthetic_df)
    assert result.ok is True
    data = result.data
    assert data["total_missing_cells"] == 2
    assert data["total_rows_with_missing"] == 2
    # Column 'grade' should be flagged as having 2 missing values
    col_map = {c["column"]: c for c in data["columns"]}
    assert col_map["grade"]["missing_count"] == 2

def test_detect_duplicates(synthetic_df):
    result = run_tool("detect_duplicates", {"subset": ["department", "hours_studied", "attendance", "grade"]}, synthetic_df)
    assert result.ok is True
    assert result.data["duplicate_count"] >= 1
    assert len(result.data["sample_duplicate_rows"]) > 0

def test_calculate_statistics_against_scipy(synthetic_df):
    result = run_tool("calculate_statistics", {"columns": ["hours_studied", "attendance"]}, synthetic_df)
    assert result.ok is True
    stats_list = result.data["statistics"]
    hours_stat = next(s for s in stats_list if s["column"] == "hours_studied")

    # Verify against scipy / pandas reference ground truth
    clean_hours = synthetic_df["hours_studied"].dropna()
    assert abs(hours_stat["mean"] - round(float(clean_hours.mean()), 4)) < 1e-3
    assert abs(hours_stat["median"] - round(float(clean_hours.median()), 4)) < 1e-3
    assert abs(hours_stat["std"] - round(float(clean_hours.std(ddof=1)), 4)) < 1e-3
    assert abs(hours_stat["skewness"] - round(float(sp_stats.skew(clean_hours, bias=False)), 4)) < 1e-3

def test_group_by_analysis(synthetic_df):
    result = run_tool(
        "group_by_analysis",
        {"group_column": "department", "metric_column": "hours_studied", "aggregation": "mean"},
        synthetic_df
    )
    assert result.ok is True
    groups = result.data["groups"]
    assert len(groups) == 2
    science_grp = next(g for g in groups if g["group"] == "Science")
    arts_grp = next(g for g in groups if g["group"] == "Arts")
    # Science study hours should be substantially higher than Arts in synthetic dataset
    assert science_grp["metric_value"] > arts_grp["metric_value"]

def test_correlation_analysis_against_scipy(synthetic_df):
    result = run_tool(
        "correlation_analysis",
        {"columns": ["hours_studied", "attendance"], "method": "pearson"},
        synthetic_df
    )
    assert result.ok is True
    ranked = result.data["ranked_pairs"]
    assert len(ranked) >= 1
    pair = ranked[0]

    # Ground truth from scipy
    sub = synthetic_df[["hours_studied", "attendance"]].dropna()
    ref_r, ref_p = sp_stats.pearsonr(sub["hours_studied"], sub["attendance"])

    assert abs(pair["correlation"] - round(float(ref_r), 4)) < 1e-3
    assert pair["direction"] == "positive"
    assert pair["strength"] == "strong"

def test_detect_outliers(synthetic_df):
    result = run_tool(
        "detect_outliers",
        {"column": "grade", "method": "iqr", "threshold": 1.5},
        synthetic_df
    )
    assert result.ok is True
    data = result.data
    assert data["outlier_count"] >= 1
    # Check that our planted 195.0 outlier is caught
    sample_values = [s["value"] for s in data["samples"]]
    assert 195.0 in sample_values

def test_statistical_test_two_groups(synthetic_df):
    result = run_tool(
        "statistical_test",
        {"group_column": "department", "value_column": "hours_studied"},
        synthetic_df
    )
    assert result.ok is True
    data = result.data
    assert data["test"] in ["welch_t_test", "mann_whitney_u"]
    assert data["is_significant"] is True
    assert data["p_value"] < 0.05
    assert "effect_size" in data
    assert "selection_reason" in data

def test_statistical_test_categorical(synthetic_df):
    result = run_tool(
        "statistical_test",
        {"group_column": "department", "value_column": "survey_rating"},
        synthetic_df
    )
    assert result.ok is True
    data = result.data
    assert data["test"] == "chi_square_independence"
    assert "degrees_of_freedom" in data
    assert "effect_size" in data

def test_generate_chart_plotly_spec(synthetic_df):
    # Scatter plot
    scatter_res = run_tool(
        "generate_chart",
        {"chart_type": "scatter", "x": "hours_studied", "y": "attendance", "title": "Hours vs Attendance"},
        synthetic_df
    )
    assert scatter_res.ok is True
    assert scatter_res.data["spec"]["data"][0]["type"] == "scatter"

    # Bar chart
    bar_res = run_tool(
        "generate_chart",
        {"chart_type": "bar", "x": "department", "y": "hours_studied", "title": "Mean Hours by Department"},
        synthetic_df
    )
    assert bar_res.ok is True
    assert bar_res.data["spec"]["data"][0]["type"] == "bar"

    # Heatmap
    heatmap_res = run_tool("generate_chart", {"chart_type": "heatmap"}, synthetic_df)
    assert heatmap_res.ok is True
    assert heatmap_res.data["spec"]["data"][0]["type"] == "heatmap"

def test_trend_analysis():
    # Construct a synthetic time series DataFrame
    dates = pd.date_range("2025-01-01", periods=12, freq="ME")
    trend_vals = [10.0 + (i * 2.5) for i in range(12)]
    df = pd.DataFrame({"month": dates, "revenue": trend_vals})

    result = run_tool("trend_analysis", {"date_column": "month", "metric_column": "revenue", "freq": "ME"}, df)
    assert result.ok is True
    data = result.data
    assert data["trend_direction"] == "upward"
    assert data["pct_change"] > 0
    assert data["is_statistically_significant"] is True

def test_invalid_arguments_graceful_handling(synthetic_df):
    # Unknown column
    result = run_tool("calculate_statistics", {"columns": ["non_existent_col"]}, synthetic_df)
    assert result.ok is False
    assert "not found in dataset" in result.error

    # Non-numeric column for statistics
    result2 = run_tool("calculate_statistics", {"columns": ["department"]}, synthetic_df)
    assert result2.ok is False
    assert "must be numeric" in result2.error

    # Unknown tool
    result3 = run_tool("arbitrary_code_runner", {"code": "print('hack')"}, synthetic_df)
    assert result3.ok is False
    assert "Unknown tool" in result3.error
