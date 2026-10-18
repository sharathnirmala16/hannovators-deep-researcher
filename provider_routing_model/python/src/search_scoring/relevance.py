"""Rank-discounted top-k relevance of one provider response against a private gold answer.

R(i, p) = wA * AnsHit + wU * URLHit + wD * DomHit, each hit = max_r 1/log2(1 + r).
Answers too short to match safely in free text ("1", "A", "for") are uninformative: their
query is scored on URL and domain evidence only, with those weights renormalized to one.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

from search_urls.models import SearchResult

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-")
_ARROWS = re.compile(r"\s*(?:\u21d2|\u2192|\u27f6|=>|->)\s*")
_CURRENCY_SPACE = re.compile(r"([$\u20ac\u00a3\u00a5])\s+")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_WORD = re.compile(r"[a-z]+")
_SPACE = re.compile(r"\s+")
_STOPWORDS = frozenset({"a", "an", "and", "for", "in", "of", "on", "or", "the", "to", "with"})
_TEXT_METADATA_KEYS = ("highlights", "excerpts", "extra_snippets", "description")
_TRACKING_PARAMS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"})
_MULTIPART_SUFFIXES = frozenset(
    {"co.uk", "org.uk", "gov.uk", "ac.uk", "com.au", "gov.au", "co.jp", "co.in", "com.br"}
)
_MAX_TEXT_CHARS = 60_000
_NUMBER_WINDOW = 200


@dataclass(frozen=True, slots=True)
class RelevanceWeights:
    answer: float = 0.50
    url: float = 0.35
    domain: float = 0.15


DEFAULT_WEIGHTS = RelevanceWeights()


@dataclass(frozen=True, slots=True)
class AnswerProfile:
    text: str
    numbers: frozenset[Decimal]
    digit_count: int
    informative: bool
    numeric_match: bool


@dataclass(frozen=True, slots=True)
class Relevance:
    answer_hit: float | None
    url_hit: float
    domain_hit: float
    score: float
    answer_rank: int | None
    url_rank: int | None


def _repair_mojibake(text: str) -> str:
    if not any(marker in text for marker in ("\u00e2", "\u00c3", "\u00c2")):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def normalize_text(text: str) -> str:
    """Casefold and canonicalize dashes, arrows, currency spacing, and thousands separators."""
    text = unicodedata.normalize("NFKC", _repair_mojibake(text)).translate(_DASHES).casefold()
    text = _ARROWS.sub(" => ", text)
    text = _CURRENCY_SPACE.sub(r"\1", text)
    text = _THOUSANDS.sub("", text)
    return _SPACE.sub(" ", text).strip()


def _numbers(text: str) -> frozenset[Decimal]:
    values: set[Decimal] = set()
    for token in _NUMBER.findall(text):
        try:
            values.add(Decimal(token))
        except InvalidOperation:
            continue
    return frozenset(values)


def _significant_digits(token: str) -> int:
    whole, _, fraction = token.partition(".")
    return len(whole.lstrip("0")) + len(fraction.rstrip("0"))


def answer_profile(answer: str) -> AnswerProfile:
    """Normalize a gold answer and decide whether free-text matching is trustworthy."""
    text = normalize_text(answer).strip(" .;:,")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"`":
        text = text[1:-1].strip()
    digits = [_significant_digits(token) for token in _NUMBER.findall(text)]
    digit_count = sum(digits)
    alpha_chars = sum(
        len(word) for word in _WORD.findall(text) if len(word) >= 2 and word not in _STOPWORDS
    )
    informative = digit_count >= 3 or alpha_chars >= 4 or (digit_count >= 1 and alpha_chars >= 2)
    # Number-only matching needs every number to be specific (e.g. not the "02" in "2027-02").
    # Identifiers such as "ms17-010" or "gpio2" must match as text, not as loose numbers.
    numeric_match = (
        digit_count >= 3 and bool(digits) and min(digits) >= 2 and not re.search(r"[a-z]\d", text)
    )
    return AnswerProfile(text, _numbers(text), digit_count, informative, numeric_match)


def result_text(result: SearchResult) -> str:
    """All provider-returned text for one result: title, snippet, content, and highlights."""
    parts = [result.title, result.snippet, result.content, result.summary, result.markdown]
    for key in _TEXT_METADATA_KEYS:
        value = result.metadata.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(item for item in value if isinstance(item, str))
    return normalize_text(" ".join(part for part in parts if part))[:_MAX_TEXT_CHARS]


def _numbers_near(numbers: frozenset[Decimal], text: str) -> bool:
    """Every answer number occurs within one window of `_NUMBER_WINDOW` characters."""
    positions: dict[Decimal, list[int]] = {number: [] for number in numbers}
    for match in _NUMBER.finditer(text):
        try:
            value = Decimal(match.group(0))
        except InvalidOperation:
            continue
        if value in positions:
            positions[value].append(match.start())
    if any(not found for found in positions.values()):
        return False
    anchor_value = min(positions, key=lambda value: len(positions[value]))
    return any(
        all(
            any(abs(position - anchor) <= _NUMBER_WINDOW for position in found)
            for found in positions.values()
        )
        for anchor in positions[anchor_value]
    )


def answer_in_text(profile: AnswerProfile, text: str) -> bool:
    """Exact normalized phrase, or all specific answer numbers close together in the text."""
    if not profile.text:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(profile.text) + r"(?![a-z0-9])"
    if re.search(pattern, text):
        return True
    return profile.numeric_match and _numbers_near(profile.numbers, text)


def canonical_url(url: str) -> str:
    """Scheme-, www-, case-, trailing-slash-, fragment-, and tracking-insensitive URL key."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").casefold().removeprefix("www.")
    path = unquote(parts.path).rstrip("/").casefold()
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_PARAMS
    )
    return host + path + ("?" + urlencode(query) if query else "")


def registrable_domain(url: str) -> str:
    labels = (urlsplit(url.strip()).hostname or "").casefold().removeprefix("www.").split(".")
    take = 3 if ".".join(labels[-2:]) in _MULTIPART_SUFFIXES else 2
    return ".".join(labels[-take:])


def rank_discount(rank: int) -> float:
    return 1.0 / math.log2(1 + rank)


def _best_hit(hits: Iterable[tuple[int, bool]]) -> tuple[float, int | None]:
    ranks = [rank for rank, hit in hits if hit]
    best = min(ranks, default=None)
    return (rank_discount(best) if best is not None else 0.0), best


def score_response(
    results: Sequence[SearchResult],
    answer: str,
    gold_urls: Sequence[str],
    *,
    k: int = 5,
    weights: RelevanceWeights = DEFAULT_WEIGHTS,
) -> Relevance:
    """Score the top-k results; an empty result list scores zero on every component."""
    profile = answer_profile(answer)
    gold_keys = {canonical_url(url) for url in gold_urls}
    gold_domains = {registrable_domain(url) for url in gold_urls}
    top = [(result.rank or index + 1, result) for index, result in enumerate(results[:k])]
    url_hit, url_rank = _best_hit((rank, canonical_url(r.url) in gold_keys) for rank, r in top)
    domain_hit, _ = _best_hit((rank, registrable_domain(r.url) in gold_domains) for rank, r in top)
    if profile.informative:
        answer_hit, answer_rank = _best_hit(
            (rank, answer_in_text(profile, result_text(r))) for rank, r in top
        )
        score = weights.answer * answer_hit + weights.url * url_hit + weights.domain * domain_hit
        return Relevance(answer_hit, url_hit, domain_hit, score, answer_rank, url_rank)
    evidence_weight = weights.url + weights.domain
    score = (weights.url * url_hit + weights.domain * domain_hit) / evidence_weight
    return Relevance(None, url_hit, domain_hit, score, None, url_rank)
