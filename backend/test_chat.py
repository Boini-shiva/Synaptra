import pytest
from fastapi.testclient import TestClient
from main import app
from services.gemini_client import GeminiClientError

client = TestClient(app)


def test_chat_rejects_empty_message():
    """Verify POST /api/chat rejects empty query with 422."""
    res = client.post("/api/chat", json={"message": "   "})
    assert res.status_code == 422


def test_chat_suggestions_endpoint():
    """Verify GET /api/chat/suggestions returns curated prompt ideas."""
    res = client.get("/api/chat/suggestions")
    assert res.status_code == 200
    data = res.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 3


def test_chat_execution_mocked(monkeypatch):
    """Verify POST /api/chat calls Gemini and formats citations and response."""
    async def mock_generate_chat(message, history=None, context=None, **kwargs):
        return {
            "reply": f"SYNAPTRA audit analysis for: {message}",
            "model": "gemini-flash-lite-latest",
            "provider": "Google Gemini AI Studio",
        }

    monkeypatch.setattr("routers.chat.generate_gemini_chat", mock_generate_chat)

    res = client.post(
        "/api/chat",
        json={
            "message": "Explain how ghost vendor fraud is identified in public contracts.",
            "workspace_id": "test_ws",
            "history": [],
            "inject_memory": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "ghost vendor fraud" in data["reply"]
    assert data["provider"] == "Google Gemini AI Studio"
    assert data["workspace_id"] == "test_ws"
    assert "timestamp" in data
