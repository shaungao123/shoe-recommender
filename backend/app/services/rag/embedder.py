"""Query-time embedding via shared embedding client.

Goes through ``shared/embedding`` so the query uses the exact model the corpus
was indexed with (``settings.embedding_model_id``).
"""

from shared.embedding import EmbeddingClient, get_embedding_client


def embed_query(text: str, client: EmbeddingClient | None = None) -> list[float]:
    """Embed one user query string; raises EmbeddingError on API failure."""
    client = client or get_embedding_client()
    return client.embed_one(text)
