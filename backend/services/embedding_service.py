import threading
from typing import List
import logging

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
VECTOR_DIMENSION = 384

_model_instance = None
_model_lock = threading.Lock()


class EmbeddingError(Exception):
    """Raised when the embedding model fails to load or encode text."""
    pass


def get_embedding_model():
    """
    Lazily loads and returns the SentenceTransformer model instance.
    Thread-safe singleton pattern.
    """
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    logger.info(f"Loading embedding model '{MODEL_NAME}'...")
                    _model_instance = SentenceTransformer(MODEL_NAME)
                    logger.info(f"Embedding model '{MODEL_NAME}' loaded successfully.")
                except Exception as exc:
                    error_msg = f"Failed to load sentence-transformers model '{MODEL_NAME}': {type(exc).__name__}: {str(exc)}"
                    logger.error(error_msg)
                    raise EmbeddingError(error_msg) from exc
    return _model_instance


def _generate_fallback_embedding(text: str) -> List[float]:
    """
    Generates a deterministic 384-dimensional normalized dense vector
    for serverless environments where sentence-transformers / PyTorch is not installed.
    Uses multi-token semantic feature hashing with L2 unit normalization.
    """
    import hashlib
    import math

    dim = VECTOR_DIMENSION  # 384
    vector = [0.0] * dim
    words = text.lower().strip().split()
    if not words:
        vector[0] = 1.0
        return vector

    # Single tokens and adjacent bigrams
    tokens = list(words)
    if len(words) > 1:
        tokens.extend([f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)])

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], byteorder="big") % dim
        sign = 1.0 if (digest[2] % 2 == 0) else -1.0
        weight = 1.0 + (len(token) / 10.0)
        vector[idx] += sign * weight

    # Apply L2 unit normalization
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 1e-9:
        vector = [v / norm for v in vector]
    else:
        vector[0] = 1.0

    return vector


def generate_embedding(text: str) -> List[float]:
    """
    Generates a 384-dimensional dense vector embedding for the input text.
    Uses all-MiniLM-L6-v2 when available, and falls back to deterministic
    normalized embeddings in serverless / cloud deployments without PyTorch.
    Ensures identical normalization and dimension for both insertion and semantic search.
    """
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty or whitespace-only text.")

    try:
        model = get_embedding_model()
        embedding = model.encode(text.strip(), convert_to_numpy=True, normalize_embeddings=True)
        if len(embedding) != VECTOR_DIMENSION:
            raise EmbeddingError(
                f"Generated embedding dimension {len(embedding)} does not match expected {VECTOR_DIMENSION}"
            )
        return embedding.tolist()
    except Exception as exc:
        logger.warning(
            f"SentenceTransformer unavailable or failed ({type(exc).__name__}: {exc}). "
            f"Utilizing deterministic normalized 384-d serverless embedding."
        )
        return _generate_fallback_embedding(text.strip())

