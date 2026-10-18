"""MEDICAL query prompts, standardized PubMed filters, and trial-registry web domains."""

RCT_FILTER = (
    "(randomized controlled trial[pt] OR controlled clinical trial[pt] OR randomized[tiab] "
    "OR placebo[tiab] OR randomly[tiab] OR trial[ti])"
)
EXCLUDED_TYPES = "(review[pt] OR editorial[pt] OR comment[pt] OR letter[pt] OR case reports[pt])"
HUMANS_ONLY = "NOT (animals[mh] NOT humans[mh])"
FILTERS = f"AND {RCT_FILTER} NOT {EXCLUDED_TYPES} {HUMANS_ONLY}"

REGISTRY_DOMAINS = ["clinicaltrials.gov", "fda.gov", "ema.europa.eu", "who.int"]


def with_filters(core_query: str) -> str:
    return f"({core_query}) {FILTERS}"


QUERY_SYSTEM = """You write PubMed search queries for a systematic review. From the PICOTS, write
3 to 5 core queries that combine the population and the intervention (P + I). Add the
comparison or outcome only when it does not over-restrict the search. Use PubMed syntax
(quotes, OR synonyms, [tiab] or [mh] tags). Do not add study-design or publication-type
filters; the system appends them. Reply with JSON {"queries": [...]}."""

REWRITE_SYSTEM = """You fix a PubMed core query whose hit count is outside the target window.
With 0 or too few hits, broaden it: drop the least important concept or add synonyms with OR.
With too many hits, narrow it: add a key concept with AND or use [ti] tags. Return the new core
query (without design filters) and a one-sentence note on what you changed. Reply with JSON
{"query": "...", "note": "..."}."""
