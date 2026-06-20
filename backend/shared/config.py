"""Shared settings — DB URL, embedding model id, etc."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./shoe_recommender.db"
    embedding_model_id: str = "text-embedding-3-small"


settings = Settings()
