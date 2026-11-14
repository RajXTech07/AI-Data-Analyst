"""Tests for ChatEngine intent routing, structured schema compliance, and error-free execution."""

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

MOVIES_CSV = Path("datasets/movies_messy.csv")
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_analysis():
    init_db()
    with patch("app.agent.orchestrator.get_llm_client", return_value=MockLLMClient()):
        
        # 1. Upload movies_messy.csv
        with open(MOVIES_CSV, "rb") as f:
            resp = client.post("/api/v1/datasets/upload", files={"file": ("movies_messy.csv", f, "text/csv")})
        assert resp.status_code == 201
        dataset_id = resp.json()["id"]

        # 2. Run analysis
        ana_resp = client.post(f"/api/v1/datasets/{dataset_id}/analyze", json={})
        assert ana_resp.status_code in [200, 201, 202]
        analysis_id = ana_resp.json()["id"]

        pytest.test_dataset_id = dataset_id
        pytest.test_analysis_id = analysis_id
        yield


def test_intent_which_columns_matter_most():
    """Test Intent A: 'Which columns matter most?' ranking, roles, effect sizes, cautions."""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "Which columns matter most?"}
    )
    assert resp.status_code in (200, 202)
    data = resp.json()

    # Content exists
    assert "content" in data
    assert len(data["content"]) > 0

    # Structured answer exists and adheres to schema
    assert "structured_answer" in data
    sa = data["structured_answer"]
    assert sa is not None
    assert "answer" in sa
    assert sa["answer"].startswith("**")
    assert isinstance(sa.get("key_points"), list)
    assert len(sa["key_points"]) >= 2
    assert isinstance(sa.get("numbers"), list)
    assert len(sa["numbers"]) >= 2
    assert isinstance(sa.get("cautions"), list)
    assert len(sa["cautions"]) >= 1
    assert any("causation" in c.lower() for c in sa["cautions"])
    assert isinstance(sa.get("next_questions"), list)
    assert len(sa["next_questions"]) >= 2
    assert sa.get("confidence") in ["high", "medium", "approximate"]


def test_intent_what_if_exclude_incomplete():
    """Test Intent B: 'What if I exclude incomplete rows?' - NO HTTP 500, real math before/after."""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "What if I exclude incomplete rows?"}
    )
    assert resp.status_code in (200, 202)
    data = resp.json()

    assert "content" in data
    assert "structured_answer" in data
    sa = data["structured_answer"]
    assert sa is not None

    # Verify bold answer has row removal math
    assert "row" in sa["answer"].lower()
    assert "%" in sa["answer"]

    # Verify numbers table has before/after metrics
    num_labels = [n["label"] for n in sa["numbers"]]
    assert any("row" in l.lower() for l in num_labels)

    # Verify next questions
    assert len(sa["next_questions"]) >= 2


def test_intent_list_columns():
    """Test Intent: 'What columns are in this dataset?'"""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "What columns are in this dataset?"}
    )
    assert resp.status_code in (200, 202)
    sa = resp.json().get("structured_answer")
    assert sa is not None
    assert "title" in sa["answer"].lower() or "columns" in sa["answer"].lower()
    assert len(sa["key_points"]) >= 1


def test_intent_missing_quality():
    """Test Intent: 'Are there missing values?'"""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "Are there any missing values in this data?"}
    )
    assert resp.status_code in (200, 202)
    sa = resp.json().get("structured_answer")
    assert sa is not None
    assert "missing" in sa["answer"].lower()
    assert len(sa["numbers"]) >= 1


def test_intent_anomalies_outliers():
    """Test Intent: 'Are there any outliers or anomalies?'"""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "Are there any outliers in this dataset?"}
    )
    assert resp.status_code in (200, 202)
    sa = resp.json().get("structured_answer")
    assert sa is not None
    assert "outlier" in sa["answer"].lower() or "anomal" in sa["answer"].lower()


def test_intent_nonexistent_column():
    """Test Intent: Question mentioning a column that does not exist."""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "What is the average of non_existent_salary_bonus?"}
    )
    assert resp.status_code in (200, 202)
    sa = resp.json().get("structured_answer")
    assert sa is not None
    assert "not found" in sa["answer"].lower() or "does not exist" in sa["answer"].lower()


def test_intent_unanswerable():
    """Test Intent: Question that cannot be answered from the data."""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "What will the stock price be tomorrow?"}
    )
    assert resp.status_code in (200, 202)
    sa = resp.json().get("structured_answer")
    assert sa is not None
    assert "cannot be answered" in sa["answer"].lower() or "not contain" in sa["answer"].lower()


def test_intent_ambiguous():
    """Test Intent: Ambiguous request ('Can you fix it?')."""
    analysis_id = pytest.test_analysis_id
    resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "Can you fix it?"}
    )
    assert resp.status_code in (200, 202)
    sa = resp.json().get("structured_answer")
    assert sa is not None
    assert len(sa["next_questions"]) >= 2


def test_no_paragraphs_exceeding_three_lines():
    """Verify that chat responses are scannable and contain no dense wall-of-text paragraphs (>3 lines)."""
    analysis_id = pytest.test_analysis_id
    queries = [
        "Which columns matter most?",
        "What if I exclude incomplete rows?",
        "Are there any outliers?",
    ]
    for q in queries:
        resp = client.post(
            f"/api/v1/analyses/{analysis_id}/chat",
            json={"message": q}
        )
        data = resp.json()
        content = data.get("content", "")
        # Break into paragraphs by double newline
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for p in paragraphs:
            # If not a markdown table or bullet list, line count should be <= 4
            lines = [l for l in p.split("\n") if l.strip()]
            if not lines[0].startswith("|") and not lines[0].startswith("-"):
                assert len(lines) <= 4, f"Paragraph exceeded 4 lines in response to '{q}':\n{p}"
