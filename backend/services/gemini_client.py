import asyncio
import logging
from typing import Optional, List, Dict, Any
import httpx

import config

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
CANDIDATE_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]


class GeminiClientError(Exception):
    """Custom exception for Gemini AI Studio API communication errors."""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def generate_gemini_content(
    prompt: str,
    system_instruction: Optional[str] = None,
    timeout_seconds: float = 35.0,
) -> str:
    """
    Invokes Google Gemini AI Studio endpoint using configured GEMINI_API_KEY.
    Tries candidate models in order of speed and stability.
    """
    api_key = config.get_gemini_api_key()
    if not api_key:
        raise GeminiClientError("GEMINI_API_KEY is not configured.", status_code=500)

    payload: Dict[str, Any] = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    timeout_config = httpx.Timeout(
        connect=10.0,
        read=timeout_seconds,
        write=10.0,
        pool=10.0,
    )

    last_error: Optional[Exception] = None

    for model_name in CANDIDATE_MODELS:
        url = f"{GEMINI_API_BASE}/{model_name}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
                raise GeminiClientError("Gemini response missing candidate parts.", status_code=502)

            # If not 200, try next candidate model
            logger.warning(
                f"Gemini model {model_name} returned HTTP {response.status_code}: {response.text[:200]}"
            )
            last_error = GeminiClientError(
                f"Gemini API ({model_name}) returned HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code if response.status_code in [400, 401, 403, 404, 429] else 502,
            )

        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning(f"Gemini model {model_name} request failed: {exc}")
            last_error = exc

    if isinstance(last_error, GeminiClientError):
        raise last_error
    raise GeminiClientError(f"All candidate Gemini models failed. Last error: {last_error}", status_code=502)


async def execute_gemini_agent(
    agent_role: str,
    task: str,
    context: Optional[str] = None,
    plan: Optional[str] = None,
    execution_results: Optional[str] = None,
) -> str:
    """
    Dispatches a structured multi-agent role to Gemini AI Studio with domain-tailored system instructions.
    Used for resilient fallback and automatic error rectification.
    """
    role_lower = agent_role.lower()

    if "plan" in role_lower:
        system_instruction = (
            "You are the SYNAPTRA Planner Agent, an elite AI workflow decomposition specialist. "
            "Your objective is to decompose the user's task into sequential, actionable subtasks. "
            "Itemize each subtask clearly with numbers (e.g., '1. [Subtask title]: [Specific instructions]', '2. ...'). "
            "Be clear, precise, and practical."
        )
        prompt = (
            f"User Task: {task}\n\n"
            f"Workspace Context & Memory Insights:\n{context or 'No prior memories found.'}\n\n"
            f"Instruction: Break this task down into sequential, actionable subtasks with clear objectives."
        )

    elif "exec" in role_lower:
        system_instruction = (
            "You are the SYNAPTRA Executor Agent, a senior analytical multi-agent executor. "
            "Your objective is to execute the assigned subtasks thoroughly and rigorously. "
            "Provide concrete, detailed findings, calculations, risk indicators, audits, and drafts. "
            "Do not handwave or give placeholders. Deliver complete, actionable output."
        )
        prompt = (
            f"Task Goal: {task}\n\n"
            f"Execution Action Plan:\n{plan or 'Execute comprehensive analysis for this task.'}\n\n"
            f"Memory Context:\n{context or 'Standard enterprise workspace context.'}\n\n"
            f"Instruction: Execute all planned steps thoroughly with specific details, observations, and findings."
        )

    elif "review" in role_lower:
        system_instruction = (
            "You are the SYNAPTRA Reviewer Agent, the quality assurance and synthesis authority. "
            "Your role is to rigorously evaluate the execution findings against the original objective, "
            "verify accuracy, flag any potential risks or edge cases, and produce the authoritative, "
            "polished, final comprehensive response for the user."
        )
        prompt = (
            f"Original Task: {task}\n\n"
            f"Action Plan:\n{plan or 'Decomposition plan'}\n\n"
            f"Execution Findings:\n{execution_results or 'Detailed execution output'}\n\n"
            f"Memory Context:\n{context or 'Workspace context'}\n\n"
            f"Instruction: Review and synthesize the execution results into the final authoritative response."
        )

    else:
        # Default / Memory Agent
        system_instruction = (
            "You are the SYNAPTRA Memory Agent. Your role is to analyze retrieved vector context, "
            "synthesize key historical guidelines and constraints, and propose valuable domain context."
        )
        prompt = (
            f"Task: {task}\n\n"
            f"Retrieved Records:\n{context or 'No prior records'}\n\n"
            f"Instruction: Synthesize the relevant domain constraints and contextual background."
        )

    return await generate_gemini_content(prompt, system_instruction=system_instruction)


async def generate_gemini_chat(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    context: Optional[str] = None,
    system_instruction: Optional[str] = None,
    timeout_seconds: float = 35.0,
) -> Dict[str, Any]:
    """
    Multi-turn conversation helper with Google Gemini AI Studio.
    Converts chat history into Gemini contents schema with role 'user' and 'model'.
    """
    api_key = config.get_gemini_api_key()
    if not api_key:
        raise GeminiClientError("GEMINI_API_KEY is not configured.", status_code=500)

    default_sys = (
        "You are SYNAPTRA AI Copilot, an elite multi-agent AI assistant and financial audit expert. "
        "You assist users in auditing invoices, tenders, procurement contracts, detecting fraud/waste/anomalies "
        "(duplicate billings, ghost vendors, inflated amounts), analyzing workflow results, and answering "
        "questions with authoritative precision, clear structure, and professional formatting."
    )

    contents: List[Dict[str, Any]] = []

    # Inject context into history if available
    if history:
        for turn in history[-10:]:  # Keep recent context window
            role = turn.get("role", "user")
            gemini_role = "model" if role in ["assistant", "model", "bot"] else "user"
            text_val = turn.get("content", "").strip()
            if text_val:
                contents.append({"role": gemini_role, "parts": [{"text": text_val}]})

    # Prepare user query with workspace context
    final_user_text = message
    if context and context.strip():
        final_user_text = f"Workspace Memory Context (Qdrant):\n{context.strip()}\n\nUser Question:\n{message}"

    contents.append({"role": "user", "parts": [{"text": final_user_text}]})

    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
        "systemInstruction": {
            "parts": [{"text": system_instruction or default_sys}]
        },
    }

    timeout_config = httpx.Timeout(
        connect=10.0,
        read=timeout_seconds,
        write=10.0,
        pool=10.0,
    )

    last_error: Optional[Exception] = None

    for model_name in CANDIDATE_MODELS:
        url = f"{GEMINI_API_BASE}/{model_name}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return {
                            "reply": parts[0]["text"].strip(),
                            "model": model_name,
                            "provider": "Google Gemini AI Studio",
                        }
                raise GeminiClientError("Gemini chat response missing candidates.", status_code=502)

            logger.warning(
                f"Gemini chat model {model_name} HTTP {response.status_code}: {response.text[:200]}"
            )
            last_error = GeminiClientError(
                f"Gemini chat ({model_name}) HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code if response.status_code in [400, 401, 403, 404, 429] else 502,
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning(f"Gemini chat model {model_name} request failed: {exc}")
            last_error = exc

    if isinstance(last_error, GeminiClientError):
        raise last_error
    raise GeminiClientError(f"All candidate Gemini models failed for chat. Last error: {last_error}", status_code=502)

