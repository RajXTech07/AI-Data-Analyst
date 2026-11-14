import sys
from pathlib import Path
import pytest

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import init_db

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

client = TestClient(app)

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_readyz():
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["storage"] == "ok"

import uuid

def test_auth_flow():
    # 1. Register a test user
    email = f"researcher_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!"}
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == email
    assert "id" in user_data

    # 2. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"}
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 3. Get /me
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

def test_upload_and_profile_flow():
    # 1. Read test CSV
    csv_path = Path(__file__).resolve().parent.parent.parent / "datasets" / "student_performance.csv"
    assert csv_path.exists(), f"Sample CSV not found at {csv_path}"

    with open(csv_path, "rb") as f:
        file_bytes = f.read()

    # 2. Upload CSV
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("student_performance.csv", file_bytes, "text/csv")}
    )
    assert response.status_code == 201, f"Upload failed: {response.text}"
    dataset_data = response.json()
    dataset_id = dataset_data["id"]
    assert dataset_data["n_rows"] == 20
    assert dataset_data["n_cols"] == 7
    assert dataset_data["filename"] == "student_performance.csv"

    # 3. Get profile
    profile_resp = client.get(f"/api/v1/datasets/{dataset_id}/profile")
    assert profile_resp.status_code == 200
    profile = profile_resp.json()
    assert profile["n_rows"] == 20
    assert profile["n_cols"] == 7
    assert profile["duplicate_rows"] == 0
    assert len(profile["columns"]) == 7

    # Verify column profiling
    col_map = {c["name"]: c for c in profile["columns"]}
    assert col_map["final_mark"]["dtype"] == "numeric"
    assert "mean" in col_map["final_mark"]["stats"]
    assert col_map["department"]["dtype"] == "categorical"
    assert len(col_map["department"]["top_values"]) > 0

    # 4. Get preview
    preview_resp = client.get(f"/api/v1/datasets/{dataset_id}/preview?rows=5")
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert len(preview["rows"]) == 5
    assert "attendance" in preview["columns"]

    # 5. List datasets
    list_resp = client.get("/api/v1/datasets")
    assert list_resp.status_code == 200
    assert any(d["id"] == dataset_id for d in list_resp.json())

    # 6. Delete dataset
    del_resp = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert del_resp.status_code == 204

    # 7. Verify 404 after deletion
    get_after_del = client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_after_del.status_code == 404

def test_invalid_upload():
    # Non-CSV rejection
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("report.pdf", b"%PDF-1.4...", "application/pdf")}
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"
