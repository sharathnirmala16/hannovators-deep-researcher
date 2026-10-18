"""Application settings from the environment and the root `.env` (PLAN.md section 6)."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from hannovators_deep_researcher.configuration.database import project_root
from hannovators_deep_researcher.models.contracts import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    DEFAULT_EMBEDDING_MODEL,
    MAX_EMBEDDING_DIMENSIONS,
    MIN_EMBEDDING_DIMENSIONS,
)
from hannovators_deep_researcher.models.enums import ModelRole

AUTO_WEB_SEARCH_PROVIDER = "auto"


class ProviderMode(StrEnum):
    REAL = "real"
    FAKE = "fake"


class Settings(BaseSettings):
    """Process settings. The shell environment wins over `.env`; empty values count as unset.

    Secrets are `SecretStr`, so they never print in reprs or logs.
    """

    model_config = SettingsConfigDict(
        env_file=project_root() / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    provider_mode: ProviderMode = ProviderMode.REAL

    api_host: str = "127.0.0.1"
    api_port: int | None = Field(default=None, ge=1, le=65535)
    vite_port: int | None = Field(default=None, ge=1, le=65535)

    nebius_api_key: SecretStr | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    agent_model: str = "nvidia/Nemotron-3.5-Super-VL"
    model_decompose: str | None = None
    model_query: str | None = None
    model_appraise: str | None = None
    model_extract_vision: str | None = None
    model_synthesize: str | None = None
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_dimensions: int = Field(
        default=DEFAULT_EMBEDDING_DIMENSIONS,
        ge=MIN_EMBEDDING_DIMENSIONS,
        le=MAX_EMBEDDING_DIMENSIONS,
    )

    jev_api_key: SecretStr | None = None
    jev_base_url: str = "https://api.commandcode.ai/provider/v1"
    jev_model: str = "typesafe/jev-1.14.0"
    jev_concurrency: int = Field(default=8, ge=1)
    jev_max_state_tokens: int = Field(default=24_000, ge=1, le=32_000)

    web_search_provider: str = AUTO_WEB_SEARCH_PROVIDER
    web_search_priority: Annotated[tuple[str, ...], NoDecode] = ("tavily", "exa")
    tavily_api_key: SecretStr | None = None
    exa_api_key: SecretStr | None = None

    ncbi_api_key: SecretStr | None = None
    ncbi_email: str | None = None

    run_budget_max_candidates: int = Field(default=100, ge=1)

    @field_validator("web_search_provider")
    @classmethod
    def _normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("web_search_priority", mode="before")
    @classmethod
    def _split_priority(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list | tuple):
            names = tuple(str(name).strip().lower() for name in value if str(name).strip())
            if not names:
                raise ValueError("WEB_SEARCH_PRIORITY must name at least one provider")
            return names
        return value

    def model_for(self, role: ModelRole) -> str:
        """Return the model ID for a role: its MODEL_<ROLE> override, else AGENT_MODEL."""

        overrides = {
            ModelRole.DECOMPOSE: self.model_decompose,
            ModelRole.QUERY: self.model_query,
            ModelRole.APPRAISE: self.model_appraise,
            ModelRole.EXTRACT_VISION: self.model_extract_vision,
            ModelRole.SYNTHESIZE: self.model_synthesize,
        }
        return overrides[role] or self.agent_model

    def require_api_port(self) -> int:
        """Return API_PORT, or stop with a clear error. There is no numeric fallback."""

        if self.api_port is None:
            raise RuntimeError(
                "API_PORT is not set. Set it in the root .env (see the port table in AGENTS.md)."
            )
        return self.api_port


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once."""

    return Settings()
