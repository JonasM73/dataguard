"""Configuration de l'application, lue dans l'environnement.

Aucune valeur sensible n'est écrite en dur : `.env.example` documente les clés,
`.env` n'est jamais versionné.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    env: str = Field("local", alias="DATAGUARD_ENV")
    log_level: str = Field("INFO", alias="DATAGUARD_LOG_LEVEL")

    postgres_user: str = Field("dataguard", alias="POSTGRES_USER")
    postgres_password: str = Field("dataguard", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field("dataguard", alias="POSTGRES_DB")
    postgres_host: str = Field("localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    cors_origins: str = Field("http://localhost:5173", alias="DATAGUARD_CORS_ORIGINS")

    # Un fichier plus gros que cette limite est refusé avant d'être lu : le MVP
    # travaille en mémoire et ne prétend pas traiter des volumes arbitraires.
    max_download_bytes: int = Field(52_428_800, alias="DATAGUARD_MAX_DOWNLOAD_BYTES")
    raw_dir: Path = Field(Path("data/raw"), alias="DATAGUARD_RAW_DIR")

    otel_exporter: str = Field("console", alias="DATAGUARD_OTEL_EXPORTER")

    @field_validator("otel_exporter")
    @classmethod
    def _known_exporter(cls, value: str) -> str:
        allowed = {"console", "none", "otlp"}
        if value not in allowed:
            raise ValueError(f"DATAGUARD_OTEL_EXPORTER doit valoir l'un de {sorted(allowed)}")
        return value

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
