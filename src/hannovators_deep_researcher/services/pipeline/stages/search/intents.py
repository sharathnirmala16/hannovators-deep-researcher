"""Per-intent query planning: fallback templates, query variants, and web query text.

Every run searches CORE plus NEGATIVE, ALTERNATIVE, and SAFETY. When the model gives no query
for an intent, a template from the decomposition fills the gap, so disconfirming searches never
silently drop out.
"""

import re
from dataclasses import dataclass, field

from hannovators_deep_researcher.models.contracts import PicotsDecomposition, ScopeDecomposition
from hannovators_deep_researcher.models.enums import SearchIntent
from hannovators_deep_researcher.services.pipeline.stages.search.medical import (
    REGISTRY_DOMAINS,
    REGULATOR_DOMAINS,
    Variant,
)

MAX_PER_INTENT = {
    SearchIntent.CORE: 4,
    SearchIntent.NEGATIVE: 3,
    SearchIntent.ALTERNATIVE: 3,
    SearchIntent.SAFETY: 2,
}
MIN_CORE = 2
PLACEBO_LIKE = re.compile(r"placebo|no treatment|usual care|standard of care|sham", re.I)
_PUBMED_TAG = re.compile(r"\[[^\]]*\]")
_BOOLEAN = re.compile(r"\b(?:AND|OR|NOT)\b")
_PUNCT = re.compile(r"[()\"*]")

Decomposition = PicotsDecomposition | ScopeDecomposition


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """One query to run. `variant` names the PubMed filter; web specs use `domains`."""

    intent: SearchIntent
    query: str
    tool: str  # "pubmed" or "web"
    variant: Variant = Variant.NONE
    limit: int = 10
    domains: tuple[str, ...] = field(default=())

    @property
    def label(self) -> str:
        scope = f" site:{','.join(self.domains)}" if self.domains else ""
        return f"intent:{self.intent} variant:{self.variant}{scope}"


def unique(queries: list[str]) -> list[str]:
    return list(dict.fromkeys(query.strip() for query in queries if query and query.strip()))


def plain_query(query: str, max_words: int = 14) -> str:
    """PubMed syntax -> a short keyword query for web search."""

    text = _PUNCT.sub(" ", _BOOLEAN.sub(" ", _PUBMED_TAG.sub(" ", query)))
    words = list(dict.fromkeys(text.split()))
    return " ".join(words[:max_words])


def _short(text: str, words: int = 8) -> str:
    """The first words of a decomposition term, without characters PubMed would parse."""

    return " ".join(_PUNCT.sub(" ", _BOOLEAN.sub(" ", text)).split()[:words])


def medical_fallbacks(picots: PicotsDecomposition, question: str) -> dict[SearchIntent, list[str]]:
    population = _short(picots.population)
    interventions = [_short(item) for item in picots.interventions] or [_short(question)]
    lead = interventions[0]
    alternatives = [_short(item) for item in picots.comparisons if not PLACEBO_LIKE.search(item)]
    outcome = _short(picots.outcomes[0], 5) if picots.outcomes else ""
    return {
        SearchIntent.CORE: [
            *(f"{population} {item}" for item in interventions),
            _short(question, 12),
        ],
        SearchIntent.NEGATIVE: [
            f'({lead}) AND ({population}) AND ("no significant" OR futility OR terminated '
            "OR discontinued OR harm OR failed)",
            f"{lead} {outcome} no benefit".strip(),
        ],
        SearchIntent.ALTERNATIVE: [f"{population} {item}" for item in alternatives]
        or [f"{population} {outcome} treatment comparison".strip()],
        SearchIntent.SAFETY: [f"{lead} {population} (adverse events OR safety OR harms)"],
    }


def general_fallbacks(scope: ScopeDecomposition, question: str) -> dict[SearchIntent, list[str]]:
    lead = scope.entities[0] if scope.entities else ""
    claims = scope.claims or [question]
    return {
        SearchIntent.CORE: [*(f"{lead} {claim}".strip() for claim in claims), question],
        SearchIntent.NEGATIVE: [f"{lead} {claims[0]} false criticism failed".strip()],
        SearchIntent.ALTERNATIVE: list(scope.counter_hypotheses)
        or [f"{lead} competitors alternative".strip()],
        SearchIntent.SAFETY: [f"{lead} risks incidents problems".strip()],
    }


def complete_plan(
    planned: dict[SearchIntent, list[str]], fallbacks: dict[SearchIntent, list[str]]
) -> dict[SearchIntent, list[str]]:
    """Per intent: the model's queries, topped up from the templates, capped per intent."""

    plan: dict[SearchIntent, list[str]] = {}
    for intent, cap in MAX_PER_INTENT.items():
        queries = unique(planned.get(intent, []))
        minimum = MIN_CORE if intent is SearchIntent.CORE else 1
        if len(queries) < minimum:
            queries = unique([*queries, *fallbacks.get(intent, [])])
        plan[intent] = queries[:cap]
    return plan


def medical_specs(plan: dict[SearchIntent, list[str]]) -> list[QuerySpec]:
    """PubMed variants per intent (systematic reviews first), plus a few web searches."""

    specs: list[QuerySpec] = []
    for query in plan[SearchIntent.CORE]:
        specs.append(QuerySpec(SearchIntent.CORE, query, "pubmed", Variant.SR_MA, 10))
        specs.append(QuerySpec(SearchIntent.CORE, query, "pubmed", Variant.RCT, 25))
    specs += [
        QuerySpec(SearchIntent.NEGATIVE, query, "pubmed", Variant.HIERARCHY, 15)
        for query in plan[SearchIntent.NEGATIVE]
    ]
    specs += [
        QuerySpec(SearchIntent.ALTERNATIVE, query, "pubmed", Variant.HIERARCHY, 15)
        for query in plan[SearchIntent.ALTERNATIVE]
    ]
    specs += [
        QuerySpec(SearchIntent.SAFETY, query, "pubmed", Variant.ANY_HUMAN, 15)
        for query in plan[SearchIntent.SAFETY]
    ]
    web = [
        (SearchIntent.CORE, plan[SearchIntent.CORE], ()),
        (SearchIntent.CORE, plan[SearchIntent.CORE], tuple(REGISTRY_DOMAINS)),
        (SearchIntent.NEGATIVE, plan[SearchIntent.NEGATIVE], ()),
        (SearchIntent.ALTERNATIVE, plan[SearchIntent.ALTERNATIVE], ()),
        (SearchIntent.SAFETY, plan[SearchIntent.SAFETY], tuple(REGULATOR_DOMAINS)),
    ]
    specs += [
        QuerySpec(intent, plain_query(queries[0]), "web", Variant.NONE, 8, domains)
        for intent, queries, domains in web
        if queries
    ]
    return specs


def general_specs(plan: dict[SearchIntent, list[str]]) -> list[QuerySpec]:
    return [
        QuerySpec(intent, query, "web", Variant.NONE, 10)
        for intent, queries in plan.items()
        for query in queries
    ]
