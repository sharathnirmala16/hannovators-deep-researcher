"""Fake agent model: every response schema supplies its own canned answer."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel

from hannovators_deep_researcher.models.enums import ModelRole

if TYPE_CHECKING:
    from hannovators_deep_researcher.models.ports import ChatModel


class FakeExampleMissingError(LookupError):
    """The response schema has no `fake_example()` classmethod, so fake mode cannot answer."""

    def __init__(self, schema: type[BaseModel]) -> None:
        super().__init__(
            f"{schema.__module__}.{schema.__qualname__} has no fake_example() classmethod; "
            "add one to the schema so PROVIDER_MODE=fake can answer"
        )
        self.schema = schema


class FakeChatModel:
    """Returns `schema.fake_example()`, validated as `schema`. Prompts and images are ignored."""

    async def complete_json[T: BaseModel](
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        schema: type[T],
        images: Sequence[bytes] = (),
    ) -> T:
        fake_example = getattr(schema, "fake_example", None)
        if not callable(fake_example):
            raise FakeExampleMissingError(schema)
        return schema.model_validate(fake_example())


if TYPE_CHECKING:
    _chat_model: ChatModel = FakeChatModel()
