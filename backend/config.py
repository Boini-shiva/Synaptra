import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv, dotenv_values

# Explicitly resolve repository root directory from backend source file location
# (backend/config.py -> parent is backend/ -> parent.parent is project root)
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
ENV_FILE = ROOT_DIR / ".env"

# Initial secure load from root .env file if it exists
if ENV_FILE.is_file():
    load_dotenv(dotenv_path=ENV_FILE, override=True)

# Recognized placeholder tokens that should be treated as unconfigured
KNOWN_PLACEHOLDERS = {
    "your_lyzr_api_key_here",
    "your_planner_agent_id_here",
    "your_api_key_here",
    "your_agent_id_here",
    "your_key_here",
    "<your-api-key>",
    "<your_api_key>",
    "<your-agent-id>",
    "<your_agent_id>",
    "placeholder",
    "changeme",
    "example",
    "none",
    "null",
    "todo",
}


def is_placeholder_or_empty(value: Optional[str]) -> bool:
    """
    Returns True if value is None, empty, whitespace-only,
    or matches known placeholder templates.
    """
    if value is None:
        return True
    val = value.strip()
    if not val:
        return True
    val_lower = val.lower()
    if val_lower in KNOWN_PLACEHOLDERS:
        return True
    if val_lower.startswith("your_") or val_lower.startswith("<your"):
        return True
    return False


def reload_env():
    """Reload environment variables from root .env file using explicit path."""
    if ENV_FILE.is_file():
        load_dotenv(dotenv_path=ENV_FILE, override=True)


def get_lyzr_api_key() -> str:
    """Reads LYZR_API_KEY from environment or root .env file without printing value."""
    reload_env()
    key = os.getenv("LYZR_API_KEY")
    if not key and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        key = file_vals.get("LYZR_API_KEY")
    return (key or "").strip()


def get_lyzr_planner_agent_id() -> str:
    """Reads LYZR_PLANNER_AGENT_ID from environment or root .env file without printing value."""
    reload_env()
    agent_id = os.getenv("LYZR_PLANNER_AGENT_ID")
    if not agent_id and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        agent_id = file_vals.get("LYZR_PLANNER_AGENT_ID")
    return (agent_id or "").strip()


def get_lyzr_executor_agent_id() -> str:
    """Reads LYZR_EXECUTOR_AGENT_ID from environment or root .env file without printing value."""
    reload_env()
    agent_id = os.getenv("LYZR_EXECUTOR_AGENT_ID")
    if not agent_id and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        agent_id = file_vals.get("LYZR_EXECUTOR_AGENT_ID")
    return (agent_id or "").strip()


def get_lyzr_memory_agent_id() -> str:
    """Reads LYZR_MEMORY_AGENT_ID from environment or root .env file without printing value."""
    reload_env()
    agent_id = os.getenv("LYZR_MEMORY_AGENT_ID")
    if not agent_id and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        agent_id = file_vals.get("LYZR_MEMORY_AGENT_ID")
    return (agent_id or "").strip()


def get_lyzr_reviewer_agent_id() -> str:
    """Reads LYZR_REVIEWER_AGENT_ID from environment or root .env file without printing value."""
    reload_env()
    agent_id = os.getenv("LYZR_REVIEWER_AGENT_ID")
    if not agent_id and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        agent_id = file_vals.get("LYZR_REVIEWER_AGENT_ID")
    return (agent_id or "").strip()


def get_qdrant_url() -> str:
    """Reads QDRANT_URL from environment or root .env file, default http://127.0.0.1:6333."""
    reload_env()
    url = os.getenv("QDRANT_URL")
    if not url and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        url = file_vals.get("QDRANT_URL")
    return (url or "http://127.0.0.1:6333").strip()


def get_qdrant_collection() -> str:
    """Reads QDRANT_COLLECTION from environment or root .env file, default synaptra_memory."""
    reload_env()
    col = os.getenv("QDRANT_COLLECTION")
    if not col and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        col = file_vals.get("QDRANT_COLLECTION")
    return (col or "synaptra_memory").strip()


def get_qdrant_api_key() -> Optional[str]:
    """Reads QDRANT_API_KEY from environment or root .env file without printing value."""
    reload_env()
    key = os.getenv("QDRANT_API_KEY")
    if not key and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        key = file_vals.get("QDRANT_API_KEY")
    if is_placeholder_or_empty(key):
        return None
    return key.strip()



def get_gemini_api_key() -> str:
    """Reads GEMINI_API_KEY from environment or root .env file without printing value."""
    reload_env()
    key = os.getenv("GEMINI_API_KEY")
    if not key and ENV_FILE.is_file():
        file_vals = dotenv_values(dotenv_path=ENV_FILE)
        key = file_vals.get("GEMINI_API_KEY")
    return (key or "").strip()


def get_config_diagnostic() -> Dict[str, Any]:
    """
    Configuration diagnostic reporting ONLY whether each required
    variable is configured. Never prints or exposes secret values.
    """
    env_exists = ENV_FILE.is_file()
    api_key = get_lyzr_api_key()
    planner_id = get_lyzr_planner_agent_id()
    executor_id = get_lyzr_executor_agent_id()
    memory_id = get_lyzr_memory_agent_id()
    reviewer_id = get_lyzr_reviewer_agent_id()

    api_key_configured = not is_placeholder_or_empty(api_key)
    planner_id_configured = not is_placeholder_or_empty(planner_id)
    executor_id_configured = not is_placeholder_or_empty(executor_id)
    memory_id_configured = not is_placeholder_or_empty(memory_id)
    reviewer_id_configured = not is_placeholder_or_empty(reviewer_id)

    all_workflow = (
        api_key_configured
        and planner_id_configured
        and executor_id_configured
        and memory_id_configured
        and reviewer_id_configured
    )

    gemini_key = get_gemini_api_key()
    gemini_configured = not is_placeholder_or_empty(gemini_key)

    return {
        "env_file_path": str(ENV_FILE),
        "env_file_exists": env_exists,
        "lyzr_api_key_configured": api_key_configured,
        "lyzr_planner_agent_id_configured": planner_id_configured,
        "lyzr_executor_agent_id_configured": executor_id_configured,
        "lyzr_memory_agent_id_configured": memory_id_configured,
        "lyzr_reviewer_agent_id_configured": reviewer_id_configured,
        "gemini_api_key_configured": gemini_configured,
        "self_healing_enabled": gemini_configured,
        "all_configured": api_key_configured and planner_id_configured,
        "all_workflow_agents_configured": all_workflow,
        "qdrant_url": get_qdrant_url(),
        "qdrant_collection": get_qdrant_collection(),
    }



def validate_lyzr_credentials() -> Tuple[str, str]:
    """
    Validates presence of required Lyzr credentials for Planner Agent.
    Treats empty or placeholder credentials as missing.
    Raises ValueError with a clear, sanitized configuration error if missing.
    Never exposes or logs credential values.
    """
    api_key = get_lyzr_api_key()
    agent_id = get_lyzr_planner_agent_id()

    missing = []
    if is_placeholder_or_empty(api_key):
        missing.append("LYZR_API_KEY")
    if is_placeholder_or_empty(agent_id):
        missing.append("LYZR_PLANNER_AGENT_ID")

    if missing:
        raise ValueError(
            f"Missing required configuration: {', '.join(missing)}. "
            f"Please configure valid, non-placeholder credentials in root .env file at {ENV_FILE}."
        )

    return api_key, agent_id


def validate_workflow_credentials() -> Dict[str, str]:
    """
    Validates presence of required Lyzr credentials for all multi-agent workflow agents:
    - LYZR_API_KEY
    - LYZR_PLANNER_AGENT_ID
    - LYZR_EXECUTOR_AGENT_ID
    - LYZR_MEMORY_AGENT_ID
    - LYZR_REVIEWER_AGENT_ID

    Raises ValueError with a clear, sanitized message if any are missing or placeholder.
    Returns dict mapping role to agent_id plus api_key.
    Never exposes secret values.
    """
    api_key = get_lyzr_api_key()
    planner_id = get_lyzr_planner_agent_id()
    executor_id = get_lyzr_executor_agent_id()
    memory_id = get_lyzr_memory_agent_id()
    reviewer_id = get_lyzr_reviewer_agent_id()

    missing = []
    if is_placeholder_or_empty(api_key):
        missing.append("LYZR_API_KEY")
    if is_placeholder_or_empty(planner_id):
        missing.append("LYZR_PLANNER_AGENT_ID")
    if is_placeholder_or_empty(executor_id):
        missing.append("LYZR_EXECUTOR_AGENT_ID")
    if is_placeholder_or_empty(memory_id):
        missing.append("LYZR_MEMORY_AGENT_ID")
    if is_placeholder_or_empty(reviewer_id):
        missing.append("LYZR_REVIEWER_AGENT_ID")

    if missing:
        raise ValueError(
            f"Missing required workflow configuration: {', '.join(missing)}. "
            f"Please configure valid, non-placeholder credentials in root .env file at {ENV_FILE}."
        )

    return {
        "api_key": api_key,
        "planner_agent_id": planner_id,
        "executor_agent_id": executor_id,
        "memory_agent_id": memory_id,
        "reviewer_agent_id": reviewer_id,
    }
