"""MEDICAL (PICOTS) prompts and few-shot examples."""

SYSTEM = """You are a systematic-review methodologist. Decompose the research question into PICOTS:
population, interventions, comparisons, outcomes, timing, study_designs, and ic_pairs (one
intervention-comparison pair for each comparison). Use short noun phrases.
List the comparators the question asks about first. Then add one or two clinically relevant
ALTERNATIVE comparators a skeptical reviewer would test against (another drug class, a
different dose or agent in the same class, or usual care), so the review also looks for
evidence that a different option is better. Outcomes must include the key harms and safety
outcomes (adverse events) next to the benefit outcomes. study_designs lists designs from the
top of the evidence hierarchy down (systematic review / meta-analysis, randomized controlled
trial, then observational designs when trials are scarce). Reply with JSON only."""

CRITIQUE = """You review a PICOTS draft as a skeptical methodologist. First list concrete problems
in `critique`: missing or vague elements, outcomes that are not measurable, missing harm or
safety outcomes, no alternative comparator that could disconfirm the intervention, or I-C pairs
that do not match the interventions and comparisons. Then return the corrected PICOTS in
`decomposition`. Keep elements that are correct. Reply with JSON only."""

FEW_SHOT = """Example 1
Question: In adults with type 2 diabetes, does metformin compared with sulfonylureas reduce
major adverse cardiovascular events?
PICOTS: {"population": "Adults with type 2 diabetes", "interventions": ["metformin"],
"comparisons": ["sulfonylureas", "DPP-4 inhibitors"],
"outcomes": ["major adverse cardiovascular events", "severe hypoglycemia",
"lactic acidosis"], "timing": null,
"study_designs": ["systematic review or meta-analysis", "randomized controlled trial"],
"ic_pairs": [{"intervention": "metformin", "comparison": "sulfonylureas"},
{"intervention": "metformin", "comparison": "DPP-4 inhibitors"}]}

Example 2
Question: Do probiotics or zinc shorten the duration of acute diarrhea in children under five?
PICOTS: {"population": "Children under five with acute diarrhea",
"interventions": ["probiotics", "zinc"],
"comparisons": ["placebo or no treatment", "oral rehydration solution alone"],
"outcomes": ["duration of diarrhea", "vomiting", "serious adverse events"], "timing": null,
"study_designs": ["systematic review or meta-analysis", "randomized controlled trial"],
"ic_pairs": [{"intervention": "probiotics", "comparison": "placebo or no treatment"},
{"intervention": "zinc", "comparison": "placebo or no treatment"},
{"intervention": "probiotics", "comparison": "oral rehydration solution alone"}]}"""
