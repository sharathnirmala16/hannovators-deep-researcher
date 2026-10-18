"""Edge cases for the fake Jev decision model."""

import pytest

from hannovators_deep_researcher.adapters.fake.decisions import FakeDecisionModel
from hannovators_deep_researcher.models.decisions import DecisionQuestion
from hannovators_deep_researcher.models.enums import DecisionQuestionType

pytestmark = pytest.mark.unit

QUESTIONS = {
    "relevance": DecisionQuestion(
        type=DecisionQuestionType.SCORE,
        instructions="How relevant is the record?",
        criteria=["none", "low", "some", "high", "exact"],
    ),
    "population_ok": DecisionQuestion(
        type=DecisionQuestionType.NOUL, instructions="Is the population eligible?"
    ),
    "exclusion": DecisionQuestion(
        type=DecisionQuestionType.CHOICE,
        instructions="Main exclusion reason?",
        criteria={"NONE": None, "ANIMAL_STUDY": "Animals only", "OFF_TOPIC": None},
    ),
}


async def test_same_input_gives_the_same_answers() -> None:
    state = "Dapagliflozin versus placebo in heart failure with reduced ejection fraction"

    first = await FakeDecisionModel().evaluate(state, QUESTIONS)
    second = await FakeDecisionModel().evaluate(state, QUESTIONS)

    assert first == second


async def test_every_choice_answer_is_one_of_the_given_options() -> None:
    options = [f"OPTION_{index}" for index in range(20)]
    question = DecisionQuestion(
        type=DecisionQuestionType.CHOICE,
        instructions="Pick one.",
        criteria=dict.fromkeys(options),
    )
    model = FakeDecisionModel()

    answers = [
        (await model.evaluate(f"candidate {index}", {"pick": question}))["pick"]
        for index in range(200)
    ]

    assert all(answer.choice in options for answer in answers)
    assert all(set(answer.probabilities) == set(options) for answer in answers)
    assert len({answer.choice for answer in answers}) > 1
