"""BM25 (Okapi) over chunk texts with a small English stopword list."""

import re
from collections.abc import Sequence

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

_TOKEN = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")
_STOPWORD_TEXT = """a an and are as at be been being but by can could did do does for from had
has have how if in into is it its may might more most no not of on or our should such than that
the their them then there these they this those to was we were what when where whether which
while who whom why will with without would you your"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(text.lower()) if token not in _STOPWORDS]


def bm25_scores(query: str, documents: Sequence[str]) -> list[float]:
    """One BM25 score per document; all zeros when the query or the corpus has no tokens."""

    query_tokens = tokenize(query)
    corpus = [tokenize(document) for document in documents]
    if not query_tokens or not any(corpus):
        return [0.0] * len(documents)
    scores = BM25Okapi([tokens or ["\x00"] for tokens in corpus]).get_scores(query_tokens)
    return [float(score) for score in scores]
