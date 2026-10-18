"""Nebius adapter edge cases: JSON repair and Matryoshka truncation with query prefixes.

The OpenAI SDK runs on `httpx2`, which respx does not intercept, so the embedder gets a stub
SDK client at the same boundary.
"""

import math
from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from hannovators_deep_researcher.adapters.nebius import (
    NebiusEmbedder,
    parse_json_reply,
    require_all_properties,
)

pytestmark = pytest.mark.unit


class _Answer(BaseModel):
    verdict: str


class _Item(BaseModel):
    name: str
    note: str | None = None


class _Reply(BaseModel):
    items: list[_Item] = []
    summary: str = ""


def test_schema_marks_defaulted_and_nested_fields_required() -> None:
    schema = require_all_properties(_Reply.model_json_schema())
    assert set(schema["required"]) == {"items", "summary"}
    assert set(schema["$defs"]["_Item"]["required"]) == {"name", "note"}
    assert _Reply.model_validate({}).items == []


class _StubEmbeddings:
    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

    async def create(self, *, model: str, input: list[str], dimensions: int) -> Any:
        self.inputs.append(input)
        data = [SimpleNamespace(index=i, embedding=[1.0] * 4096) for i in range(len(input))]
        return SimpleNamespace(data=data)


def test_fenced_json_is_parsed_and_truncated_json_fails_clearly() -> None:
    assert parse_json_reply(_Answer, '```json\n{"verdict": "ok"}\n```').verdict == "ok"
    with pytest.raises(ValidationError):
        parse_json_reply(_Answer, '{"verdict": "o')


async def test_long_vectors_are_truncated_renormalized_and_prefixed_only_for_queries() -> None:
    stub = _StubEmbeddings()
    client = cast(AsyncOpenAI, SimpleNamespace(embeddings=stub))
    embedder = NebiusEmbedder(client, model="m", dimensions=1024)

    assert await embedder.embed([]) == []
    assert stub.inputs == []
    vectors = await embedder.embed(["a doc"])
    await embedder.embed(["a query"], instruction="Find trials")

    assert len(vectors[0]) == 1024
    assert math.isclose(sum(value * value for value in vectors[0]), 1.0, rel_tol=1e-6)
    assert stub.inputs == [["a doc"], ["Instruct: Find trials\nQuery: a query"]]
