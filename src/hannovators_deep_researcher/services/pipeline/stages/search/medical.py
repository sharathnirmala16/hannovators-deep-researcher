"""MEDICAL query prompts, evidence-hierarchy PubMed filters, and registry/regulator web domains.

Each core query runs twice: once restricted to systematic reviews and meta-analyses and once
to randomized trials, so the strongest designs are pulled first. Negative and alternative
queries accept either level; safety queries accept any human study, because harms often come
from observational data.
"""

from enum import StrEnum

RCT_FILTER = (
    "(randomized controlled trial[pt] OR controlled clinical trial[pt] OR randomized[tiab] "
    "OR placebo[tiab] OR randomly[tiab] OR trial[ti])"
)
SR_MA_FILTER = (
    '(meta-analysis[pt] OR systematic review[pt] OR "meta-analysis"[ti] '
    'OR "systematic review"[ti] OR "pooled analysis"[ti])'
)
EXCLUDED_TYPES = "(review[pt] OR editorial[pt] OR comment[pt] OR letter[pt] OR case reports[pt])"
OPINION_TYPES = "(editorial[pt] OR comment[pt] OR letter[pt] OR news[pt])"
HUMANS_ONLY = "NOT (animals[mh] NOT humans[mh])"


class Variant(StrEnum):
    """Which evidence-hierarchy filter a PubMed query variant appends."""

    SR_MA = "SR_MA"
    RCT = "RCT"
    HIERARCHY = "SR_MA_OR_RCT"
    ANY_HUMAN = "ANY_HUMAN"
    NONE = "NONE"


FILTERS: dict[Variant, str] = {
    Variant.SR_MA: f"AND {SR_MA_FILTER} NOT {OPINION_TYPES} {HUMANS_ONLY}",
    Variant.RCT: f"AND {RCT_FILTER} NOT {EXCLUDED_TYPES} {HUMANS_ONLY}",
    Variant.HIERARCHY: f"AND ({SR_MA_FILTER} OR {RCT_FILTER}) NOT {OPINION_TYPES} {HUMANS_ONLY}",
    Variant.ANY_HUMAN: f"NOT {OPINION_TYPES} {HUMANS_ONLY}",
    Variant.NONE: "",
}

REGISTRY_DOMAINS = ["clinicaltrials.gov", "fda.gov", "ema.europa.eu", "who.int"]
REGULATOR_DOMAINS = ["fda.gov", "ema.europa.eu", "who.int"]


def with_filters(core_query: str, variant: Variant = Variant.RCT) -> str:
    filters = FILTERS[variant]
    return f"({core_query}) {filters}".strip()


QUERY_SYSTEM = """You write PubMed search queries for a systematic review that must look for
disconfirming evidence as hard as for supporting evidence. From the PICOTS, return four lists:
- core: 2 to 4 queries that combine the population and the intervention (P + I). Add the
  comparison or outcome only when it does not over-restrict the search.
- negative: 1 to 3 queries for evidence AGAINST the intervention: null or negative trials,
  harm, trials stopped early for futility or safety, terminated or discontinued trials,
  "no significant difference", and contradicting results.
- alternative: 1 to 3 queries for OTHER interventions and comparators for the same population
  and outcomes (other drug classes, the alternative comparators in the PICOTS, head-to-head
  comparisons).
- safety: 1 to 2 queries for adverse events and safety outcomes of the intervention in the
  population.
Use PubMed syntax (quotes, OR synonyms, [tiab] or [mh] tags) and keep each query short enough
to return hits. Do not add study-design or publication-type filters; the system appends them.
Reply with JSON {"core": [...], "negative": [...], "alternative": [...], "safety": [...]}."""

REWRITE_SYSTEM = """You fix a PubMed core query whose hit count is outside the target window.
With 0 or too few hits, broaden it: drop the least important concept or add synonyms with OR.
With too many hits, narrow it: add a key concept with AND or use [ti] tags. Return the new core
query (without design filters) and a one-sentence note on what you changed. Reply with JSON
{"query": "...", "note": "..."}."""

INTENT_REWRITE_HINT = {
    "NEGATIVE": "Keep the query aimed at null, negative, harmful, or stopped trials.",
    "ALTERNATIVE": "Keep the query aimed at other interventions or comparators.",
    "SAFETY": "Keep the query aimed at adverse events and harms.",
}
