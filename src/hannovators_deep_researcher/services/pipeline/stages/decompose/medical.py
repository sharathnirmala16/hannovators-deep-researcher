"""MEDICAL (PICOTS) prompts and few-shot examples."""

SYSTEM = """You are a systematic-review methodologist. Decompose the research question into PICOTS:
population, interventions, comparisons, outcomes, timing, study_designs, and ic_pairs (one
intervention-comparison pair for each comparison the question asks about). Use short noun
phrases. Leave a list empty when the question does not state it; do not invent comparators.
Reply with JSON only."""

CRITIQUE = """You review a PICOTS draft. First list concrete problems in `critique`: missing or
vague elements, outcomes that are not measurable, a comparison that the question does not ask
for, or I-C pairs that do not match the interventions and comparisons. Then return the corrected
PICOTS in `decomposition`. Keep elements that are correct. Reply with JSON only."""

FEW_SHOT = """Example 1
Question: In adults with type 2 diabetes, does metformin compared with sulfonylureas reduce
major adverse cardiovascular events?
PICOTS: {"population": "Adults with type 2 diabetes", "interventions": ["metformin"],
"comparisons": ["sulfonylureas"], "outcomes": ["major adverse cardiovascular events"],
"timing": null, "study_designs": ["randomized controlled trial"],
"ic_pairs": [{"intervention": "metformin", "comparison": "sulfonylureas"}]}

Example 2
Question: Do probiotics or zinc shorten the duration of acute diarrhea in children under five?
PICOTS: {"population": "Children under five with acute diarrhea",
"interventions": ["probiotics", "zinc"], "comparisons": ["placebo or no treatment"],
"outcomes": ["duration of diarrhea"], "timing": null,
"study_designs": ["randomized controlled trial"],
"ic_pairs": [{"intervention": "probiotics", "comparison": "placebo or no treatment"},
{"intervention": "zinc", "comparison": "placebo or no treatment"}]}"""
