"""Live Jev check. One small request; skipped when JEV_API_KEY is missing."""

import pytest

from hannovators_deep_researcher.adapters.jev import build_decision_model
from hannovators_deep_researcher.configuration.settings import get_settings
from hannovators_deep_researcher.infrastructure.http import create_http_client
from hannovators_deep_researcher.models.decisions import DecisionQuestion
from hannovators_deep_researcher.models.enums import DecisionQuestionType

pytestmark = pytest.mark.live


async def test_jev_choice_score_and_noul() -> None:
    settings = get_settings()
    if settings.jev_api_key is None:
        pytest.skip("JEV_API_KEY is not set")
    questions = {
        "team": DecisionQuestion(
            type=DecisionQuestionType.CHOICE,
            instructions="Which team should handle it?",
            criteria={"billing": "payments", "shipping": "delivery"},
        ),
        "anger": DecisionQuestion(
            type=DecisionQuestionType.SCORE,
            instructions="How frustrated is the customer?",
            criteria=["calm", "frustrated", "angry"],
        ),
        "urgent": DecisionQuestion(
            type=DecisionQuestionType.NOUL, instructions="Does this need urgent attention?"
        ),
    }
    async with create_http_client() as http:
        answers = await build_decision_model(settings, http).evaluate(
            "My card payment failed three times today.", questions
        )

    assert answers["team"].choice == "billing"
    assert answers["anger"].score is not None
    assert answers["urgent"].noul is not None
