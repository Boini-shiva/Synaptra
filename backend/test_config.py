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

client = TestClient(app)


@pytest.fixture(autouse=True)
def restore_environment():
    """Ensure environment variables and config settings are preserved across tests."""
    orig_key = os.environ.get("LYZR_API_KEY")
    orig_id = os.environ.get("LYZR_PLANNER_AGENT_ID")
    orig_file = config.ENV_FILE
    yield
    if orig_key is not None:
        os.environ["LYZR_API_KEY"] = orig_key
    else:
        os.environ.pop("LYZR_API_KEY", None)
    if orig_id is not None:
        os.environ["LYZR_PLANNER_AGENT_ID"] = orig_id
    else:
        os.environ.pop("LYZR_PLANNER_AGENT_ID", None)
    config.ENV_FILE = orig_file


def test_explicit_root_env_path_resolution():
    """Verify that ENV_FILE is explicitly resolved from source file location, not cwd."""
    expected_root = Path(__file__).resolve().parent.parent
    expected_env_file = expected_root / ".env"
    assert config.ENV_FILE == expected_env_file
    assert config.ENV_FILE.name == ".env"
    assert config.BACKEND_DIR == Path(__file__).resolve().parent


def test_placeholder_detection():
    """Verify that empty, whitespace, and known placeholder values are recognized."""
    assert config.is_placeholder_or_empty(None) is True
    assert config.is_placeholder_or_empty("") is True
    assert config.is_placeholder_or_empty("   ") is True
    assert config.is_placeholder_or_empty("your_lyzr_api_key_here") is True
    assert config.is_placeholder_or_empty("YOUR_LYZR_API_KEY_HERE") is True
    assert config.is_placeholder_or_empty("your_planner_agent_id_here") is True
    assert config.is_placeholder_or_empty("<your-api-key>") is True
    assert config.is_placeholder_or_empty("changeme") is True

    # Real-looking values should NOT be marked as placeholders
    assert config.is_placeholder_or_empty("lyzr_sk_live_1234567890abcdef") is False
    assert config.is_placeholder_or_empty("683f4657fcc016e56d66dbe8") is False


def test_config_diagnostic_structure():
    """Verify diagnostic returns boolean status without exposing values."""
    diag = config.get_config_diagnostic()
    assert "env_file_path" in diag
    assert "env_file_exists" in diag
    assert "lyzr_api_key_configured" in diag
    assert "lyzr_planner_agent_id_configured" in diag
    assert "all_configured" in diag

    assert isinstance(diag["lyzr_api_key_configured"], bool)
    assert isinstance(diag["lyzr_planner_agent_id_configured"], bool)
    assert isinstance(diag["all_configured"], bool)


def test_config_status_endpoint():
    """Verify GET /api/config/status endpoint returns valid diagnostic."""
    response = client.get("/api/config/status")
    assert response.status_code == 200
    data = response.json()
    assert "env_file_path" in data
    assert "env_file_exists" in data
    assert "lyzr_api_key_configured" in data
    assert "lyzr_planner_agent_id_configured" in data


def test_health_endpoint_includes_config_diagnostic():
    """Verify GET /api/health includes the config diagnostic."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "config" in data
    assert "lyzr_api_key_configured" in data["config"]


def test_loading_from_explicit_env_file(tmp_path, monkeypatch):
    """
    Simulate loading from an explicit .env file location to prove
    root .env loading works correctly without relying on terminal cwd.
    """
    fake_env = tmp_path / ".env"
    fake_env.write_text("LYZR_API_KEY=lyzr_test_valid_key_12345\nLYZR_PLANNER_AGENT_ID=agent_test_valid_id_67890\n")

    monkeypatch.setattr(config, "ENV_FILE", fake_env)
    monkeypatch.delenv("LYZR_API_KEY", raising=False)
    monkeypatch.delenv("LYZR_PLANNER_AGENT_ID", raising=False)

    diag = config.get_config_diagnostic()
    assert diag["env_file_exists"] is True
    assert diag["lyzr_api_key_configured"] is True
    assert diag["lyzr_planner_agent_id_configured"] is True
    assert diag["all_configured"] is True

    key, agent_id = config.validate_lyzr_credentials()
    assert key == "lyzr_test_valid_key_12345"
    assert agent_id == "agent_test_valid_id_67890"


def test_placeholder_in_env_file_treated_as_missing(tmp_path, monkeypatch):
    """
    Verify that placeholder values in .env file are rejected as missing.
    """
    fake_env = tmp_path / ".env"
    fake_env.write_text("LYZR_API_KEY=your_lyzr_api_key_here\nLYZR_PLANNER_AGENT_ID=your_planner_agent_id_here\n")

    monkeypatch.setattr(config, "ENV_FILE", fake_env)
    monkeypatch.delenv("LYZR_API_KEY", raising=False)
    monkeypatch.delenv("LYZR_PLANNER_AGENT_ID", raising=False)

    diag = config.get_config_diagnostic()
    assert diag["lyzr_api_key_configured"] is False
    assert diag["lyzr_planner_agent_id_configured"] is False
    assert diag["all_configured"] is False

    with pytest.raises(ValueError, match="Missing required configuration"):
        config.validate_lyzr_credentials()
