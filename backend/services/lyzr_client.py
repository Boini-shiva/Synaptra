import asyncio
import uuid
import logging
from typing import Optional, Dict, Any
import httpx
from pydantic import BaseModel, Field

from config import get_lyzr_api_key, validate_lyzr_credentials

logger = logging.getLogger(__name__)

LYZR_CHAT_URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"
DEFAULT_TIMEOUT_SECONDS = 90.0


class LyzrClientError(Exception):
    """Custom exception for Lyzr API communication errors with sanitized message."""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def execute_lyzr_agent(
    agent_id: str,
    message: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = 2,
    retry_delay_seconds: float = 1.0,
) -> Dict[str, Any]:
    """
    Executes any Lyzr agent via the official Lyzr Agent v3 inference endpoint.
    Includes bounded retries for transient HTTP (502, 503, 504) or network errors.
    Ensures secure header injection and never logs or leaks credentials.
    """
    api_key = get_lyzr_api_key()
    if not api_key:
        raise LyzrClientError("LYZR_API_KEY is not configured.", status_code=500)
    if not agent_id or not agent_id.strip():
        raise LyzrClientError("Agent ID must be provided and non-empty.", status_code=500)

    effective_user_id = user_id or "synaptra_user"
    effective_session_id = session_id or f"synaptra_{uuid.uuid4().hex[:12]}"

    payload = {
        "user_id": effective_user_id,
        "agent_id": agent_id.strip(),
        "session_id": effective_session_id,
        "message": message,
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }

    timeout_config = httpx.Timeout(
        connect=10.0,
        read=timeout_seconds,
        write=10.0,
        pool=10.0,
    )

    last_error: Optional[LyzrClientError] = None
    retries_performed = 0

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.post(
                    LYZR_CHAT_URL,
                    json=payload,
                    headers=headers,
                )

            if response.status_code != 200:
                err_text = response.text[:300] if response.text else "No details returned by upstream API"
                status_code = response.status_code if response.status_code in [400, 401, 403, 404, 422, 429] else 502
                
                # Check if error is transient and retryable
                is_transient = response.status_code in [502, 503, 504, 429]
                last_error = LyzrClientError(
                    message=f"Lyzr API error (HTTP {response.status_code}): {err_text}",
                    status_code=status_code,
                )
                if is_transient and attempt < max_retries:
                    retries_performed += 1
                    logger.warning(
                        f"Transient Lyzr API error HTTP {response.status_code}. "
                        f"Retrying in {retry_delay_seconds * (2 ** attempt)}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(retry_delay_seconds * (2 ** attempt))
                    continue
                raise last_error

            data = response.json()
            agent_reply = data.get("response")
            if agent_reply is None:
                raise LyzrClientError(
                    message="Lyzr API returned unexpected response structure without 'response' field.",
                    status_code=502,
                )

            return {
                "message": message,
                "response": agent_reply,
                "agent_id": agent_id,
                "session_id": effective_session_id,
                "retry_count": retries_performed,
                "raw": data,
            }

        except httpx.TimeoutException as exc:
            last_error = LyzrClientError(
                message=f"Timed out after {timeout_seconds}s waiting for Lyzr Agent response.",
                status_code=504,
            )
            if attempt < max_retries:
                retries_performed += 1
                logger.warning(f"Lyzr API request timed out. Retrying (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            raise last_error from exc
        except httpx.RequestError as exc:
            last_error = LyzrClientError(
                message=f"Failed to connect to Lyzr API endpoint: {type(exc).__name__}",
                status_code=503,
            )
            if attempt < max_retries:
                retries_performed += 1
                logger.warning(f"Lyzr API connection failed: {exc}. Retrying (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            raise last_error from exc

    if last_error:
        raise last_error
    raise LyzrClientError("Unknown error occurred during Lyzr agent execution.", status_code=500)


async def execute_planner_agent(
    task: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Executes the SYNAPTRA Planner agent via the official Lyzr Agent v3 inference endpoint.
    Maintains full backward compatibility with existing tests and API callers.
    """
    api_key, agent_id = validate_lyzr_credentials()
    result = await execute_lyzr_agent(
        agent_id=agent_id,
        message=task,
        user_id=user_id,
        session_id=session_id,
        timeout_seconds=timeout_seconds,
    )
    return {
        "task": task,
        "response": result["response"],
        "agent_id": result["agent_id"],
        "session_id": result["session_id"],
        "raw": result["raw"],
    }
