# Python Provider-Evals Tools

Prepares the [`smolagents/browse_comp`](https://huggingface.co/datasets/smolagents/browse_comp) benchmark dataset and provides direct search-result collection for eval_v2. The agent-based v1 evaluation harness remains in the repository root and uses Bun/TypeScript.

## Features

- Downloads and decrypts the XOR-obfuscated canary-protected questions and answers.
- Cleans and structures data using pandas, pyarrow, and pydantic.
- Outputs answer-free benchmark input JSONL files (`id`, `prompt`, optional `requiredTools`) strictly compatible with the harness validator.
- Outputs separate ground-truth answer JSONL files (`id`, `answer`, `problem_topic`, `prompt`) in a gitignored location for later offline scoring.
- Generates both the full 1,266-question evaluation dataset and a 10-question evaluation subset.

## Usage

```sh
# Sync virtualenv dependencies with uv
uv sync

# Run dataset preparation
uv run prepare-browse-comp
```

## Query/gold curation (eval_v2: 24 categories)

The shared framework and frozen record contract live in
[`src/query_gold/CONTRACT.md`](src/query_gold/CONTRACT.md). Category agents
implement `query_gold.categories.<module>.collect(output_dir, count=50)` and
cache source bytes/evidence under the private artifact root. Review
the contract's direct-search-answerability standard before adding cases: each
query must name its entity/identifier, field, and temporal scope; a normal public
answer-bearing page must explicitly support the gold answer, scope, and units.
API-only raw data, multi-hop puzzles, calculations, hidden context, and
unspecified `latest` questions are not valid cases.

```sh
uv sync
uv run query-gold collect       # reuses category cases.jsonl; collects missing caches
uv run query-gold validate      # offline evidence/schema/quality gates
uv run query-gold assemble      # private canonical cases, schema, manifests, reports
uv run query-gold export        # exact public input + separate private answer join
```

Artifacts are stored under gitignored `results/query-gold-curation/first-five-v1/`.
Only `collect --refresh` re-runs existing category collectors. The public export
is `benchmarks/eval_v2/questions/query_gold.jsonl`; answers and gold URLs are
separate in `benchmarks/eval_v2/answers/query_gold_answers.jsonl`.

The optional Jev reviewer requires an explicit live opt-in after validation:
`uv run query-gold jev-review --live-jevreview`. It uses the pinned
`typesafe/jev-1.14.0` model, three stratified cases/category, two calibration
requests, at most one retry, and a scaled physical-request cap. Jev results are
triage—not proof of top-five search retrieval or a replacement for human review.
That reviewer reads credentials only from `CMD_API_KEY`, `COMMANDCODE_API_KEY`,
or `COMMANDCODE_KEY`; it does not load `.env` files. See
[`../docs/query-gold-curation.md`](../docs/query-gold-curation.md) for the full
workflow and retention limitations.

## Direct provider search collection (eval_v2)

`search-urls` sends each public query directly to the single provider selected by
its settings file. It runs no Pi or other LLM, does not fetch result URLs, and
never reads reference answers or grades results. From the repository root:

```sh
uv run --project python search-urls --config benchmarks/configs/search_configs/exa.json --benchmark benchmarks/eval_v2/questions/query_gold.jsonl
uv run --project python search-urls --benchmark benchmarks/eval_v2/questions/query_gold.jsonl --max-queries 10
```

The default settings are `benchmarks/configs/search_configs/exa.json`. Pass
`--benchmark` explicitly to select an answer-free query JSONL; the collector
does not discover an input by default. The collector resumes automatically under
`benchmarks/eval_v2/search_results/<provider>/<config-hash>/`. Use
`--retry-failed` to rerun terminal failures and `--max-queries N` to bound new
work for one invocation. Progress and ETA go to stderr while stdout contains a
compact JSON summary.

Provider credentials are read from the process environment. At runtime the CLI
may load the repository-root `.env` using `python-dotenv`; credentials are never
included in settings snapshots, manifests, or result records. See
[`../docs/search-results-collection.md`](../docs/search-results-collection.md)
for the durable attempt journal, resumption rules, cancellation behavior, and
cost fields.
