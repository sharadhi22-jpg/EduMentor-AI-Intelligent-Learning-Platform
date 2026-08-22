"""
In-memory cosine similarity and nearest-neighbor vector retrieval operations.

Embeddings are stored per-chunk as JSON float arrays directly on
DocumentChunk rows (see app.models.document). For this project's scale
(a student's own course documents) a full DB/library-backed vector index
is overkill — brute-force cosine similarity over a subject's chunks is
fast enough and keeps the stack dependency-free.
"""
import math


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def top_k_chunks(query_embedding: list[float], chunks: list, k: int = 5) -> list[tuple]:
    """
    Rank a list of DocumentChunk-like objects (must expose `.embedding`) against
    a query embedding and return the top-k as (chunk, score) tuples, highest
    similarity first. Chunks with no embedding (score 0) are naturally pushed
    to the bottom and excluded once real matches exist.
    """
    if not query_embedding or not chunks:
        return []

    scored = [(chunk, cosine_similarity(query_embedding, chunk.embedding)) for chunk in chunks]
    scored = [pair for pair in scored if pair[1] > 0.0]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]
