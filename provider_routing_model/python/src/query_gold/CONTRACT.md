# Query + gold curation contract (`query-gold/v1`)

This file is the shared implementation contract for the first-five-category
query/gold dataset. Category collectors must read it before returning records.
It is intentionally independent of benchmark runtime and does not define a
provider fallback or an agent tool.

## Category factories

Implement these modules under `python/src/query_gold/categories/`:

| Module | `categoryId` |
| --- | --- |
| `finance.py` | `01_earnings_corporate_finance` |
| `clinical.py` | `02_biomedical_clinical_trials` |
| `code_api.py` | `03_code_api_documentation` |
| `venture_ma.py` | `04_venture_capital_funding_ma` |
| `government_legal.py` | `05_government_courts_legal` |
| `hardware_specs.py` | `06_hardware_product_specifications` |
| `math_stem.py` | `07_static_mathematics_stem` |
| `sports_stats.py` | `08_sports_box_scores_game_stats` |
| `real_estate.py` | `09_real_estate_land_registries` |
| `academic_citations.py` | `10_academic_literature_citations` |
| `cybersecurity_cve.py` | `11_cybersecurity_vulnerability_tracking` |
| `municipal_zoning.py` | `12_municipal_code_zoning_local_law` |
| `logistics.py` | `13_logistics_freight_supply_chain` |
| `aerospace.py` | `14_aerospace_telemetry_records` |
| `cloud_pricing.py` | `15_cloud_infrastructure_service_pricing` |
| `art_auctions.py` | `16_art_collectibles_auction_transactions` |
| `municipal_directory.py` | `17_local_graph_municipal_pois_directory_lookups` |
| `entertainment_media.py` | `18_entertainment_box_office_media_registries` |
| `immigration_visa.py` | `19_immigration_visa_bulletins_consular_policies` |
| `historical_meteorology.py` | `20_historical_meteorology_disaster_telemetry` |
| `gaming_patch_telemetry.py` | `21_gaming_software_release_patch_telemetry` |
| `consumer_recalls.py` | `22_consumer_ecommerce_msrp_recall_notices` |
| `executive_leadership.py` | `23_executive_directory_corporate_leadership` |
| `standards_rfc.py` | `24_standards_rfcs_technical_specifications` |

Each exports this stable factory:

```python
def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]: ...
```

The pipeline passes `results/query-gold-curation/first-five-v1/categories/<categoryId>`
as `output_dir`. `rawPath` is relative to that directory, uses `/` separators,
and must point to the exact UTF-8 source bytes cited by the excerpt. Collectors
may also write `cases.jsonl` themselves for standalone use; the shared pipeline
persists the returned records there and reuses that cache on later runs. Network
collection is opt-in via the `collect` CLI command; it is not performed by
`validate`, `assemble`, or `export`.

## Canonical record

Every canonical JSONL line is a strict Pydantic v2 `QueryGoldCase`. Unknown
fields are errors. All dates retain the precision actually supplied by the
source; never turn a year or month into an invented day/time.

## Hard query-selection and evidence standard

These are direct, standalone inputs for an agent's web-search tool, not
BrowseComp puzzles or multi-hop research tasks. Each query must identify a
natural entity or unique identifier, the metric/field being requested, and an
exact date/period/software version when the fact is mutable. Dates and versions
define scope; they are not extra navigation instructions. Do not use hidden
dataset context, vague references (`this company`, `the above document`),
answer snippets, concealed-source riddles, unspecified `latest`/`current`
scope, cross-document arithmetic, or compound research instructions.

At least one supplied evidence entry must be a plausible normal public
answer-bearing HTML/PDF/versioned-document page that a direct search could
surface. Its cached excerpt must explicitly contain the gold answer at the
matching temporal scope and units. An internal API/benchmark JSON response may
verify extraction, but API-only/hidden raw data is not enough: also capture the
normal public page where the answer appears. Prefer one primary page supporting
the complete answer. Clinical-trial registry pages may be paired with their
underlying API record; technical source may be paired with versioned official
documentation or a normal versioned source/blob page. Do not manufacture
arithmetic or rely on model knowledge. The shared structural checks reject
high-confidence context-dependent, derived/compound, missing-scope, unsupported
answer, and API-only cases; direct-search discoverability and domain fit still
need human sample review. Do not run multi-provider/current-fetch retrieval
benchmarks in this curation phase; record discovery limitations honestly.

```json
{
  "schemaVersion": "query-gold/v1",
  "id": "stable-unique-id",
  "categoryId": "01_earnings_corporate_finance",
  "query": "A standalone, answerable question with its temporal scope stated naturally.",
  "temporal": {
    "kind": "as_of",
    "precision": "day",
    "asOf": "2025-06-30"
  },
  "gold": {
    "answer": "The canonical supported answer.",
    "acceptedAnswers": [],
    "value": 12.5,
    "units": "USD per share",
    "currency": "USD"
  },
  "evidence": [
    {
      "url": "https://example.org/source/record-1",
      "title": "Source record title",
      "retrievedAtUTC": "2026-10-17T12:00:00Z",
      "publishedAt": "2025-06",
      "sourceRecordId": "record-1",
      "license": "CC BY 4.0",
      "rawSha256": "<64 lowercase hex characters>",
      "rawPath": "raw/record-1.json",
      "excerpt": "A literal UTF-8 substring of the cached source bytes."
    }
  ],
  "derivation": {
    "sourceFamily": "official_filings",
    "generatorVersion": "finance-collector/1",
    "questionType": "historical_per_share_value"
  }
}
```

Allowed category IDs are exactly those in the table above. `temporal.kind` is
`immutable | as_of | period | event | version`; `precision` is
`immutable | year | month | day | second | version`. Immutable facts use
`kind="immutable", precision="immutable"`; `immutableReason` is optional but
recommended when the fact's immutability is not self-evident. Every mutable
record must provide a scope field required by its kind: `asOf` for `as_of`,
`date` for `event`, both `periodStart` and `periodEnd` for `period`, or `version`
for `version`. The temporal validator checks that the scope's ISO precision
matches the declared precision. Natural-language query wording need not contain
the exact ISO string, but must state the same date/year/period/version clearly.

`gold.value`, when present, is finite JSON (`null`, booleans, strings, finite
numbers, arrays, and string-keyed objects). `acceptedAnswers` is always present.
Gold units and currency are explicit when applicable. Each record has at least
one evidence entry. URLs are public HTTP(S) URLs without URL-embedded credentials
or credential-like query parameters. `retrievedAtUTC` is a full UTC timestamp;
`publishedAt` and `effectiveDate` may retain source precision (`YYYY`, `YYYY-MM`,
`YYYY-MM-DD`, or a timezone-qualified timestamp). Do not fabricate missing dates.

`rawSha256` is SHA-256 of the actual bytes at `rawPath`. `excerpt` must be an
exact substring after strict UTF-8 decoding (no normalization is applied).
Evidence paths must remain inside the category output directory and may not be
absolute, traverse upward, use symlinks, or point to `.env`/credential files.
Never read or stat a path that is lexically recognized as a credential path.

`derivation.questionType` is **required** and should be a concise semantic
question subtype (not merely a source/API name). Across each 50-record category,
the quality gate requires at least 25 distinct non-empty `sourceRecordId`s and
at least 3 distinct `questionType`s. `sourceFamily` identifies the source class;
multiple families are encouraged, but source diversity is not faked by renaming
one source.

If these cases later train or evaluate a query router, routing features must
come only from public prompt/query text. Case IDs are join keys, not features;
their prefixes may reveal category. Do not feed category labels, gold answers,
evidence, or agent trajectories to the router. `sourceRecordId` is provenance
metadata that can support future grouped train/test split design; this curation
work does not add training or split logic.

## Dataset gates and review notes

The first-five version contains exactly 50 cases per category (250 total), with
unique IDs and normalized queries. Normalization is Unicode NFKC, casefolding,
and collapsing whitespace. Every record must pass strict schema, temporal,
URL/path, raw-byte checksum, and exact-excerpt validation. The validator also
reports source and question-type concentrations, missing units/currencies,
duration units, clinical/trial date evidence, public answer-page coverage,
source-answer literal support, standalone query shape, and weak or answer-leaking
query signals. Structural high-confidence red flags fail validation; entity/field
classification and search discoverability remain explicit human review items.
In particular, the answer-leak check only warns when the normalized
non-numeric canonical answer (at least five characters) occurs verbatim in the
query; it is not a generic number/year matcher.

Each category writes `sources.md` beside `cases.jsonl`. Include: benchmark fit;
candidate rejection criteria and counts; construction method; license and
source revision/snapshot policy; source/question-type concentration; a manual
sample-review note; the normal public answer-bearing pages; direct-search
discoverability limitations; and representativeness gaps. Keep provenance and
review artifacts private under `results/query-gold-curation/first-five-v1/`.

The pipeline stores canonical `cases.jsonl`, generated schema JSON, validation
and rejection reports, source manifests, and Jev reports under that private
root. The only public export is
`benchmarks/eval_v2/questions/query_gold.jsonl`, with exactly `{ "id", "prompt" }`
where `prompt` is the canonical query. The private join is
`benchmarks/eval_v2/answers/query_gold_answers.jsonl`, with exactly
`{ "id", "prompt", "answer", "goldUrls" }`. Export joins are checked by ID
and prompt. Never include gold answers, evidence excerpts, or answer files in the
public export or benchmark run configuration.

The manifest pins canonical dataset SHA-256, category file hashes/counts,
resolved collection parameters, timestamp, and source/question-type
concentrations; it must not contain credentials. Failed collection or validation
must not replace a previous valid canonical dataset or either export. Cached
category files are reused unless `collect --refresh` is explicitly requested.

## Bounded Jev reviewer

The optional CommandCode Jev reviewer uses the documented
`POST https://api.commandcode.ai/provider/v1/systemone` endpoint and pinned
`typesafe/jev-1.14.0` model (not a chat endpoint). It sees only the case query,
declared temporal scope, gold fields needed for comparison, and supplied
evidence title/URL/date/excerpt. It must not browse, fetch, or invent evidence.
The typed request has `model`, `state` as a compact JSON string, and a `questions`
object keyed by question ID. Each question is `{ "type": "noul", "instructions":
"..." }`; the four questions cover whether one direct search could surface
answer-bearing public content, direct gold support by the supplied excerpt,
temporal coherence, and single-answer ambiguity. The response has a top-level
`model` and must contain all four `answers.<questionId>` objects with
`{ "type": "noul", "noul": probability }` in `[0,1]`, plus native `usage`.

An explicit `--live-jevreview` is required. The default sampler takes three
deterministically stratified records from each category plus one fixed positive
and one fixed negative calibration case: at most 17 logical requests. One retry
is allowed, with a shared hard cap of 34 physical requests, a 30-second request
timeout, and a 12,000-character JSON state cap. Persist timing, status, safe
usage, probabilities, and decision locally after each physical request and
before attempting another. Do not persist headers, raw error bodies, or secrets.
The versioned calibration pair uses the first ID-sorted case with a numeric
finance value as its real positive control. Its negative is a counterfactual
copy with the same query, temporal scope, and evidence, but a conflicting gold
answer/value and no accepted aliases. The positive must meet every rubric
threshold; the negative must have `gold_supported` at or below its negative
threshold, with no pass requirement on its other dimensions. Rubric and
calibration versions are part of the cache digest.
Use request-cache keys over case digest + model + rubric digest; cached decisions
skip requests. Unknown cost stays unknown (`reportedUsd=null` unless the response
reports it); estimated cost is never substituted. Failed/invalid responses are
`review_required`, never `PASS`. Jev probabilities are triage only: they do not
prove a page appears in the top five results or replace human review. Jev does
not automatically review or pass all 250 cases. If a configured
zero-data-retention requirement is requested, including `CMD_ZDR=1`, stop with an
explicit unsupported status rather than silently disabling it.
