import sys
from pathlib import Path
from typing import Optional

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from config import validate_lyzr_credentials, get_config_diagnostic
from services.lyzr_client import execute_planner_agent, LyzrClientError
from services.gemini_client import execute_gemini_agent
from routers.memory import router as memory_router
from routers.workflow import router as workflow_router
from routers.chat import router as chat_router

app = FastAPI(
    title="SYNAPTRA Backend API",
    description="Multi-agent AI workflow backend with Qdrant vector memory for SYNAPTRA",
    version="0.3.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(memory_router)
app.include_router(workflow_router, prefix="/api/workflows")
app.include_router(workflow_router, prefix="/api/workflow", include_in_schema=False)
app.include_router(chat_router)


class PlannerRequest(BaseModel):
    task: str = Field(..., description="The task description or goal to plan. Must not be empty.")
    user_id: Optional[str] = Field(None, description="Optional user identifier for conversational memory")
    session_id: Optional[str] = Field(None, description="Optional session identifier for context persistence")

    @field_validator("task")
    @classmethod
    def validate_task_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Task string must not be empty.")
        return v.strip()


class PlannerResponse(BaseModel):
    status: str
    task: str
    response: str
    agent_id: str
    session_id: str


@app.get("/", summary="Root Health & Info")
@app.get("/api", summary="API Health & Info")
@app.get("/api/health", summary="Health Check")
async def health_check():
    """Returns the operational status and configuration diagnostics of SYNAPTRA backend service."""
    diagnostic = get_config_diagnostic()
    return {
        "status": "ok",
        "service": "synaptra-backend",
        "version": "0.2.0",
        "config": diagnostic,
    }


@app.get("/api/config/status", summary="Configuration Diagnostic")
async def config_status():
    """
    Configuration diagnostic reporting ONLY whether each required
    variable is configured. Never exposes secret values.
    """
    return get_config_diagnostic()


@app.post("/api/planner", response_model=PlannerResponse, summary="Execute SYNAPTRA Planner Agent")
async def plan_task(request: PlannerRequest):
    """
    Submits a task to the SYNAPTRA Planner agent via Lyzr Agent API.
    Validates credentials and inputs before dispatching.
    """
    # 1. Validate required environment configuration
    try:
        validate_lyzr_credentials()
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(val_err),
        )

    # 2. Execute agent inference call
    try:
        result = await execute_planner_agent(
            task=request.task,
            user_id=request.user_id,
            session_id=request.session_id,
        )
        return PlannerResponse(
            status="success",
            task=result["task"],
            response=result["response"],
            agent_id=result["agent_id"],
            session_id=result["session_id"],
        )
    except LyzrClientError as err:
        import config as cfg
        gemini_key = cfg.get_gemini_api_key()
        if gemini_key:
            import uuid
            try:
                gemini_res = await execute_gemini_agent(
                    agent_role="planner_agent",
                    task=request.task,
                )
                return PlannerResponse(
                    status="success",
                    task=request.task,
                    response=gemini_res,
                    agent_id="gemini-auto-rectified",
                    session_id=request.session_id or f"synaptra_{uuid.uuid4().hex[:12]}",
                )
            except Exception as g_err:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Both Lyzr ({err.message}) and Gemini fallback failed: {str(g_err)}",
                )
        raise HTTPException(
            status_code=err.status_code,
            detail=err.message,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {type(err).__name__}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
