"""Live Nebius checks. One small request each; skipped when NEBIUS_API_KEY is missing."""

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import BaseModel

from hannovators_deep_researcher.adapters.nebius import build_chat_model, build_embedder
from hannovators_deep_researcher.configuration.settings import Settings, get_settings
from hannovators_deep_researcher.infrastructure.http import create_http_client
from hannovators_deep_researcher.models.enums import ModelRole

pytestmark = pytest.mark.live


class _Capital(BaseModel):
    city: str


@pytest.fixture
def settings() -> Settings:
    settings = get_settings()
    if settings.nebius_api_key is None:
        pytest.skip("NEBIUS_API_KEY is not set")
    return settings


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with create_http_client(timeout=120.0) as client:
        yield client


async def test_nemotron_json_completion(settings: Settings, http: httpx.AsyncClient) -> None:
    chat = build_chat_model(settings, http)
    answer = await chat.complete_json(
        role=ModelRole.QUERY,
        system="Answer in JSON.",
        user="What is the capital of France?",
        schema=_Capital,
    )
    assert "paris" in answer.city.lower()


async def test_qwen_embedding_dimensions(settings: Settings, http: httpx.AsyncClient) -> None:
    vectors = await build_embedder(settings, http).embed(["aspirin", "heart attack"])
    assert [len(vector) for vector in vectors] == [settings.embedding_dimensions] * 2
