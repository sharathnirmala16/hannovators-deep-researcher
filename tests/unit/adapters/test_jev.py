"""Jev adapter edge cases: 429 with Retry-After, truncation, and missing answer keys."""

import asyncio
import json

import httpx
import pytest
import respx
from pydantic import SecretStr

from hannovators_deep_researcher.adapters.jev import build_decision_model
from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.models.decisions import DecisionQuestion
from hannovators_deep_researcher.models.enums import DecisionQuestionType
from hannovators_deep_researcher.models.web import ProviderFailure

pytestmark = pytest.mark.unit

URL = "https://jev.test/v1/systemone"
QUESTIONS = {"keep": DecisionQuestion(type=DecisionQuestionType.NOUL, instructions="Keep it?")}


def _settings() -> Settings:
    return Settings(
        jev_api_key=SecretStr("test"), jev_base_url="https://jev.test/v1", jev_max_state_tokens=10
    )


@respx.mock
async def test_429_honors_retry_after_and_long_state_is_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, json={"answers": {"keep": {"type": "noul", "noul": 0.5}}}),
        ]
    )
    async with httpx.AsyncClient() as http:
        answers = await build_decision_model(_settings(), http).evaluate("x" * 500, QUESTIONS)

    assert answers["keep"].noul == 0.5
    assert delays == [3.0]
    assert len(json.loads(route.calls[-1].request.content)["state"]) == 40


@respx.mock
async def test_missing_answer_key_raises_typed_error() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"answers": {}}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(ProviderFailure, match="missing answers: keep"):
            await build_decision_model(_settings(), http).evaluate("state", QUESTIONS)
