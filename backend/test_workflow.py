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
from services.lyzr_client import LyzrClientError
from services.qdrant_service import memory_service, QdrantUnavailableError

client = TestClient(app)


@pytest.fixture(autouse=True)
def restore_environment():
    """Ensure environment variables and config settings are preserved across tests."""
    orig_env = dict(os.environ)
    orig_file = config.ENV_FILE
    yield
    os.environ.clear()
    os.environ.update(orig_env)
    config.ENV_FILE = orig_file


# ============================================================================
# Unit Tests: Input Validation
# ============================================================================

def test_workflow_rejects_empty_task():
    """Verify POST /api/workflows rejects empty or whitespace-only task."""
    res1 = client.post("/api/workflows", json={"task": ""})
    assert res1.status_code == 422
    assert "task" in res1.text.lower()

    res2 = client.post("/api/workflows", json={"task": "   "})
    assert res2.status_code == 422

    res3 = client.post("/api/workflows", json={})
    assert res3.status_code == 422


def test_workflow_rejects_empty_workspace_id():
    """Verify POST /api/workflows rejects empty workspace_id."""
    res = client.post("/api/workflows", json={"task": "Audit contract", "workspace_id": ""})
    assert res.status_code == 422
    assert "workspace_id" in res.text.lower()


# ============================================================================
# Unit Tests: Credential Validation & Diagnostics
# ============================================================================

def test_workflow_status_endpoint():
    """Verify GET /api/workflows/status returns workflow diagnostic structure."""
    res = client.get("/api/workflows/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "diagnostic" in data
    assert "all_workflow_agents_configured" in data["diagnostic"]


def test_workflow_missing_credentials_returns_500(monkeypatch, tmp_path):
    """Verify that missing credentials produce a clear 500 error naming missing variable."""
    fake_env = tmp_path / ".env"
    fake_env.write_text("LYZR_API_KEY=valid_key\nLYZR_PLANNER_AGENT_ID=planner_id\n")
    monkeypatch.setattr(config, "ENV_FILE", fake_env)
    monkeypatch.setenv("LYZR_API_KEY", "valid_key")
    monkeypatch.setenv("LYZR_PLANNER_AGENT_ID", "planner_id")
    monkeypatch.setenv("LYZR_EXECUTOR_AGENT_ID", "")  # Missing executor
    monkeypatch.setenv("LYZR_MEMORY_AGENT_ID", "")
    monkeypatch.setenv("LYZR_REVIEWER_AGENT_ID", "")

    res = client.post("/api/workflows", json={"task": "Audit procurement document"})
    assert res.status_code == 500
    detail = res.json()["detail"]
    assert "Missing required workflow configuration" in detail
    assert "LYZR_EXECUTOR_AGENT_ID" in detail


# ============================================================================
# Mocked Orchestration Tests: End-to-End Success & Failure Handling
# ============================================================================

@pytest.fixture
def mock_workflow_env(monkeypatch, tmp_path):
    """Sets valid mock environment variables for all 4 agents."""
    fake_env = tmp_path / ".env"
    fake_env.write_text(
        "LYZR_API_KEY=mock_lyzr_api_key_valid\n"
        "LYZR_PLANNER_AGENT_ID=mock_planner_agent_id\n"
        "LYZR_EXECUTOR_AGENT_ID=mock_executor_agent_id\n"
        "LYZR_MEMORY_AGENT_ID=mock_memory_agent_id\n"
        "LYZR_REVIEWER_AGENT_ID=mock_reviewer_agent_id\n"
    )
    monkeypatch.setattr(config, "ENV_FILE", fake_env)
    monkeypatch.setenv("LYZR_API_KEY", "mock_lyzr_api_key_valid")
    monkeypatch.setenv("LYZR_PLANNER_AGENT_ID", "mock_planner_agent_id")
    monkeypatch.setenv("LYZR_EXECUTOR_AGENT_ID", "mock_executor_agent_id")
    monkeypatch.setenv("LYZR_MEMORY_AGENT_ID", "mock_memory_agent_id")
    monkeypatch.setenv("LYZR_REVIEWER_AGENT_ID", "mock_reviewer_agent_id")
    monkeypatch.setenv("GEMINI_API_KEY", "")


def test_workflow_successful_execution_mocked(mock_workflow_env, monkeypatch):
    """
    Simulates successful execution across all 4 Lyzr agents:
    Memory -> Planner -> Executor -> Reviewer -> Qdrant Storage.
    Verifies:
    1. POST /api/workflows returns 200 with COMPLETED status and 6-step trace.
    2. GET /api/workflows/{task_id} returns matching workflow record.
    3. GET /api/workflows/{task_id}/events returns chronological event sequence.
    """
    call_log = []

    async def mock_execute_lyzr_agent(agent_id, message, **kwargs):
        call_log.append({"agent_id": agent_id, "message": message})
        if agent_id == "mock_memory_agent_id":
            return {
                "message": message,
                "response": "Synthesized Memory: Historical budget cap is $50,000.",
                "agent_id": agent_id,
                "session_id": "sess_123",
                "retry_count": 0,
                "raw": {},
            }
        elif agent_id == "mock_planner_agent_id":
            return {
                "message": message,
                "response": "1. Verify vendor credentials. 2. Cross-reference invoice line items.",
                "agent_id": agent_id,
                "session_id": "sess_123",
                "retry_count": 0,
                "raw": {},
            }
        elif agent_id == "mock_executor_agent_id":
            return {
                "message": message,
                "response": "Execution results: Vendor is certified; line items total $42,500.",
                "agent_id": agent_id,
                "session_id": "sess_123",
                "retry_count": 0,
                "raw": {},
            }
        elif agent_id == "mock_reviewer_agent_id":
            return {
                "message": message,
                "response": "Reviewer verdict: All subtasks completed satisfactorily without anomalies.",
                "agent_id": agent_id,
                "session_id": "sess_123",
                "retry_count": 0,
                "raw": {},
            }
        raise ValueError(f"Unexpected agent_id: {agent_id}")

    # Mock memory service
    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_lyzr_agent)
    monkeypatch.setattr(
        memory_service,
        "search_memories",
        lambda query, workspace_id, limit=5: [
            {"memory_id": "mem_1", "content": "Prior procurement guidelines", "score": 0.88}
        ],
    )
    saved_items = []
    monkeypatch.setattr(
        memory_service,
        "insert_memory",
        lambda **kwargs: saved_items.append(kwargs) or {"memory_id": "new_saved_mem_99"},
    )

    # 1. Test POST /api/workflows
    res = client.post(
        "/api/workflows",
        json={"task": "Audit invoice INV-2026-091", "workspace_id": "ws_audit_alpha"},
    )
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["task"] == "Audit invoice INV-2026-091"
    assert data["workspace_id"] == "ws_audit_alpha"
    assert "Reviewer verdict:" in data["final_response"]
    assert data["total_duration_ms"] >= 0
    assigned_id = data["task_id"]
    assert assigned_id is not None

    # Verify execution trace contains all 6 key steps
    trace = data["execution_trace"]
    assert len(trace) == 6
    step_names = [s["step_name"] for s in trace]
    assert step_names == [
        "memory_retrieval",
        "memory_synthesis",
        "plan_generation",
        "subtask_execution",
        "review_and_synthesis",
        "memory_storage",
    ]

    for step in trace:
        assert step["status"] == "SUCCESS"
        assert "started_at" in step
        assert "completed_at" in step
        assert step["duration_ms"] >= 0

    # Verify summary was stored into Qdrant
    assert len(saved_items) == 1
    assert saved_items[0]["workspace_id"] == "ws_audit_alpha"
    assert saved_items[0]["source_agent"] == "reviewer_agent"

    # 2. Test GET /api/workflows/{task_id}
    detail_res = client.get(f"/api/workflows/{assigned_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["task_id"] == assigned_id
    assert detail_data["status"] == "COMPLETED"
    assert detail_data["final_response"] == data["final_response"]
    assert detail_data["events_count"] > 0

    # 3. Test GET /api/workflows/{task_id}/events
    events_res = client.get(f"/api/workflows/{assigned_id}/events")
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert events_data["task_id"] == assigned_id
    assert events_data["count"] > 0
    event_types = [e["event_type"] for e in events_data["events"]]
    assert "workflow_started" in event_types
    assert "workflow_completed" in event_types
    assert event_types[0] == "workflow_started"
    assert event_types[-1] == "workflow_completed"


def test_workflow_planner_failure(mock_workflow_env, monkeypatch):
    """
    Verify that when Planner Agent fails (e.g. 502 or upstream timeout),
    the workflow marks the planner step as FAILED, overall status as FAILED,
    does NOT call Executor or Reviewer, and returns HTTP 502 with truthful error.
    """
    call_log = []

    async def mock_execute_planner_fail(agent_id, message, **kwargs):
        call_log.append(agent_id)
        if agent_id == "mock_memory_agent_id":
            return {"response": "Memory context", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_planner_agent_id":
            raise LyzrClientError("Planner agent internal upstream failure", status_code=502)
        return {"response": "Should not reach", "agent_id": agent_id, "session_id": "s1"}

    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_planner_fail)
    monkeypatch.setattr(memory_service, "search_memories", lambda *args, **kwargs: [])

    res = client.post("/api/workflows", json={"task": "Plan audit breakdown"})
    assert res.status_code == 502
    err_body = res.json()["detail"]
    assert err_body["status"] == "FAILED"
    assert "Planner Agent failed" in err_body["message"]

    trace = err_body["execution_trace"]
    planner_steps = [s for s in trace if s["step_name"] == "plan_generation"]
    assert len(planner_steps) == 1
    assert planner_steps[0]["status"] == "FAILED"
    assert "upstream failure" in planner_steps[0]["error"]

    # Executor and Reviewer must NOT have been called
    assert "mock_executor_agent_id" not in call_log
    assert "mock_reviewer_agent_id" not in call_log


def test_workflow_executor_failure(mock_workflow_env, monkeypatch):
    """
    Verify that when Executor Agent fails, the orchestrator:
    1. Marks the executor step as FAILED.
    2. Marks the entire workflow as FAILED.
    3. Does NOT claim success or call Reviewer.
    4. Returns HTTP 502 with error details and execution trace.
    """
    call_log = []

    async def mock_execute_executor_fail(agent_id, message, **kwargs):
        call_log.append(agent_id)
        if agent_id == "mock_memory_agent_id":
            return {"response": "Memory context", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_planner_agent_id":
            return {"response": "1. Task 1. 2. Task 2.", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_executor_agent_id":
            raise LyzrClientError("Upstream executor timeout after 90s", status_code=504)
        return {"response": "Review", "agent_id": agent_id, "session_id": "s1"}

    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_executor_fail)
    monkeypatch.setattr(memory_service, "search_memories", lambda *args, **kwargs: [])

    res = client.post("/api/workflows", json={"task": "Execute complex audit task"})
    assert res.status_code == 502
    err_body = res.json()["detail"]
    assert err_body["status"] == "FAILED"
    assert "Executor Agent failed" in err_body["message"]

    trace = err_body["execution_trace"]
    executor_steps = [s for s in trace if s["step_name"] == "subtask_execution"]
    assert len(executor_steps) == 1
    assert executor_steps[0]["status"] == "FAILED"
    assert "timeout" in executor_steps[0]["error"].lower()

    # Reviewer must NOT have been called
    assert "mock_reviewer_agent_id" not in call_log


def test_workflow_reviewer_failure(mock_workflow_env, monkeypatch):
    """
    Verify that when Reviewer Agent fails, the orchestrator:
    1. Marks the reviewer step as FAILED.
    2. Marks the workflow as FAILED.
    3. Does not persist misleading summary.
    4. Returns HTTP 502 with error details.
    """
    saved_items = []

    async def mock_execute_reviewer_fail(agent_id, message, **kwargs):
        if agent_id == "mock_memory_agent_id":
            return {"response": "Memory context", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_planner_agent_id":
            return {"response": "1. Plan item", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_executor_agent_id":
            return {"response": "Execution output", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_reviewer_agent_id":
            raise LyzrClientError("Reviewer agent hallucination check failed", status_code=500)
        return {"response": "ok", "agent_id": agent_id, "session_id": "s1"}

    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_reviewer_fail)
    monkeypatch.setattr(memory_service, "search_memories", lambda *args, **kwargs: [])
    monkeypatch.setattr(memory_service, "insert_memory", lambda **kwargs: saved_items.append(kwargs))

    res = client.post("/api/workflows", json={"task": "Audit contract completeness"})
    assert res.status_code == 502
    err_body = res.json()["detail"]
    assert err_body["status"] == "FAILED"
    assert "Reviewer Agent failed" in err_body["message"]

    trace = err_body["execution_trace"]
    review_steps = [s for s in trace if s["step_name"] == "review_and_synthesis"]
    assert len(review_steps) == 1
    assert review_steps[0]["status"] == "FAILED"

    # Memory storage must NOT have occurred
    assert len(saved_items) == 0


def test_workflow_executor_self_healing_with_gemini(mock_workflow_env, monkeypatch):
    """
    Verify that when Executor Agent fails via Lyzr (e.g. 402 Credits exhausted),
    and GEMINI_API_KEY is configured, the orchestrator:
    1. Catches LyzrClientError.
    2. Auto-rectifies via Google Gemini AI Studio.
    3. Emits agent_rectification event.
    4. Marks the executor step as SUCCESS with provider='gemini (auto-rectified)' and self_healed=True.
    5. Completes the workflow successfully without crashing.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")

    async def mock_execute_lyzr(agent_id, message, **kwargs):
        if agent_id == "mock_memory_agent_id":
            return {"response": "Memory context", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_planner_agent_id":
            return {"response": "1. Task 1", "agent_id": agent_id, "session_id": "s1"}
        elif agent_id == "mock_executor_agent_id":
            raise LyzrClientError('Lyzr API error (HTTP 402): {"detail":"Credits exhausted"}', status_code=502)
        elif agent_id == "mock_reviewer_agent_id":
            return {"response": "Review completed", "agent_id": agent_id, "session_id": "s1"}
        return {"response": "ok", "agent_id": agent_id, "session_id": "s1"}

    async def mock_execute_gemini(agent_role, **kwargs):
        return f"Self-healed output for {agent_role}"

    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_lyzr)
    monkeypatch.setattr("services.orchestrator.execute_gemini_agent", mock_execute_gemini)
    monkeypatch.setattr(memory_service, "search_memories", lambda *args, **kwargs: [])
    monkeypatch.setattr(memory_service, "insert_memory", lambda **kwargs: {"memory_id": "m1"})

    res = client.post("/api/workflows", json={"task": "Audit procurement contracts"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"

    trace = data["execution_trace"]
    exec_steps = [s for s in trace if s["step_name"] == "subtask_execution"]
    assert len(exec_steps) == 1
    assert exec_steps[0]["status"] == "SUCCESS"
    assert exec_steps[0]["self_healed"] is True
    assert "gemini" in exec_steps[0]["provider"].lower()



def test_workflow_qdrant_retrieval_failure_gracefully_handled(mock_workflow_env, monkeypatch):
    """
    Verify that if Qdrant vector memory is temporarily unreachable during search,
    the workflow marks the memory_retrieval step as WARNING with the error,
    proceeds gracefully with cold-start context, and completes the agent chain.
    """
    def mock_broken_search(*args, **kwargs):
        raise QdrantUnavailableError("Connection to Qdrant vector database timed out.")

    async def mock_execute_ok(agent_id, message, **kwargs):
        return {"response": f"Output from {agent_id}", "agent_id": agent_id, "session_id": "s1"}

    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_ok)
    monkeypatch.setattr(memory_service, "search_memories", mock_broken_search)
    monkeypatch.setattr(memory_service, "insert_memory", lambda **kwargs: {"memory_id": "stored_1"})

    res = client.post("/api/workflows", json={"task": "Audit with offline Qdrant retrieval"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"

    # Step 1 should have WARNING status with error recorded
    retrieval_step = data["execution_trace"][0]
    assert retrieval_step["step_name"] == "memory_retrieval"
    assert retrieval_step["status"] == "WARNING"
    assert "unreachable" in retrieval_step["error"].lower() or "timed out" in retrieval_step["error"].lower()


def test_workflow_qdrant_storage_failure_gracefully_handled(mock_workflow_env, monkeypatch):
    """
    Verify that if Qdrant vector memory fails to store the final summary,
    the memory_storage step is marked as WARNING, and the final response is still delivered.
    """
    def mock_broken_insert(**kwargs):
        raise QdrantUnavailableError("Qdrant disk storage full.")

    async def mock_execute_ok(agent_id, message, **kwargs):
        return {"response": f"Valid output from {agent_id}", "agent_id": agent_id, "session_id": "s1"}

    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_ok)
    monkeypatch.setattr(memory_service, "search_memories", lambda *args, **kwargs: [])
    monkeypatch.setattr(memory_service, "insert_memory", mock_broken_insert)

    res = client.post("/api/workflows", json={"task": "Audit invoice storage test"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"

    storage_step = data["execution_trace"][-1]
    assert storage_step["step_name"] == "memory_storage"
    assert storage_step["status"] == "WARNING"
    assert "disk storage full" in storage_step["error"].lower()


def test_workflow_workspace_isolation(mock_workflow_env, monkeypatch):
    """
    Verify that Qdrant search and insertion strictly enforce tenant workspace_id isolation.
    """
    captured_workspaces = []

    def mock_search_ws(query, workspace_id, limit=5):
        captured_workspaces.append(("search", workspace_id))
        return []

    def mock_insert_ws(**kwargs):
        captured_workspaces.append(("insert", kwargs.get("workspace_id")))
        return {"memory_id": "mem_tenant_isolated"}

    async def mock_execute_ok(agent_id, message, **kwargs):
        return {"response": f"Output from {agent_id}", "agent_id": agent_id, "session_id": "s1"}

    monkeypatch.setattr("services.orchestrator.execute_lyzr_agent", mock_execute_ok)
    monkeypatch.setattr(memory_service, "search_memories", mock_search_ws)
    monkeypatch.setattr(memory_service, "insert_memory", mock_insert_ws)

    res = client.post("/api/workflows", json={"task": "Tenant test", "workspace_id": "gov_dept_finance"})
    assert res.status_code == 200
    assert ("search", "gov_dept_finance") in captured_workspaces
    assert ("insert", "gov_dept_finance") in captured_workspaces


def test_workflow_not_found_endpoints():
    """Verify GET /api/workflows/{task_id} and /events return 404 for non-existent IDs."""
    res1 = client.get("/api/workflows/non_existent_task_12345")
    assert res1.status_code == 404
    assert "not found" in res1.text.lower()

    res2 = client.get("/api/workflows/non_existent_task_12345/events")
    assert res2.status_code == 404
    assert "not found" in res2.text.lower()


# ============================================================================
# Live Integration Test (Executed when real credentials exist in root .env)
# ============================================================================

def test_workflow_live_execution_if_configured():
    """
    If real non-placeholder credentials are configured in root .env for all agents,
    runs a real live test of the entire multi-agent workflow against live Lyzr agents.
    """
    diag = config.get_config_diagnostic()
    if not diag.get("all_workflow_agents_configured"):
        pytest.skip("Not all Lyzr agent IDs configured in root .env - skipping live agent test.")

    res = client.post(
        "/api/workflows",
        json={
            "task": "Provide a 1-sentence verification checklist for high-risk public procurement contracts.",
            "workspace_id": "test_live_ws",
            "timeout_seconds": 60.0,
        },
    )

    assert res.status_code == 200, f"Live workflow failed: {res.text}"
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["final_response"] is not None
    assert len(data["final_response"]) > 0
    assert len(data["execution_trace"]) == 6

    # Test GET endpoints on real live task
    live_id = data["task_id"]
    get_res = client.get(f"/api/workflows/{live_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "COMPLETED"

    events_res = client.get(f"/api/workflows/{live_id}/events")
    assert events_res.status_code == 200
    assert events_res.json()["count"] > 0
