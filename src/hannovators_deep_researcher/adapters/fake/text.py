"""Tokenizer shared by the fake embedder and the fake search scoring."""

import re

_FIELD_TAG = re.compile(r"\[[^\]]*\]")
_WORD = re.compile(r"[a-z0-9]+")
_MIN_STEM_LENGTH = 4

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "its",
        "not",
        "of",
        "on",
        "or",
        "than",
        "that",
        "the",
        "this",
        "to",
        "vs",
        "was",
        "were",
        "with",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens without stopwords or PubMed field tags such as `[tiab]`.

    A trailing plural `s` is dropped, so "inhibitors" matches "inhibitor".
    """

    words = _WORD.findall(_FIELD_TAG.sub(" ", text.lower()))
    return [_stem(word) for word in words if word not in STOPWORDS]


def _stem(word: str) -> str:
    if len(word) >= _MIN_STEM_LENGTH and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word
