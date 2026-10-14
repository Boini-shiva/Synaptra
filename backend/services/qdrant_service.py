import uuid
import datetime
import logging
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PointIdsList,
)
from qdrant_client.http.exceptions import UnexpectedResponse

import config
from services.embedding_service import generate_embedding, VECTOR_DIMENSION

logger = logging.getLogger(__name__)


class QdrantServiceError(Exception):
    """Base exception for Qdrant memory service errors."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class QdrantUnavailableError(QdrantServiceError):
    """Raised when the Qdrant service cannot be reached or is down."""
    def __init__(self, message: str = "Vector database (Qdrant) is currently unreachable."):
        super().__init__(message, status_code=503)


class MemoryNotFoundError(QdrantServiceError):
    """Raised when a specific memory cannot be found in the specified workspace."""
    def __init__(self, memory_id: str, workspace_id: str):
        message = f"Memory with id '{memory_id}' not found in workspace '{workspace_id}'."
        super().__init__(message, status_code=404)


class QdrantMemoryService:
    """
    Manages vector memory operations against Qdrant.
    
    SECURITY & PRIVACY NOTICE:
    Workspace isolation is enforced via 'workspace_id' metadata filtering on all read,
    search, and delete operations. However, a workspace identifier alone provides
    data partitioning and DOES NOT replace authenticated user identity or authorization.
    Production systems must enforce authenticated identity (e.g. JWT) and permission checks.
    """

    def __init__(self, url: Optional[str] = None, collection_name: Optional[str] = None):
        self.url = url or config.get_qdrant_url()
        self.collection_name = collection_name or config.get_qdrant_collection()
        self._client: Optional[QdrantClient] = None

    def get_client(self) -> QdrantClient:
        """Returns or creates the QdrantClient instance."""
        current_url = config.get_qdrant_url()
        current_api_key = config.get_qdrant_api_key()
        if self._client is None or self.url != current_url:
            self.url = current_url
            try:
                self._client = QdrantClient(url=self.url, api_key=current_api_key, timeout=10.0)
            except Exception as exc:
                raise QdrantUnavailableError(f"Failed to initialize Qdrant client for {self.url}: {exc}") from exc
        return self._client

    def ensure_collection(self) -> bool:
        """Ensures the memory collection exists with 384 dimensions and Cosine distance."""
        client = self.get_client()
        self.collection_name = config.get_qdrant_collection()
        try:
            if not client.collection_exists(self.collection_name):
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=VECTOR_DIMENSION, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection '{self.collection_name}' (dim={VECTOR_DIMENSION}, dist=Cosine)")
            return True
        except Exception as exc:
            if "connection" in str(exc).lower() or "timeout" in str(exc).lower() or "failed to connect" in str(exc).lower():
                raise QdrantUnavailableError(f"Cannot reach Qdrant at {self.url}: {exc}") from exc
            raise QdrantServiceError(f"Failed to ensure collection '{self.collection_name}': {exc}") from exc

    def check_health(self) -> Dict[str, Any]:
        """Checks connection to Qdrant and returns collection diagnostic."""
        client = self.get_client()
        self.collection_name = config.get_qdrant_collection()
        try:
            # Check if server responds to collection query
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]
            exists = self.collection_name in collection_names
            points_count = 0
            if exists:
                info = client.get_collection(self.collection_name)
                points_count = info.points_count or 0

            return {
                "status": "ok",
                "qdrant_url": self.url,
                "collection": self.collection_name,
                "collection_exists": exists,
                "points_count": points_count,
                "embedding_model": "all-MiniLM-L6-v2",
                "vector_dim": VECTOR_DIMENSION,
            }
        except Exception as exc:
            logger.warning(f"Qdrant health check failed: {exc}")
            raise QdrantUnavailableError(f"Qdrant vector database unreachable at {self.url}: {exc}") from exc

    def insert_memory(
        self,
        content: str,
        memory_type: str = "note",
        source_agent: str = "user",
        workspace_id: str = "default",
        visibility: str = "shared",
        memory_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Embeds and stores a new memory item in Qdrant.
        """
        self.ensure_collection()
        client = self.get_client()

        assigned_id = memory_id or str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Compute 384-dimensional vector embedding
        vector = generate_embedding(content)

        payload = {
            "memory_id": assigned_id,
            "content": content,
            "memory_type": memory_type,
            "created_at": created_at,
            "source_agent": source_agent,
            "workspace_id": workspace_id,
            "visibility": visibility,
        }

        try:
            point = PointStruct(
                id=assigned_id,
                vector=vector,
                payload=payload,
            )
            client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )
            return payload
        except Exception as exc:
            if "connection" in str(exc).lower() or "timeout" in str(exc).lower():
                raise QdrantUnavailableError(f"Qdrant connection lost while storing memory: {exc}") from exc
            raise QdrantServiceError(f"Failed to upsert memory point into Qdrant: {exc}") from exc

    def search_memories(
        self,
        query: str,
        workspace_id: str,
        limit: int = 10,
        memory_type: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic search against memories isolated by workspace_id.
        """
        self.ensure_collection()
        client = self.get_client()

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty or whitespace-only.")
        if not workspace_id or not workspace_id.strip():
            raise ValueError("workspace_id is required for semantic search.")

        query_vector = generate_embedding(query)

        # Enforce workspace isolation
        must_conditions = [
            FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id.strip()))
        ]
        if memory_type and memory_type.strip():
            must_conditions.append(FieldCondition(key="memory_type", match=MatchValue(value=memory_type.strip())))
        if visibility and visibility.strip():
            must_conditions.append(FieldCondition(key="visibility", match=MatchValue(value=visibility.strip())))

        query_filter = Filter(must=must_conditions)

        try:
            # Compatible query points API
            if hasattr(client, "query_points"):
                query_response = client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=max(1, min(limit, 100)),
                    with_payload=True,
                )
                search_results = query_response.points
            else:
                search_results = client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=max(1, min(limit, 100)),
                    with_payload=True,
                )

            results = []
            for hit in search_results:
                payload = hit.payload or {}
                results.append({
                    "memory_id": payload.get("memory_id", str(hit.id)),
                    "content": payload.get("content", ""),
                    "memory_type": payload.get("memory_type", "note"),
                    "created_at": payload.get("created_at", ""),
                    "source_agent": payload.get("source_agent", "unknown"),
                    "workspace_id": payload.get("workspace_id", workspace_id),
                    "visibility": payload.get("visibility", "shared"),
                    "score": round(float(hit.score), 4),
                })
            return results
        except Exception as exc:
            if "connection" in str(exc).lower() or "timeout" in str(exc).lower():
                raise QdrantUnavailableError(f"Qdrant connection lost during search: {exc}") from exc
            raise QdrantServiceError(f"Failed to execute semantic search: {exc}") from exc

    def list_memories(
        self,
        workspace_id: str,
        limit: int = 20,
        memory_type: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists memories belonging to a specific workspace.
        """
        self.ensure_collection()
        client = self.get_client()

        if not workspace_id or not workspace_id.strip():
            raise ValueError("workspace_id is required to list memories.")

        must_conditions = [
            FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id.strip()))
        ]
        if memory_type and memory_type.strip():
            must_conditions.append(FieldCondition(key="memory_type", match=MatchValue(value=memory_type.strip())))
        if visibility and visibility.strip():
            must_conditions.append(FieldCondition(key="visibility", match=MatchValue(value=visibility.strip())))

        scroll_filter = Filter(must=must_conditions)

        try:
            points, _ = client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=max(1, min(limit, 100)),
                with_payload=True,
            )

            memories = []
            for pt in points:
                payload = pt.payload or {}
                memories.append({
                    "memory_id": payload.get("memory_id", str(pt.id)),
                    "content": payload.get("content", ""),
                    "memory_type": payload.get("memory_type", "note"),
                    "created_at": payload.get("created_at", ""),
                    "source_agent": payload.get("source_agent", "unknown"),
                    "workspace_id": payload.get("workspace_id", workspace_id),
                    "visibility": payload.get("visibility", "shared"),
                })
            return memories
        except Exception as exc:
            if "connection" in str(exc).lower() or "timeout" in str(exc).lower():
                raise QdrantUnavailableError(f"Qdrant connection lost while listing memories: {exc}") from exc
            raise QdrantServiceError(f"Failed to list memories: {exc}") from exc

    def delete_memory(self, memory_id: str, workspace_id: str) -> bool:
        """
        Deletes a specific memory record by ID, verifying that it belongs to workspace_id.
        Raises MemoryNotFoundError if not found or if workspace does not match.
        """
        self.ensure_collection()
        client = self.get_client()

        if not memory_id or not memory_id.strip():
            raise ValueError("memory_id cannot be empty.")
        if not workspace_id or not workspace_id.strip():
            raise ValueError("workspace_id cannot be empty.")

        clean_id = memory_id.strip()
        clean_workspace = workspace_id.strip()

        try:
            # 1. Verify existence and workspace isolation
            records = client.retrieve(
                collection_name=self.collection_name,
                ids=[clean_id],
                with_payload=True,
            )
            if not records:
                raise MemoryNotFoundError(clean_id, clean_workspace)

            record = records[0]
            payload = record.payload or {}
            if payload.get("workspace_id") != clean_workspace:
                # To prevent cross-workspace discovery, return 404
                raise MemoryNotFoundError(clean_id, clean_workspace)

            # 2. Perform deletion
            client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=[clean_id]),
            )
            return True
        except MemoryNotFoundError:
            raise
        except Exception as exc:
            if "connection" in str(exc).lower() or "timeout" in str(exc).lower():
                raise QdrantUnavailableError(f"Qdrant connection lost during deletion: {exc}") from exc
            raise QdrantServiceError(f"Failed to delete memory '{clean_id}': {exc}") from exc


# Global singleton instance
memory_service = QdrantMemoryService()
