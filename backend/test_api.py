import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import config
from main import app
from config import get_config_diagnostic

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /api/health returns 200 and expected status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "synaptra-backend"


def test_planner_rejects_empty_task():
    """Verify POST /api/planner rejects empty or whitespace-only task."""
    # Test completely empty string
    res1 = client.post("/api/planner", json={"task": ""})
    assert res1.status_code == 422, f"Expected 422 for empty task, got {res1.status_code}"

    # Test whitespace-only string
    res2 = client.post("/api/planner", json={"task": "   "})
    assert res2.status_code == 422, f"Expected 422 for whitespace task, got {res2.status_code}"

    # Test missing task field
    res3 = client.post("/api/planner", json={})
    assert res3.status_code == 422, f"Expected 422 for missing task field, got {res3.status_code}"


def test_planner_missing_credentials_produces_clear_error(monkeypatch, tmp_path):
    """Verify that missing credentials produce a clear 500 configuration error."""
    # Point ENV_FILE to empty temporary file and blank out env vars
    empty_env = tmp_path / ".env"
    empty_env.write_text("")
    monkeypatch.setattr(config, "ENV_FILE", empty_env)
    monkeypatch.setenv("LYZR_API_KEY", "")
    monkeypatch.setenv("LYZR_PLANNER_AGENT_ID", "")

    response = client.post("/api/planner", json={"task": "Create workflow plan for data processing"})
    assert response.status_code == 500
    data = response.json()
    assert "Missing required configuration" in data["detail"]
    assert "LYZR_API_KEY" in data["detail"]
    assert "LYZR_PLANNER_AGENT_ID" in data["detail"]


def test_planner_live_execution_if_configured():
    """
    If valid non-placeholder credentials are provided in root .env,
    sends a real request to the configured Lyzr Planner agent and verifies output.
    """
    diag = get_config_diagnostic()
    if not diag["all_configured"]:
        pytest.skip("Lyzr credentials not configured with valid real keys in root .env - skipping live agent test.")

    # Live test execution only when genuinely configured
    response = client.post(
        "/api/planner",
        json={"task": "Provide a brief 3-step high level workflow plan for an AI pipeline."},
    )

    assert response.status_code == 200, f"Live call failed: {response.status_code} - {response.text}"
    data = response.json()
    assert data["status"] == "success"
    assert "response" in data
    assert len(data["response"]) > 0
