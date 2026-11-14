import asyncio
from pathlib import Path
import sys
import uuid
import pytest

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.agent.llm import MockLLMClient, get_llm_client
from app.agent.orchestrator import run_analysis
from app.agent.planner import make_plan
from app.agent.validator import validator
from app.db.models.analysis import Analysis
from app.db.models.dataset import Dataset
from app.db.session import SessionLocal, init_db
from app.main import app
from app.schemas.dataset import DatasetProfile
from app.schemas.finding import FindingDraft, StatEvidence
from app.services.datasets import dataset_service

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

client = TestClient(app)

@pytest.fixture
def test_dataset():
    db = SessionLocal()
    try:
        csv_path = Path(__file__).resolve().parent.parent.parent / "datasets" / "student_performance.csv"
        with open(csv_path, "rb") as f:
            content = f.read()

        demo_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        dataset = dataset_service.upload_dataset(
            db=db,
            user_id=demo_user_id,
            filename=f"student_test_{uuid.uuid4().hex[:6]}.csv",
            content=content
        )
        return dataset.id
    finally:
        db.close()

def test_planner_generation(test_dataset):
    db = SessionLocal()
    try:
        dataset = db.get(Dataset, test_dataset)
        profile = DatasetProfile.model_validate(dataset.profile)
        llm = MockLLMClient()

        plan = make_plan(profile, question="Compare departments", llm=llm)
        assert len(plan.steps) >= 3
        assert any("statistics" in s.suggested_tool or "group" in s.suggested_tool for s in plan.steps)
    finally:
        db.close()

def test_grounding_validator():
    exec_id = uuid.uuid4()
    tool_results = {
        exec_id: {
            "data": {
                "groups": [
                    {"group": "Computer Science", "metric_value": 85.5, "count": 10},
                    {"group": "Mathematics", "metric_value": 73.2, "count": 10}
                ]
            }
        }
    }

    # 1. Finding with grounded numbers
    grounded_draft = FindingDraft(
        title="Computer Science marks average 85.5",
        observation="Computer Science had average marks of 85.5 with 10 students.",
        interpretation="Higher marks in Computer Science.",
        limitations="Small sample.",
        hypothesis_status="supported",
        evidence_execution_ids=[exec_id]
    )
    is_grounded, warnings = validator.verify_grounding(grounded_draft, tool_results)
    assert is_grounded is True
    assert len(warnings) == 0

    # 2. Finding with hallucinated / unverified number (e.g. 99.9)
    hallucinated_draft = FindingDraft(
        title="Dramatic surge to 99.9 marks",
        observation="Computer Science students scored 99.9 marks on average.",
        interpretation="Unfounded claim.",
        limitations="None.",
        hypothesis_status="supported",
        evidence_execution_ids=[exec_id]
    )
    is_grounded2, warnings2 = validator.verify_grounding(hallucinated_draft, tool_results)
    assert is_grounded2 is False
    assert any("Unverified numbers" in w for w in warnings2)

def test_confidence_computation():
    # Significant test with large sample -> High confidence
    high_stat = StatEvidence(test="welch_t_test", p_value=0.001, n=45)
    conf_high = validator.compute_confidence("supported", high_stat, warnings=[])
    assert conf_high == "high"

    # Moderate p-value -> Medium confidence
    med_stat = StatEvidence(test="welch_t_test", p_value=0.03, n=20)
    conf_med = validator.compute_confidence("supported", med_stat, warnings=[])
    assert conf_med == "medium"

    # Inconclusive / non-significant -> Low confidence
    low_stat = StatEvidence(test="welch_t_test", p_value=0.15, n=20)
    conf_low = validator.compute_confidence("inconclusive", low_stat, warnings=[])
    assert conf_low == "low"

def test_end_to_end_orchestrator(test_dataset):
    db = SessionLocal()
    try:
        # 1. Create an analysis record
        analysis_id = uuid.uuid4()
        demo_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        analysis = Analysis(
            id=analysis_id,
            dataset_id=test_dataset,
            user_id=demo_user_id,
            question="Why are marks different across departments?",
            status="queued"
        )
        db.add(analysis)
        db.commit()

        # 2. Run the orchestrator
        asyncio.run(run_analysis(analysis_id, force_mock_llm=True))

        # 3. Verify Database state
        db.refresh(analysis)
        assert analysis.status == "completed"
        assert analysis.plan is not None
        assert len(analysis.plan["steps"]) >= 3

        # 4. Verify tool executions were stored
        assert len(analysis.tool_executions) >= 3
        for e in analysis.tool_executions:
            assert e.ok is True
            assert e.result is not None
            assert e.source == "agent"

        # 5. Verify findings were generated and grounded
        assert len(analysis.findings) >= 1
        for f in analysis.findings:
            assert f.title != ""
            assert f.observation != ""
            assert f.confidence in ["low", "medium", "high"]
            assert len(f.evidence_links) >= 1

    finally:
        db.close()

def test_api_chat_and_messages(test_dataset):
    # 1. Start analysis via API
    analyze_resp = client.post(
        f"/api/v1/datasets/{test_dataset}/analyze",
        json={"question": "Show average marks by department"}
    )
    assert analyze_resp.status_code == 202
    analysis_id = analyze_resp.json()["id"]

    # 2. Send follow-up chat message
    chat_resp = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "Show average marks by department"}
    )
    assert chat_resp.status_code == 202
    chat_data = chat_resp.json()
    assert "Calculated result" in chat_data["content"] or "Executed" in chat_data["content"]

    # 3. Fetch chat history
    history_resp = client.get(f"/api/v1/analyses/{analysis_id}/messages")
    assert history_resp.status_code == 200
    msgs = history_resp.json()
    assert len(msgs) >= 2
    assert any(m["role"] == "user" for m in msgs)
    assert any(m["role"] == "assistant" for m in msgs)
