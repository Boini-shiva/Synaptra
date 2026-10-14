from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from services.qdrant_service import (
    memory_service,
    QdrantServiceError,
    QdrantUnavailableError,
    MemoryNotFoundError,
)
from services.embedding_service import EmbeddingError

router = APIRouter(prefix="/api/memory", tags=["Vector Memory"])

"""
SECURITY & MULTI-TENANCY NOTICE:
All memory operations enforce data segregation through 'workspace_id' metadata filtering.
NOTE: Workspace identifiers provide workspace segregation and data partitioning, but
THEY DO NOT CONSTITUTE AUTHENTICATED USER IDENTITY OR AUTHORIZATION.
Prior to production deployment, authenticated identity (e.g., verified JWT/OAuth claims)
and role-based authorization must be bound to each request.
"""


class MemoryCreateRequest(BaseModel):
    content: str = Field(..., description="The textual memory content. Must not be empty.")
    memory_type: str = Field(default="note", description="Type of memory: note, task, plan, execution, etc.")
    source_agent: str = Field(default="user", description="Source agent or author")
    workspace_id: str = Field(default="default", description="Workspace identifier for tenant isolation")
    visibility: str = Field(default="shared", description="Visibility level (shared, private, team)")
    memory_id: Optional[str] = Field(default=None, description="Optional custom unique ID. Generated automatically if omitted.")

    @field_validator("content")
    @classmethod
    def validate_content_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Memory content must not be empty.")
        return v.strip()

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("workspace_id must not be empty.")
        return v.strip()


class MemoryItem(BaseModel):
    memory_id: str
    content: str
    memory_type: str
    created_at: str
    source_agent: str
    workspace_id: str
    visibility: str


class MemorySearchItem(MemoryItem):
    score: float


class MemorySearchResponse(BaseModel):
    status: str
    query: str
    workspace_id: str
    count: int
    results: List[MemorySearchItem]


class MemoryListResponse(BaseModel):
    status: str
    workspace_id: str
    count: int
    memories: List[MemoryItem]


class MemoryDeleteResponse(BaseModel):
    status: str
    deleted_id: str
    message: str


@router.get("/health", summary="Memory Service Health Check")
async def memory_health():
    """
    Checks connection to the Qdrant vector database and returns collection status.
    Returns 503 if Qdrant is unreachable without crashing the FastAPI backend.
    """
    try:
        diag = memory_service.check_health()
        return diag
    except QdrantUnavailableError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err.message,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected memory service error: {exc}",
        )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MemoryItem, summary="Save Memory")
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=MemoryItem, include_in_schema=False)
async def create_memory(request: MemoryCreateRequest):
    """
    Generates a 384-dimensional embedding and stores a new memory item in Qdrant.
    """
    try:
        created = memory_service.insert_memory(
            content=request.content,
            memory_type=request.memory_type,
            source_agent=request.source_agent,
            workspace_id=request.workspace_id,
            visibility=request.visibility,
            memory_id=request.memory_id,
        )
        return created
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except EmbeddingError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))
    except QdrantUnavailableError as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=err.message)
    except QdrantServiceError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to store memory: {exc}")


@router.get("/search", response_model=MemorySearchResponse, summary="Semantic Memory Search")
async def search_memories(
    q: str = Query(..., description="Semantic search query text. Must not be empty."),
    workspace_id: str = Query(..., description="Workspace identifier to restrict search scope."),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of search results to return."),
    memory_type: Optional[str] = Query(None, description="Optional memory type filter."),
    visibility: Optional[str] = Query(None, description="Optional visibility filter."),
):
    """
    Converts query text to a 384-dimensional dense vector and searches the Qdrant memory collection,
    enforcing workspace isolation and returning similarity scores.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Search query 'q' must not be empty.")
    if not workspace_id or not workspace_id.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Parameter 'workspace_id' must not be empty.")

    try:
        results = memory_service.search_memories(
            query=q.strip(),
            workspace_id=workspace_id.strip(),
            limit=limit,
            memory_type=memory_type,
            visibility=visibility,
        )
        return MemorySearchResponse(
            status="success",
            query=q.strip(),
            workspace_id=workspace_id.strip(),
            count=len(results),
            results=[MemorySearchItem(**r) for r in results],
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except EmbeddingError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))
    except QdrantUnavailableError as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=err.message)
    except QdrantServiceError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Search failed: {exc}")


@router.get("", response_model=MemoryListResponse, summary="List Memories")
@router.get("/", response_model=MemoryListResponse, include_in_schema=False)
async def list_memories(
    workspace_id: str = Query(..., description="Workspace identifier to list memories from."),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of memories to return."),
    memory_type: Optional[str] = Query(None, description="Optional memory type filter."),
    visibility: Optional[str] = Query(None, description="Optional visibility filter."),
):
    """
    Lists memories belonging to a specific workspace with pagination/limit support.
    """
    if not workspace_id or not workspace_id.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Parameter 'workspace_id' must not be empty.")

    try:
        memories = memory_service.list_memories(
            workspace_id=workspace_id.strip(),
            limit=limit,
            memory_type=memory_type,
            visibility=visibility,
        )
        return MemoryListResponse(
            status="success",
            workspace_id=workspace_id.strip(),
            count=len(memories),
            memories=[MemoryItem(**m) for m in memories],
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except QdrantUnavailableError as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=err.message)
    except QdrantServiceError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Listing failed: {exc}")


@router.delete("/{memory_id}", response_model=MemoryDeleteResponse, summary="Delete Memory")
async def delete_memory(
    memory_id: str,
    workspace_id: str = Query(..., description="Workspace identifier to enforce tenant isolation during deletion."),
):
    """
    Deletes a single memory record by memory_id, strictly enforcing workspace boundary.
    Returns 404 if memory does not exist in the specified workspace.
    """
    if not memory_id or not memory_id.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Parameter 'memory_id' must not be empty.")
    if not workspace_id or not workspace_id.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Parameter 'workspace_id' must not be empty.")

    try:
        memory_service.delete_memory(
            memory_id=memory_id.strip(),
            workspace_id=workspace_id.strip(),
        )
        return MemoryDeleteResponse(
            status="success",
            deleted_id=memory_id.strip(),
            message="Memory deleted successfully.",
        )
    except MemoryNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except QdrantUnavailableError as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=err.message)
    except QdrantServiceError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Deletion failed: {exc}")
