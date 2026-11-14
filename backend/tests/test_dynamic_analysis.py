import sys
from pathlib import Path
import pytest

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.db.session import init_db
from app.agent.llm.mock import MockLLMClient

@pytest.fixture(autouse=True)
def setup_database_and_mock_llm():
    init_db()
    with patch("app.agent.orchestrator.get_llm_client", return_value=MockLLMClient()), \
         patch("app.api.v1.analyses.get_llm_client", return_value=MockLLMClient()):
        yield

client = TestClient(app)

MOVIES_CSV = Path("datasets/movies_messy.csv")
STUDENT_CSV = Path("datasets/student_performance.csv")
SALES_CSV = Path("datasets/sales_data.csv")

def test_dynamic_back_to_back_uploads_and_chat():
    """
    Acceptance Test 1, 2, 3, 4:
    - Upload movies_messy.csv, then student_performance.csv.
    - Each produces its own distinct columns, issues, findings, charts, and chat answers.
    - Upload sales_data.csv with completely different columns.
    - Re-upload movies_messy.csv and verify consistency.
    """
    # -------------------------------------------------------------
    # Step 1: Upload movies_messy.csv
    # -------------------------------------------------------------
    with open(MOVIES_CSV, "rb") as f:
        resp_m1 = client.post("/api/v1/datasets/upload", files={"file": ("movies_messy.csv", f, "text/csv")})
    assert resp_m1.status_code == 201
    m1_data = resp_m1.json()
    m1_id = m1_data["id"]

    # Verify movie columns
    prof_m1 = client.get(f"/api/v1/datasets/{m1_id}/profile").json()
    movie_cols = [c["name"] for c in prof_m1["columns"]]
    assert "title" in movie_cols
    assert "genre" in movie_cols
    assert "budget_millions" in movie_cols
    assert "final_mark" not in movie_cols
    assert "department" not in movie_cols

    # Verify issues detected for movies_messy (missing tokens ?, -, duplicates, outliers)
    issues_m1 = client.get(f"/api/v1/datasets/{m1_id}/issues").json()
    assert any("dup" in i["category"] for i in issues_m1["issues"])
    assert issues_m1["summary"]["duplicates"]["count"] >= 1
    assert issues_m1["summary"]["missing_values"]["percentage"] > 0

    # Start analysis on movies_messy (TestClient runs background task synchronously)
    analyze_m1 = client.post(f"/api/v1/datasets/{m1_id}/analyze", json={})
    assert analyze_m1.status_code == 202
    m1_analysis_id = analyze_m1.json()["id"]

    # Verify findings use movie data
    findings_m1 = client.get(f"/api/v1/analyses/{m1_analysis_id}/findings").json()
    assert len(findings_m1) > 0
    # None of the findings should mention student departments
    for f in findings_m1:
        assert "Computer Science" not in f["title"]
        assert "Humanities" not in f["title"]

    # Ask chat "which columns does this dataset have?"
    chat_m1 = client.post(
        f"/api/v1/analyses/{m1_analysis_id}/chat",
        json={"message": "which columns does this dataset have?"}
    )
    assert chat_m1.status_code == 202
    chat_m1_text = chat_m1.json()["content"]
    assert "title" in chat_m1_text
    assert "genre" in chat_m1_text
    assert "budget_millions" in chat_m1_text
    assert "final_mark" not in chat_m1_text
    assert "department" not in chat_m1_text

    # -------------------------------------------------------------
    # Step 2: Upload student_performance.csv (Second Dataset)
    # -------------------------------------------------------------
    with open(STUDENT_CSV, "rb") as f:
        resp_s = client.post("/api/v1/datasets/upload", files={"file": ("student_performance.csv", f, "text/csv")})
    assert resp_s.status_code == 201
    s_data = resp_s.json()
    s_id = s_data["id"]

    # Verify student columns
    prof_s = client.get(f"/api/v1/datasets/{s_id}/profile").json()
    student_cols = [c["name"] for c in prof_s["columns"]]
    assert "department" in student_cols
    assert "final_mark" in student_cols
    assert "title" not in student_cols
    assert "budget_millions" not in student_cols

    # Start analysis on student dataset
    analyze_s = client.post(f"/api/v1/datasets/{s_id}/analyze", json={})
    assert analyze_s.status_code == 202
    s_analysis_id = analyze_s.json()["id"]

    # Ask chat "which columns does this dataset have?" on student dataset
    chat_s = client.post(
        f"/api/v1/analyses/{s_analysis_id}/chat",
        json={"message": "which columns does this dataset have?"}
    )
    assert chat_s.status_code == 202
    chat_s_text = chat_s.json()["content"]
    assert "department" in chat_s_text
    assert "final_mark" in chat_s_text
    assert "title" not in chat_s_text
    assert "budget_millions" not in chat_s_text

    # -------------------------------------------------------------
    # Step 3: Upload sales_data.csv (Third Dataset)
    # -------------------------------------------------------------
    with open(SALES_CSV, "rb") as f:
        resp_sales = client.post("/api/v1/datasets/upload", files={"file": ("sales_data.csv", f, "text/csv")})
    assert resp_sales.status_code == 201
    sales_id = resp_sales.json()["id"]

    prof_sales = client.get(f"/api/v1/datasets/{sales_id}/profile").json()
    sales_cols = [c["name"] for c in prof_sales["columns"]]
    assert "transaction_id" in sales_cols
    assert "sales_rep" in sales_cols
    assert "revenue" in sales_cols
    assert "department" not in sales_cols
    assert "title" not in sales_cols

    # Start analysis on sales dataset
    analyze_sales = client.post(f"/api/v1/datasets/{sales_id}/analyze", json={})
    assert analyze_sales.status_code == 202
    sales_analysis_id = analyze_sales.json()["id"]

    # Verify charts generated for sales dataset
    charts_sales = client.get(f"/api/v1/analyses/{sales_analysis_id}/charts").json()
    # Charts should not use movie or student columns
    for ch in charts_sales:
        spec_str = str(ch.get("spec", ""))
        assert "final_mark" not in spec_str
        assert "budget_millions" not in spec_str

    # Chat query on sales
    chat_sales = client.post(
        f"/api/v1/analyses/{sales_analysis_id}/chat",
        json={"message": "which columns does this dataset have?"}
    )
    assert chat_sales.status_code == 202
    chat_sales_text = chat_sales.json()["content"]
    assert "transaction_id" in chat_sales_text
    assert "sales_rep" in chat_sales_text
    assert "revenue" in chat_sales_text
    assert "final_mark" not in chat_sales_text
    assert "title" not in chat_sales_text

    # Ask about non-existent column
    chat_nonexistent = client.post(
        f"/api/v1/analyses/{sales_analysis_id}/chat",
        json={"message": "What is the average of final_mark?"}
    )
    assert chat_nonexistent.status_code == 202
    # Should report column does not exist and mention available columns
    nonexistent_text = chat_nonexistent.json()["content"]
    assert "not found" in nonexistent_text.lower() or "not exist" in nonexistent_text.lower() or "revenue" in nonexistent_text

    # -------------------------------------------------------------
    # Step 4: Re-upload movies_messy.csv (Consistency check)
    # -------------------------------------------------------------
    with open(MOVIES_CSV, "rb") as f:
        resp_m2 = client.post("/api/v1/datasets/upload", files={"file": ("movies_messy.csv", f, "text/csv")})
    assert resp_m2.status_code == 201
    m2_id = resp_m2.json()["id"]

    prof_m2 = client.get(f"/api/v1/datasets/{m2_id}/profile").json()
    assert prof_m2["n_rows"] == prof_m1["n_rows"]
    assert prof_m2["n_cols"] == prof_m1["n_cols"]
    assert [c["name"] for c in prof_m2["columns"]] == [c["name"] for c in prof_m1["columns"]]

def test_clean_dataset_creates_separate_copy():
    """
    Verify cleaning creates a separate copy and does not overwrite original.
    """
    with open(MOVIES_CSV, "rb") as f:
        resp = client.post("/api/v1/datasets/upload", files={"file": ("movies_messy.csv", f, "text/csv")})
    dataset_id = resp.json()["id"]

    # Request cleaning
    clean_resp = client.post(
        f"/api/v1/datasets/{dataset_id}/clean",
        json={"selected_fixes": ["drop_duplicates", "fill_median", "standardize_labels"]}
    )
    assert clean_resp.status_code == 200
    clean_data = clean_resp.json()
    assert clean_data["ok"] is True
    assert len(clean_data["changelog"]) > 0

    # Download cleaned file
    download_resp = client.get(f"/api/v1/datasets/{dataset_id}/clean/download")
    assert download_resp.status_code == 200
    content = download_resp.text
    assert "title,genre,release_year" in content

    # Check original profile is intact
    prof = client.get(f"/api/v1/datasets/{dataset_id}/profile").json()
    assert prof["n_rows"] == 18

def test_no_hardcoded_columns_in_analysis_engine():
    """
    Acceptance Test 5: Grep check verifying no hardcoded column names remain in
    mock LLM tool calls or chart execution code.
    """
    import re
    disallowed_patterns = [
        r"arguments\s*=\s*\{[^}]*['\"]final_mark['\"]",
        r"arguments\s*=\s*\{[^}]*['\"]department['\"]",
        r"arguments\s*=\s*\{[^}]*['\"]attendance['\"]",
        r"x\s*=\s*['\"]department['\"]",
        r"y\s*=\s*['\"]final_mark['\"]"
    ]

    files_to_check = [
        Path("backend/app/agent/llm/mock.py"),
        Path("backend/app/agent/orchestrator.py"),
        Path("backend/app/agent/interpreter.py"),
    ]

    for p in files_to_check:
        text = p.read_text(encoding="utf-8")
        for pat in disallowed_patterns:
            matches = re.findall(pat, text)
            assert not matches, f"Found hardcoded column pattern '{pat}' in {p}: {matches}"
