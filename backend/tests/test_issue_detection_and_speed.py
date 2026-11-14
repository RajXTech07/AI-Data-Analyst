import pytest
import pandas as pd
from app.services.safe_loader import load_csv_safely
from app.services.datasets import profile_dataframe, detect_dataset_issues
from app.schemas.analysis import PlanStep, InvestigationPlan
from app.agent.orchestrator import execute_planned_step
from app.tools import REGISTRY

def test_messy_ragged_and_trailing_summary_detection():
    """Ensure ragged rows and trailing summaries are flagged as issues."""
    csv_text = """id,name,score
1,Alice,90
2,Bob,85,extra_value_here
3,Charlie,80
Total,Summary,255
"""
    res = load_csv_safely(csv_text.encode("utf-8"), filename="test_messy.csv")
    profile = profile_dataframe(res.df, loading_report=res.loading_report)
    issues_res = detect_dataset_issues(res.df, profile)
    
    issues = issues_res.get("issues", [])
    categories = [i["category"] for i in issues]
    
    assert len(issues) >= 2, f"Expected at least 2 issues, got {len(issues)}"
    assert "structure" in categories
    
    ragged_issue = next((i for i in issues if "ragged" in i["id"]), None)
    assert ragged_issue is not None
    assert ragged_issue["severity"] == "High"
    
    summary_issue = next((i for i in issues if "trailing" in i["id"]), None)
    assert summary_issue is not None

def test_messy_corrupted_headers_and_comments():
    """Ensure empty/duplicate headers and comment lines are flagged as issues."""
    csv_text = """id,,revenue,revenue
# Stray comment line in CSV
1,Alice,100,100
2,Bob,200,200
"""
    res = load_csv_safely(csv_text.encode("utf-8"), filename="test_headers.csv")
    profile = profile_dataframe(res.df, loading_report=res.loading_report)
    issues_res = detect_dataset_issues(res.df, profile)
    
    issues = issues_res.get("issues", [])
    issue_ids = [i["id"] for i in issues]
    
    assert any("header" in i_id for i_id in issue_ids), f"Expected header modification issue in {issue_ids}"
    assert any("comment" in i_id for i_id in issue_ids), f"Expected comment issue in {issue_ids}"

def test_fast_path_planned_step_execution():
    """Verify that execute_planned_step runs instantly via fast path without calling LLM."""
    df = pd.DataFrame({
        "age": [20, 25, 30, 35],
        "salary": [50000, 60000, 75000, 90000],
        "dept": ["HR", "IT", "IT", "HR"]
    })
    profile = profile_dataframe(df)
    
    step = PlanStep(
        id=1,
        goal="Compute correlation between age and salary",
        suggested_tool="correlation_analysis",
        columns=["age", "salary"],
        method="pearson"
    )
    
    # Passing None as LLM client ensures that if an LLM network call was attempted, it would crash
    tool_name, tool_args = execute_planned_step(step, df, profile, llm=None)
    
    assert tool_name == "correlation_analysis"
    assert tool_args["columns"] == ["age", "salary"]
    assert tool_args["method"] == "pearson"

