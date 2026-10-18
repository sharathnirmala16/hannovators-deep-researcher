"""Fake embedder: signed hashed bag-of-words vectors, so texts that share words score higher."""

import hashlib
import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from hannovators_deep_researcher.adapters.fake.text import tokenize
from hannovators_deep_researcher.models.contracts import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    MAX_EMBEDDING_DIMENSIONS,
    MIN_EMBEDDING_DIMENSIONS,
)

if TYPE_CHECKING:
    from hannovators_deep_researcher.models.ports import Embedder

FAKE_EMBEDDING_MODEL = "fake/hashed-bag-of-words"


class FakeEmbedder:
    """L2-normalized vectors of length `dimensions`.

    The instruction is ignored, so query and document vectors of the same words compare
    directly. A text without tokens maps to the first basis vector.
    """

    def __init__(self, dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS) -> None:
        if not MIN_EMBEDDING_DIMENSIONS <= dimensions <= MAX_EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"dimensions must be {MIN_EMBEDDING_DIMENSIONS} to {MAX_EMBEDDING_DIMENSIONS}, "
                f"got {dimensions}"
            )
        self.model = FAKE_EMBEDDING_MODEL
        self.dimensions = dimensions

    async def embed(
        self, texts: Sequence[str], *, instruction: str | None = None
    ) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            value = int.from_bytes(digest)
            vector[value % self.dimensions] += 1.0 if value >> 63 else -1.0
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            vector[0] = 1.0
            return vector
        return [component / norm for component in vector]


if TYPE_CHECKING:
    _embedder: Embedder = FakeEmbedder()
