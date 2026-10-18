"""Synthesize edge case: zero promoted sources gives an "insufficient evidence" synthesis."""

from collections.abc import Collection, Mapping
from typing import Any, cast

import pytest

from hannovators_deep_researcher.configuration.settings import ProviderMode, Settings
from hannovators_deep_researcher.models.enums import RecommendationDirection, SourceStatus
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.synthesize.stage import build_synthesis

pytestmark = pytest.mark.unit


class _NoSources:
    async def list_sources(
        self, workspace_id: str, statuses: Collection[SourceStatus] | None = None
    ) -> list[object]:
        return []


class _NoChat:
    async def complete_json(self, **kwargs: Any) -> Any:
        raise AssertionError("the model must not be called without evidence")


class _Context:
    workspace_id = "ws-00000000"
    app_settings = Settings(provider_mode=ProviderMode.FAKE)
    repositories = _NoSources()
    chat = _NoChat()

    def __init__(self) -> None:
        self.warnings: list[str] = []

    async def emit(
        self, kind: object, message: str, payload: Mapping[str, object] | None = None
    ) -> None:
        self.warnings.append(message)


async def test_zero_promoted_sources_gives_insufficient_evidence() -> None:
    ctx = _Context()

    synthesis = await build_synthesis(cast(StageContext, ctx))

    assert synthesis.pairwise_summaries == []
    assert synthesis.recommendation.direction == RecommendationDirection.NONE
    assert "Insufficient evidence" in synthesis.recommendation.text
    assert synthesis.provenance.canary.startswith("hdr-ws-00000")
    assert ctx.warnings
