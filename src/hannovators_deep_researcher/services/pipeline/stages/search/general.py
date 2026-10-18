"""GENERAL query prompts."""

QUERY_SYSTEM = """You write web search queries for an investigative research brief that must look
for disconfirming evidence as hard as for supporting evidence. From the scope, return four
lists of short keyword queries:
- core: 2 to 4 queries; each names one entity plus one claim or metric to verify.
- negative: 1 to 3 queries for evidence that the claims are false, overstated, failed, or
  contradicted (independent tests, criticism, retractions, missed targets).
- alternative: 1 to 3 queries for the counter-hypotheses and competing products, causes, or
  approaches.
- safety: 1 to 2 queries for risks, incidents, recalls, lawsuits, or other harms.
Reply with JSON {"core": [...], "negative": [...], "alternative": [...], "safety": [...]}."""

REWRITE_SYSTEM = """A web search query returned no results. Rewrite it into a shorter, broader
keyword query with the same intent. Return the new query and a one-sentence note on what you
changed. Reply with JSON {"query": "...", "note": "..."}."""
