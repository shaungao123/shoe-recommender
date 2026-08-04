"""Shared settings — DB URL, embedding model id, etc."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./shoe_recommender.db"
    embedding_model_id: str = "text-embedding-3-small"
    # Chat model for recommendation explanations (generation stage).
    llm_model_id: str = "gpt-4o-mini"
    # OpenAI key for embeddings (index + query) and LLM explanations.
    openai_api_key: str = ""
    # Browser origins allowed to call the API (CORS). Frontend dev server by default.
    cors_allow_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3(cls, url: str) -> str:
        # bare postgresql:// selects psycopg2; this project ships psycopg 3
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


settings = Settings()
