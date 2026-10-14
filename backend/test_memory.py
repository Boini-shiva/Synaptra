import sys
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from services.qdrant_service import memory_service, QdrantUnavailableError

client = TestClient(app)


# ============================================================================
# Unit Tests: Input Validation & Error Handling
# ============================================================================

def test_memory_rejects_empty_content():
    """Verify POST /api/memory rejects empty or whitespace-only content."""
    res = client.post("/api/memory", json={"content": "", "workspace_id": "ws_test"})
    assert res.status_code == 422
    assert "content" in res.text

    res_ws = client.post("/api/memory", json={"content": "   ", "workspace_id": "ws_test"})
    assert res_ws.status_code == 422


def test_memory_rejects_empty_workspace_id():
    """Verify POST /api/memory rejects empty or whitespace-only workspace_id."""
    res = client.post("/api/memory", json={"content": "Valid content", "workspace_id": ""})
    assert res.status_code == 422
    assert "workspace_id" in res.text


def test_search_rejects_empty_query():
    """Verify GET /api/memory/search rejects empty or missing query string."""
    res = client.get("/api/memory/search?q=&workspace_id=ws_test")
    assert res.status_code == 422

    res_missing = client.get("/api/memory/search?workspace_id=ws_test")
    assert res_missing.status_code == 422


def test_search_rejects_empty_workspace_id():
    """Verify GET /api/memory/search rejects empty or missing workspace_id."""
    res = client.get("/api/memory/search?q=agents&workspace_id=")
    assert res.status_code == 422

    res_missing = client.get("/api/memory/search?q=agents")
    assert res_missing.status_code == 422


def test_list_rejects_empty_workspace_id():
    """Verify GET /api/memory rejects empty or missing workspace_id."""
    res = client.get("/api/memory?workspace_id=")
    assert res.status_code == 422

    res_missing = client.get("/api/memory")
    assert res_missing.status_code == 422


def test_qdrant_unavailable_returns_503(monkeypatch):
    """
    Verify that when Qdrant is unreachable, the API returns HTTP 503
    with a clear, informative message without crashing the server.
    """
    def mock_check_health():
        raise QdrantUnavailableError("Qdrant service simulated unreachable.")

    monkeypatch.setattr(memory_service, "check_health", mock_check_health)
    res = client.get("/api/memory/health")
    assert res.status_code == 503
    assert "unreachable" in res.json()["detail"].lower()


# ============================================================================
# Live Integration Tests against running local Qdrant container
# ============================================================================

def test_live_qdrant_health():
    """Verify that the local Qdrant container is reachable and reporting health."""
    res = client.get("/api/memory/health")
    assert res.status_code == 200, f"Qdrant health check failed: {res.text}"
    data = res.json()
    assert data["status"] == "ok"
    assert data["vector_dim"] == 384
    assert data["collection_exists"] is True
    assert "synaptra_memory" in data["collection"]


def test_live_memory_lifecycle_with_semantic_search_and_workspace_isolation():
    """
    Full live integration test:
    1. Insert memory into workspace A.
    2. Insert distinct memory into workspace B.
    3. Semantically search in workspace A -> finds memory A with similarity score.
    4. Semantically search in workspace B -> verifies workspace A memory is isolated and omitted.
    5. List memories in workspace A -> contains memory A.
    6. Attempt deletion from wrong workspace B -> returns 404 (isolation enforced).
    7. Delete memory with matching workspace A -> returns 200.
    8. Verify deleted memory is gone.
    """
    ws_a = f"ws_alpha_{uuid.uuid4().hex[:6]}"
    ws_b = f"ws_beta_{uuid.uuid4().hex[:6]}"

    content_a = "SYNAPTRA is an autonomous multi-agent platform for collaborative AI workflows and orchestration."
    content_b = "Independent financial document analysis module for public auditing."

    # 1. Insert memory into workspace A
    res_a = client.post(
        "/api/memory",
        json={
            "content": content_a,
            "memory_type": "architecture",
            "source_agent": "planner",
            "workspace_id": ws_a,
            "visibility": "team",
        },
    )
    assert res_a.status_code == 201, f"Failed to insert memory A: {res_a.text}"
    mem_a = res_a.json()
    id_a = mem_a["memory_id"]
    assert mem_a["content"] == content_a
    assert mem_a["workspace_id"] == ws_a
    assert mem_a["source_agent"] == "planner"
    assert "created_at" in mem_a

    # 2. Insert memory into workspace B
    res_b = client.post(
        "/api/memory",
        json={
            "content": content_b,
            "memory_type": "audit",
            "source_agent": "auditor",
            "workspace_id": ws_b,
        },
    )
    assert res_b.status_code == 201
    mem_b = res_b.json()
    id_b = mem_b["memory_id"]

    try:
        # 3. Semantic search in workspace A
        search_a = client.get(
            f"/api/memory/search?q=multi-agent+collaborative+platform&workspace_id={ws_a}"
        )
        assert search_a.status_code == 200
        data_a = search_a.json()
        assert data_a["status"] == "success"
        assert data_a["count"] >= 1
        top_match = data_a["results"][0]
        assert top_match["memory_id"] == id_a
        assert top_match["score"] > 0.5  # High cosine similarity

        # 4. Search in workspace B for same query -> memory A MUST NOT appear
        search_b = client.get(
            f"/api/memory/search?q=multi-agent+collaborative+platform&workspace_id={ws_b}"
        )
        assert search_b.status_code == 200
        data_b = search_b.json()
        ids_in_b = [r["memory_id"] for r in data_b["results"]]
        assert id_a not in ids_in_b, "Workspace isolation breach! Memory A found in Workspace B search."

        # 5. List memories in workspace A
        list_res = client.get(f"/api/memory?workspace_id={ws_a}")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["count"] >= 1
        list_ids = [m["memory_id"] for m in list_data["memories"]]
        assert id_a in list_ids
        assert id_b not in list_ids

        # 6. Delete attempt from wrong workspace must fail with 404
        del_cross = client.delete(f"/api/memory/{id_a}?workspace_id={ws_b}")
        assert del_cross.status_code == 404

        # 7. Delete with proper workspace
        del_valid = client.delete(f"/api/memory/{id_a}?workspace_id={ws_a}")
        assert del_valid.status_code == 200
        assert del_valid.json()["deleted_id"] == id_a

        # 8. Verify it is no longer returned
        search_after = client.get(
            f"/api/memory/search?q=multi-agent+collaborative+platform&workspace_id={ws_a}"
        )
        assert search_after.status_code == 200
        ids_after = [r["memory_id"] for r in search_after.json()["results"]]
        assert id_a not in ids_after

    finally:
        # Cleanup memory B
        try:
            client.delete(f"/api/memory/{id_b}?workspace_id={ws_b}")
        except Exception:
            pass
