"""Web search and fetch shapes shared by the web router and the provider adapters."""

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel, NonEmptyText, Probability
from hannovators_deep_researcher.models.enums import ProviderAttemptStatus


class WebSearchRequest(ContractModel):
    query: NonEmptyText
    limit: int = Field(default=10, ge=1, le=100)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    days: int | None = Field(default=None, ge=1)


class SearchResult(ContractModel):
    """One hit. `published_at` is the provider's date string (ISO 8601 when available)."""

    title: str
    url: str
    snippet: str = ""
    published_at: str | None = None
    score: Probability | None = None
    provider: str


class ProviderError(ContractModel):
    """A provider failure mapped to one shape, so routers can decide on failover."""

    provider: str
    code: str
    message: str
    retryable: bool = False
    status_code: int | None = None


class ProviderFailure(Exception):
    """Raised by adapters and routers. Carries the mapped `ProviderError`."""

    def __init__(self, error: ProviderError) -> None:
        super().__init__(f"{error.provider}: {error.code}: {error.message}")
        self.error = error


class ProviderAttempt(ContractModel):
    provider: str
    status: ProviderAttemptStatus
    latency_ms: int | None = Field(default=None, ge=0)
    error: ProviderError | None = None


class WebSearchResponse(ContractModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    provider: str
    attempts: list[ProviderAttempt] = Field(default_factory=list)


class FetchedDocument(ContractModel):
    """Extracted page content. `content` is markdown or plain text."""

    url: str
    title: str | None = None
    content: str
    content_type: str
    provider: str
