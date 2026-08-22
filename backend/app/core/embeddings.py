"""
Embeddings generation service.

Thin orchestration layer on top of app.core.gemini's embed_texts/embed_query.
Batches large chunk lists to stay under the Gemini API's per-request item
limit, and degrades gracefully (returns empty vectors + logs a warning)
when no GEMINI_API_KEY is configured, so document upload and other flows
never hard-fail just because embeddings aren't available yet.
"""
import logging

from app.core import gemini

logger = logging.getLogger(__name__)

# Gemini's embed_content endpoint accepts a bounded number of texts per call.
_BATCH_SIZE = 100


def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of document chunk texts for storage.
    Returns a list of vectors (or empty lists per-item if embeddings are
    unavailable), always the same length as `texts`.
    """
    if not texts:
        return []

    if not gemini.is_configured():
        logger.warning(
            "GEMINI_API_KEY not set — storing %d chunk(s) without embeddings. "
            "Semantic search/chat will be degraded until a key is added and "
            "the document is re-uploaded.",
            len(texts),
        )
        return [[] for _ in texts]

    vectors: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        try:
            vectors.extend(gemini.embed_texts(batch, task_type="RETRIEVAL_DOCUMENT"))
        except gemini.GeminiError as e:
            logger.error("Embedding batch failed (%d items): %s", len(batch), e)
            vectors.extend([[] for _ in batch])
    return vectors


def embed_query(text: str) -> list[float]:
    """
    Embed a single query string (e.g. a chat message) for similarity search.
    Returns an empty list if embeddings are unavailable.
    """
    if not text or not gemini.is_configured():
        return []
    try:
        return gemini.embed_query(text)
    except gemini.GeminiError as e:
        logger.error("Query embedding failed: %s", e)
        return []
