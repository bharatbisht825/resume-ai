from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    database_user: str = "postgres"
    database_password: str = "postgres"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "resume_ai"
    database_echo: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            if self.database_url.startswith("postgres://"):
                return self.database_url.replace(
                    "postgres://", "postgresql+asyncpg://", 1
                )
            return self.database_url
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        return (
            f"postgresql+asyncpg://{user}:{password}@"
            f"{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def database_configured(self) -> bool:
        return bool(
            self.database_url
            or any(
                os.getenv(name)
                for name in (
                    "DATABASE_USER",
                    "DATABASE_PASSWORD",
                    "DATABASE_HOST",
                    "DATABASE_PORT",
                    "DATABASE_NAME",
                )
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
