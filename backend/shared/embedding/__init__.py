"""Shared embedding client — same model at index time and query time."""

from shared.embedding.client import EmbeddingClient, EmbeddingError, get_embedding_client

__all__ = ["EmbeddingClient", "EmbeddingError", "get_embedding_client"]
