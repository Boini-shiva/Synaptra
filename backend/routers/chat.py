import logging
import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

import config
from services.gemini_client import generate_gemini_chat, GeminiClientError
from services.qdrant_service import memory_service, QdrantServiceError, QdrantUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["AI Copilot / Chatbot"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's query or instruction")
    workspace_id: str = Field(default="default", description="Active tenant workspace for vector context")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Recent conversation turns")
    inject_memory: bool = Field(default=True, description="Whether to semantically query Qdrant vector memory")


class Citation(BaseModel):
    id: Optional[str] = None
    content: str
    score: Optional[float] = None
    workspace_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    model: str
    provider: str
    workspace_id: str
    citations: List[Citation]
    timestamp: str


@router.post("", response_model=ChatResponse, summary="Interactive AI Copilot Chat (Gemini AI Studio)")
@router.post("/", response_model=ChatResponse, include_in_schema=False)
async def chat_with_assistant(request: ChatRequest):
    """
    Direct conversational interface with SYNAPTRA's AI Copilot powered by Google Gemini AI Studio.
    Injects contextual memory from Qdrant vector database for the active workspace.
    """
    clean_msg = request.message.strip()
    if not clean_msg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chat message must not be empty.",
        )

    # 1. Retrieve relevant memory context from Qdrant if requested
    citations: List[Citation] = []
    context_text = ""

    if request.inject_memory:
        try:
            memories = memory_service.search_memories(
                query=clean_msg,
                workspace_id=request.workspace_id,
                limit=4,
                score_threshold=0.25,
            )
            if memories:
                snippets = []
                for m in memories:
                    c = m.get("content", "").strip()
                    if c:
                        snippets.append(f"- {c}")
                        citations.append(
                            Citation(
                                id=m.get("id"),
                                content=c[:200] + "..." if len(c) > 200 else c,
                                score=m.get("score"),
                                workspace_id=request.workspace_id,
                            )
                        )
                if snippets:
                    context_text = "\n".join(snippets)
        except (QdrantUnavailableError, QdrantServiceError, Exception) as exc:
            logger.warning(f"Vector memory retrieval skipped for chat: {exc}")

    # 2. Call Gemini AI Studio
    try:
        chat_history = [
            {"role": m.role, "content": m.content}
            for m in request.history
        ]
        result = await generate_gemini_chat(
            message=clean_msg,
            history=chat_history,
            context=context_text,
        )

        return ChatResponse(
            reply=result["reply"],
            model=result.get("model", "gemini-flash-lite-latest"),
            provider=result.get("provider", "Google Gemini AI Studio"),
            workspace_id=request.workspace_id,
            citations=citations,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    except GeminiClientError as g_err:
        logger.error(f"Gemini AI Studio chat failed: {g_err.message}")
        raise HTTPException(
            status_code=g_err.status_code,
            detail=g_err.message,
        )
    except Exception as exc:
        logger.error(f"Unexpected error during chat: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation failed: {type(exc).__name__} - {str(exc)}",
        )


@router.get("/suggestions", summary="Get Quick Chat Prompts")
async def get_chat_suggestions():
    """Returns curated quick prompts for the AI Assistant."""
    return {
        "suggestions": [
            {
                "title": "Municipal Fraud Detection",
                "prompt": "How does SYNAPTRA audit municipal vendor procurement contracts to detect duplicate billing anomalies?",
                "category": "Fraud Audit",
            },
            {
                "title": "Ghost Vendor Red Flags",
                "prompt": "What are the key red flags and risk indicators for identifying ghost vendors in government expenditure?",
                "category": "Audit Patterns",
            },
            {
                "title": "Multi-Agent Self-Healing",
                "prompt": "Explain how SYNAPTRA's multi-agent architecture uses Google Gemini AI Studio for automated self-healing when upstream agents fail.",
                "category": "Architecture",
            },
            {
                "title": "Tender Bid Rigging",
                "prompt": "What algorithmic checks should be performed on public tender bids to detect collusion or bid rigging between competing vendors?",
                "category": "Procurement",
            },
        ]
    }
