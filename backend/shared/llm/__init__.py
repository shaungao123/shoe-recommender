"""Shared LLM client — structured chat completions for generation."""

from shared.llm.client import LLMClient, LLMError, get_llm_client

__all__ = ["LLMClient", "LLMError", "get_llm_client"]
