"""Edge case for the fake agent model."""

import pytest
from pydantic import BaseModel

from hannovators_deep_researcher.adapters.fake.chat import FakeChatModel, FakeExampleMissingError
from hannovators_deep_researcher.models.enums import ModelRole

pytestmark = pytest.mark.unit


class _SchemaWithoutExample(BaseModel):
    answer: str


async def test_schema_without_fake_example_raises_a_clear_error() -> None:
    with pytest.raises(FakeExampleMissingError, match=r"_SchemaWithoutExample has no fake_example"):
        await FakeChatModel().complete_json(
            role=ModelRole.DECOMPOSE, system="s", user="u", schema=_SchemaWithoutExample
        )
