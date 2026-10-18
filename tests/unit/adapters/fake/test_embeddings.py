"""Edge cases for the fake embedder."""

import math

import pytest

from hannovators_deep_researcher.adapters.fake.embeddings import FakeEmbedder

pytestmark = pytest.mark.unit


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


async def test_similar_texts_score_higher_than_unrelated_texts() -> None:
    query, similar, unrelated = await FakeEmbedder().embed(
        [
            "SGLT2 inhibitors and heart failure hospitalization",
            "Dapagliflozin, an SGLT2 inhibitor, reduced hospitalization for heart failure",
            "Sodium-ion battery cells for grid storage",
        ],
        instruction="Retrieve trial results that answer the question",
    )

    assert _dot(query, similar) > _dot(query, unrelated)


async def test_every_vector_has_unit_norm_and_the_configured_length() -> None:
    texts = ["", "!!! ???", "the and of", "heart", "heart heart failure " * 50]

    vectors = await FakeEmbedder(dimensions=64).embed(texts)

    assert all(len(vector) == 64 for vector in vectors)
    assert all(math.isclose(math.sqrt(_dot(v, v)), 1.0, rel_tol=1e-9) for v in vectors)
