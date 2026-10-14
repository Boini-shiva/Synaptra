from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from services.orchestrator import workflow_orchestrator
import config

router = APIRouter(tags=["Multi-Agent Workflow Orchestrator"])


class WorkflowExecutionRequest(BaseModel):
    task: str = Field(..., description="The user task or goal to execute. Must not be empty.")
    workspace_id: str = Field(default="default", description="Workspace identifier for tenant memory isolation")
    user_id: Optional[str] = Field(None, description="Optional user identifier for conversational continuity")
    session_id: Optional[str] = Field(None, description="Optional session identifier for context grouping")
    task_id: Optional[str] = Field(None, description="Optional unique task ID (generated if omitted)")
    timeout_seconds: Optional[float] = Field(default=90.0, ge=5.0, le=300.0, description="Per-agent timeout in seconds")

    @field_validator("task")
    @classmethod
    def validate_task_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Task description must not be empty.")
        return v.strip()

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("workspace_id must not be empty.")
        return v.strip()


class WorkflowEvent(BaseModel):
    event_id: str
    task_id: str
    event_type: str
    step_name: Optional[str] = None
    agent_role: Optional[str] = None
    agent_id: Optional[str] = None
    status: str
    timestamp: str
    duration_ms: Optional[float] = None
    input_summary: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0


class TraceStep(BaseModel):
    step_name: str
    agent_role: str
    agent_id: Optional[str] = None
    status: str  # SUCCESS, FAILED, WARNING, SKIPPED
    started_at: str
    completed_at: str
    duration_ms: float
    input_summary: str
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    provider: Optional[str] = "lyzr"
    self_healed: Optional[bool] = False


class WorkflowExecutionResponse(BaseModel):
    task_id: str
    status: str  # COMPLETED, FAILED
    task: str
    workspace_id: str
    final_response: Optional[str] = None
    execution_trace: List[TraceStep]
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    total_duration_ms: Optional[float] = None


class WorkflowDetailResponse(BaseModel):
    task_id: str
    status: str
    task: str
    workspace_id: str
    final_response: Optional[str] = None
    execution_trace: List[TraceStep]
    events_count: int
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    total_duration_ms: Optional[float] = None


class WorkflowEventsResponse(BaseModel):
    task_id: str
    count: int
    events: List[WorkflowEvent]


class WorkflowListItem(BaseModel):
    task_id: str
    status: str
    task: str
    workspace_id: str
    started_at: str
    completed_at: Optional[str] = None
    final_response: Optional[str] = None
    total_duration_ms: Optional[float] = None
    error: Optional[str] = None


class WorkflowListResponse(BaseModel):
    count: int
    workflows: List[WorkflowListItem]


@router.get("", response_model=WorkflowListResponse, summary="List Workflow History")
@router.get("/", response_model=WorkflowListResponse, include_in_schema=False)
async def list_workflows(
    workspace_id: Optional[str] = Query(None, description="Optional workspace filter"),
    limit: int = Query(50, ge=1, le=100, description="Max workflows to return"),
):
    """
    Retrieves history of executed workflows from in-memory orchestrator store, ordered newest first.
    """
    items = workflow_orchestrator.list_workflows(workspace_id=workspace_id, limit=limit)
    return WorkflowListResponse(
        count=len(items),
        workflows=[
            WorkflowListItem(
                task_id=w["task_id"],
                status=w["status"],
                task=w["task"],
                workspace_id=w["workspace_id"],
                started_at=w["started_at"],
                completed_at=w.get("completed_at"),
                final_response=w.get("final_response"),
                total_duration_ms=w.get("total_duration_ms"),
                error=w.get("error"),
            )
            for w in items
        ],
    )


@router.get("/status", summary="Workflow Orchestration Status")
async def get_workflow_status():
    """
    Returns diagnostics for all four workflow agents and vector memory.
    Never exposes API keys or secrets.
    """
    diag = config.get_config_diagnostic()
    return {
        "status": "ready" if diag.get("all_workflow_agents_configured") else "missing_credentials",
        "diagnostic": diag,
    }


@router.post("", response_model=WorkflowExecutionResponse, summary="Execute Multi-Agent Workflow")
@router.post("/", response_model=WorkflowExecutionResponse, include_in_schema=False)
@router.post("/execute", response_model=WorkflowExecutionResponse, summary="Execute Multi-Agent Workflow (alias)")
async def execute_workflow(request: WorkflowExecutionRequest):
    """
    Executes the real SYNAPTRA multi-agent workflow:
    1. Retrieves relevant historical context from Qdrant vector memory.
    2. Synthesizes knowledge via Memory Agent.
    3. Generates sequential subtasks via Planner Agent.
    4. Executes subtasks via Executor Agent with bounded concurrency.
    5. Reviews completeness, identifies missing work & produces final answer via Reviewer Agent.
    6. Stores workflow summary back into Qdrant for long-term memory.
    """
    # 1. Validate credentials
    try:
        config.validate_workflow_credentials()
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(val_err),
        )

    # 2. Execute orchestrator
    result = await workflow_orchestrator.execute_workflow(
        task=request.task,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        session_id=request.session_id,
        task_id=request.task_id,
        timeout_seconds=request.timeout_seconds or 90.0,
    )

    # If workflow failed, return HTTP 502 with structured failure trace
    if result["status"] == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": result["error"],
                "task_id": result["task_id"],
                "status": "FAILED",
                "execution_trace": result["execution_trace"],
            },
        )

    return WorkflowExecutionResponse(**result)


@router.get("/{task_id}", response_model=WorkflowDetailResponse, summary="Get Workflow Details")
async def get_workflow_by_id(task_id: str):
    """
    Retrieves execution state, final response, and execution trace for a specific workflow task.
    """
    wf = workflow_orchestrator.get_workflow(task_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow task with ID '{task_id}' not found.",
        )
    events = workflow_orchestrator.get_workflow_events(task_id) or []
    return WorkflowDetailResponse(
        task_id=wf["task_id"],
        status=wf["status"],
        task=wf["task"],
        workspace_id=wf["workspace_id"],
        final_response=wf.get("final_response"),
        execution_trace=wf.get("execution_trace", []),
        events_count=len(events),
        error=wf.get("error"),
        started_at=wf["started_at"],
        completed_at=wf.get("completed_at"),
        total_duration_ms=wf.get("total_duration_ms"),
    )


@router.get("/{task_id}/events", response_model=WorkflowEventsResponse, summary="Get Workflow Execution Events")
async def get_workflow_events_by_id(task_id: str):
    """
    Retrieves chronological execution events (start, completion, error, retry) for a specific workflow task.
    """
    wf = workflow_orchestrator.get_workflow(task_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow task with ID '{task_id}' not found.",
        )
    events = workflow_orchestrator.get_workflow_events(task_id) or []
    return WorkflowEventsResponse(
        task_id=task_id,
        count=len(events),
        events=[WorkflowEvent(**e) for e in events],
    )
