"""Collection, validation, assembly, and public/private export pipeline."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from query_gold.io import (
    atomic_write_many,
    ensure_safe_path,
    json_bytes,
    jsonl_bytes,
    read_json,
    read_jsonl,
    read_text,
    sha256_bytes,
)
from query_gold.models import (
    SCHEMA_VERSION,
    CategoryId,
    PrivateBenchmarkAnswer,
    PublicBenchmarkCase,
    QueryGoldCase,
)
from query_gold.validation import (
    CATEGORY_IDS,
    DEFAULT_VALIDATION_POLICY,
    ValidationIssue,
    ValidationPolicy,
    ValidationReport,
    rejection_report,
    validate_records,
)

ARTIFACT_RELATIVE_PATH = Path("results/query-gold-curation/first-five-v1")
DATASET_ID = "query_gold_first5_v1"
CATEGORY_MODULES: dict[str, str] = {
    "01_earnings_corporate_finance": "finance",
    "02_biomedical_clinical_trials": "clinical",
    "03_code_api_documentation": "code_api",
    "04_venture_capital_funding_ma": "venture_ma",
    "05_government_courts_legal": "government_legal",
    "06_hardware_product_specifications": "hardware_specs",
    "07_static_mathematics_stem": "math_stem",
    "08_sports_box_scores_game_stats": "sports_stats",
    "09_real_estate_land_registries": "real_estate",
    "10_academic_literature_citations": "academic_citations",
    "11_cybersecurity_vulnerability_tracking": "cybersecurity_cve",
    "12_municipal_code_zoning_local_law": "municipal_zoning",
    "13_logistics_freight_supply_chain": "logistics",
    "14_aerospace_telemetry_records": "aerospace",
    "15_cloud_infrastructure_service_pricing": "cloud_pricing",
    "16_art_collectibles_auction_transactions": "art_auctions",
    "17_local_graph_municipal_pois_directory_lookups": "municipal_directory",
    "18_entertainment_box_office_media_registries": "entertainment_media",
    "19_immigration_visa_bulletins_consular_policies": "immigration_visa",
    "20_historical_meteorology_disaster_telemetry": "historical_meteorology",
    "21_gaming_software_release_patch_telemetry": "gaming_patch_telemetry",
    "22_consumer_ecommerce_msrp_recall_notices": "consumer_recalls",
    "23_executive_directory_corporate_leadership": "executive_leadership",
    "24_standards_rfcs_technical_specifications": "standards_rfc",
}
REQUIRED_SOURCE_NOTE_GROUPS: tuple[tuple[str, ...], ...] = (
    ("benchmark fit", "benchmark relevance"),
    ("rejection", "rejected candidate"),
    ("construction method", "construction"),
    ("license",),
    ("revision", "snapshot"),
    ("concentration", "diversity"),
    ("sample review", "manual review"),
    ("representativeness",),
    ("answer-bearing page", "public answer page", "public page"),
    ("discoverability", "search limitation", "search result limitation"),
    ("limitation",),
)


class DatasetFailure(RuntimeError):
    """A collection or dataset gate failed without exposing source data."""


@dataclass(frozen=True)
class AssemblyArtifacts:
    root: Path
    case_count: int
    dataset_sha256: str
    manifest_path: Path
    canonical_path: Path
    schema_path: Path
    validation_path: Path
    rejection_path: Path


@dataclass(frozen=True)
class ExportArtifacts:
    public_path: Path
    private_path: Path
    public_sha256: str
    private_sha256: str
    case_count: int


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_artifact_root() -> Path:
    return repository_root() / ARTIFACT_RELATIVE_PATH


def category_output_dir(root: Path, category_id: str) -> Path:
    if category_id not in CATEGORY_MODULES:
        raise ValueError("Unknown query-gold category")
    return root / "categories" / category_id


def _timestamp_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _model_error_summary(error: ValidationError) -> str:
    details = []
    for item in error.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"])
        details.append(f"{location or '<record>'}:{item['type']}")
    return ", ".join(details[:8]) or "schema mismatch"


def parse_cases(rows: Iterable[Any], *, source_name: str) -> list[QueryGoldCase]:
    """Validate every JSON object without echoing record content in errors."""
    cases: list[QueryGoldCase] = []
    for line_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise DatasetFailure(f"Invalid record shape in {source_name} line {line_number}.")
        try:
            case = QueryGoldCase.model_validate(row, strict=True)
        except ValidationError as error:
            summary = _model_error_summary(error)
            raise DatasetFailure(
                f"Schema validation failed in {source_name} line {line_number}: {summary}."
            ) from None
        cases.append(case)
    return cases


def _read_case_file(path: Path) -> list[QueryGoldCase]:
    try:
        rows = read_jsonl(path)
    except FileNotFoundError:
        raise
    except ValueError as error:
        raise DatasetFailure(f"Unable to read {path.name}: {type(error).__name__}.") from None
    return parse_cases(rows, source_name=path.name)


def _category_policy(
    category: CategoryId,
    count: int,
    min_source_ids: int,
    min_question_types: int,
) -> ValidationPolicy:
    return ValidationPolicy(
        categories=(category,),
        expected_count_per_category=count,
        min_distinct_source_ids=min_source_ids,
        min_question_types=min_question_types,
    )


def _write_failure_reports(root: Path, report: ValidationReport) -> None:
    atomic_write_many(
        {
            root / "validation-report.json": json_bytes(report.to_dict(), pretty=True),
            root / "rejection-report.json": json_bytes(rejection_report(report), pretty=True),
        }
    )


def _add_source_note_issues(
    report: ValidationReport,
    root: Path,
    categories: tuple[str, ...] = CATEGORY_IDS,
) -> None:
    for category in categories:
        notes_path = category_output_dir(root, category) / "sources.md"
        try:
            notes = read_text(notes_path).casefold()
        except FileNotFoundError:
            report.add(
                ValidationIssue(
                    "error",
                    "source_notes_missing",
                    "Category sources.md is required for benchmark fit and provenance review.",
                    categoryId=category,
                )
            )
            continue
        except (OSError, ValueError):
            report.add(
                ValidationIssue(
                    "error",
                    "source_notes_unreadable",
                    "Category sources.md is unsafe or unreadable.",
                    categoryId=category,
                )
            )
            continue
        for required_terms in REQUIRED_SOURCE_NOTE_GROUPS:
            if not any(term in notes for term in required_terms):
                report.add(
                    ValidationIssue(
                        "error",
                        "source_notes_section_missing",
                        "Category sources.md omits a required provenance/review topic.",
                        categoryId=category,
                    )
                )


def collect_categories(
    root: Path | None = None,
    *,
    count: int = 50,
    categories: tuple[str, ...] = CATEGORY_IDS,
    refresh: bool = False,
    min_distinct_source_ids: int = 25,
    min_question_types: int = 3,
) -> dict[str, list[QueryGoldCase]]:
    """Reuse category caches or invoke their factories when explicitly requested."""
    if count <= 0:
        raise ValueError("count must be positive")
    artifact_root = root or default_artifact_root()
    ensure_safe_path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    collected: dict[str, list[QueryGoldCase]] = {}

    for category in categories:
        if category not in CATEGORY_MODULES:
            raise ValueError("Unknown query-gold category")
        output_dir = category_output_dir(artifact_root, category)
        ensure_safe_path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        case_file = output_dir / "cases.jsonl"

        if not refresh:
            try:
                cached = _read_case_file(case_file)
            except FileNotFoundError:
                cached = None
            if cached is not None:
                if len(cached) != count or any(case.categoryId != category for case in cached):
                    raise DatasetFailure(
                        f"Cached category {category} has wrong count/category; "
                        "use --refresh explicitly."
                    )
                collected[category] = cached
                continue

        module_name = f"query_gold.categories.{CATEGORY_MODULES[category]}"
        try:
            module = importlib.import_module(module_name)
            factory = cast(Any, module).collect
            raw_cases = factory(output_dir=output_dir, count=count)
        except Exception as error:
            _write_failure_reports(
                artifact_root,
                ValidationReport(
                    valid=False,
                    issues=[
                        ValidationIssue(
                            "error",
                            "collection_failed",
                            f"Category collection failed ({type(error).__name__}); "
                            "no canonical export was written.",
                            categoryId=category,
                        )
                    ],
                ),
            )
            raise DatasetFailure(
                f"Category collection failed for {category} ({type(error).__name__})."
            ) from None

        if not isinstance(raw_cases, list) or len(raw_cases) != count:
            raise DatasetFailure(
                f"Collector for {category} did not return exactly {count} records."
            )
        cases = parse_cases(raw_cases, source_name=f"{category} collector")
        if any(case.categoryId != category for case in cases):
            raise DatasetFailure(
                f"Collector returned records with the wrong categoryId for {category}."
            )
        category_dir_map = {category: output_dir}
        local_report = validate_records(
            cases,
            category_dirs=category_dir_map,
            policy=_category_policy(
                cast(CategoryId, category),
                count,
                min_distinct_source_ids,
                min_question_types,
            ),
            dataset_sha256=sha256_bytes(jsonl_bytes(cases)),
        )
        if not local_report.valid:
            _write_failure_reports(artifact_root, local_report)
            raise DatasetFailure(f"Collected records for {category} failed validation.")

        atomic_write_many({case_file: jsonl_bytes(cases)})
        collected[category] = cases

    collection_state = {
        "collectionVersion": "query-gold-collection/v1",
        "createdAtUTC": _timestamp_utc(),
        "requestedCountPerCategory": count,
        "categories": list(categories),
        "categoryModules": {
            category: f"query_gold.categories.{CATEGORY_MODULES[category]}"
            for category in categories
        },
        "refreshRequested": refresh,
        "categoryFiles": {
            category: {
                "caseCount": len(category_cases),
                "casesSha256": sha256_bytes(jsonl_bytes(category_cases)),
            }
            for category, category_cases in collected.items()
        },
    }
    atomic_write_many(
        {artifact_root / "collection-state.json": json_bytes(collection_state, pretty=True)}
    )
    return collected


def load_category_cases(
    root: Path,
    *,
    categories: tuple[str, ...] = CATEGORY_IDS,
) -> tuple[list[QueryGoldCase], dict[str, list[QueryGoldCase]]]:
    by_category: dict[str, list[QueryGoldCase]] = {}
    combined: list[QueryGoldCase] = []
    for category in categories:
        path = category_output_dir(root, category) / "cases.jsonl"
        try:
            cases = _read_case_file(path)
        except FileNotFoundError:
            raise DatasetFailure(f"Category cache is missing for {category}.") from None
        if any(case.categoryId != category for case in cases):
            raise DatasetFailure(f"Category cache contains a mismatched categoryId for {category}.")
        by_category[category] = cases
        combined.extend(cases)
    return combined, by_category


def load_canonical_cases(root: Path) -> list[QueryGoldCase]:
    try:
        return _read_case_file(root / "cases.jsonl")
    except FileNotFoundError:
        raise DatasetFailure("Canonical cases.jsonl is missing; run assemble first.") from None


def _base_validation(
    cases: list[QueryGoldCase], root: Path, policy: ValidationPolicy
) -> ValidationReport:
    digest = sha256_bytes(jsonl_bytes(cases))
    report = validate_records(
        cases,
        category_dirs={
            category: category_output_dir(root, category) for category in policy.categories
        },
        policy=policy,
        dataset_sha256=digest,
    )
    _add_source_note_issues(report, root, policy.categories)
    return report


def validate_category_dataset(
    root: Path | None = None,
    *,
    policy: ValidationPolicy = DEFAULT_VALIDATION_POLICY,
) -> ValidationReport:
    """Validate cached category records and persist private validation/rejection reports."""
    artifact_root = root or default_artifact_root()
    ensure_safe_path(artifact_root)
    cases, _ = load_category_cases(artifact_root, categories=policy.categories)
    report = _base_validation(cases, artifact_root, policy)
    _write_failure_reports(artifact_root, report)
    return report


def _concentrations_by_category(report: ValidationReport) -> dict[str, Any]:
    return {category: report.sourceConcentration.get(category, {}) for category in CATEGORY_IDS}


def assemble_dataset(
    root: Path | None = None,
    *,
    policy: ValidationPolicy = DEFAULT_VALIDATION_POLICY,
    refresh_requested: bool = False,
) -> AssemblyArtifacts:
    """Validate all raw category caches and atomically assemble private canonical artifacts."""
    artifact_root = root or default_artifact_root()
    ensure_safe_path(artifact_root)
    cases, by_category = load_category_cases(artifact_root, categories=policy.categories)
    report = _base_validation(cases, artifact_root, policy)
    canonical_bytes = jsonl_bytes(cases)
    dataset_digest = sha256_bytes(canonical_bytes)
    report.datasetSha256 = dataset_digest

    validation_path = artifact_root / "validation-report.json"
    rejection_path = artifact_root / "rejection-report.json"
    _write_failure_reports(artifact_root, report)
    if not report.valid:
        raise DatasetFailure(
            "Dataset validation failed; canonical dataset and exports were not replaced."
        )

    category_files = {
        category: {
            "caseCount": len(category_cases),
            "casesSha256": sha256_bytes(jsonl_bytes(category_cases)),
        }
        for category, category_cases in by_category.items()
    }
    collection_state: dict[str, Any] = {}
    try:
        candidate_state = read_json(artifact_root / "collection-state.json")
        if isinstance(candidate_state, dict):
            collection_state = candidate_state
    except (FileNotFoundError, OSError, ValueError):
        collection_state = {}
    resolved_refresh = refresh_requested or collection_state.get("refreshRequested") is True
    manifest = {
        "manifestVersion": "query-gold-manifest/v1",
        "datasetId": DATASET_ID,
        "schemaVersion": SCHEMA_VERSION,
        "createdAtUTC": _timestamp_utc(),
        "caseCount": len(cases),
        "categoryCounts": report.categoryCounts,
        "datasetSha256": dataset_digest,
        "categoryFiles": category_files,
        "sourceParameters": {
            "requestedCountPerCategory": policy.expected_count_per_category,
            "categoryModules": {
                category: f"query_gold.categories.{CATEGORY_MODULES[category]}"
                for category in policy.categories
            },
            "cachePolicy": "reuse unless --refresh is explicit",
            "refreshRequested": resolved_refresh,
            "collectionStateSha256": (
                sha256_bytes(json_bytes(collection_state)) if collection_state else None
            ),
            "datasetScope": "all twelve categories",
            "querySelectionStandard": "direct-search-answerable/v1",
        },
        "sourceConcentration": _concentrations_by_category(report),
        "validation": {
            "errorCount": len(report.errors),
            "warningCount": len(report.warnings),
            "valid": report.valid,
        },
        "exports": {},
    }
    schema_path = artifact_root / "query-gold-v1.schema.json"
    canonical_path = artifact_root / "cases.jsonl"
    files = {
        canonical_path: canonical_bytes,
        schema_path: json_bytes(QueryGoldCase.model_json_schema(mode="validation"), pretty=True),
        validation_path: json_bytes(report.to_dict(), pretty=True),
        rejection_path: json_bytes(rejection_report(report), pretty=True),
        artifact_root / "manifest.json": json_bytes(manifest, pretty=True),
    }
    atomic_write_many(files)
    return AssemblyArtifacts(
        root=artifact_root,
        case_count=len(cases),
        dataset_sha256=dataset_digest,
        manifest_path=artifact_root / "manifest.json",
        canonical_path=canonical_path,
        schema_path=schema_path,
        validation_path=validation_path,
        rejection_path=rejection_path,
    )


def validate_export_join(
    public_rows: list[PublicBenchmarkCase], private_rows: list[PrivateBenchmarkAnswer]
) -> None:
    """Prove the public/private exports are a one-to-one join by ID and prompt."""
    if len(public_rows) != len(private_rows):
        raise DatasetFailure("Public/private export counts do not match.")
    public_ids = [row.id for row in public_rows]
    private_ids = [row.id for row in private_rows]
    if len(public_ids) != len(set(public_ids)) or len(private_ids) != len(set(private_ids)):
        raise DatasetFailure("Public/private exports contain duplicate IDs.")
    if public_ids != private_ids:
        raise DatasetFailure("Public/private exports do not have identical ordered IDs.")
    for public, private in zip(public_rows, private_rows, strict=True):
        if public.prompt != private.prompt:
            raise DatasetFailure("Public/private export prompts do not match by ID.")


def _unique_urls(case: QueryGoldCase) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for evidence in case.evidence:
        if evidence.url not in seen:
            seen.add(evidence.url)
            urls.append(evidence.url)
    return urls


def _normalized_path_key(path: Path) -> str:
    """Normalize a destination for host-specific path identity comparisons."""
    return os.path.normcase(os.path.abspath(path))


def _path_is_within(path_key: str, directory_key: str) -> bool:
    try:
        return os.path.commonpath((path_key, directory_key)) == directory_key
    except ValueError:
        return False


def _paths_overlap(first_key: str, second_key: str) -> bool:
    return _path_is_within(first_key, second_key) or _path_is_within(second_key, first_key)


def _validate_export_targets(
    artifact_root: Path, public_target: Path, private_target: Path
) -> None:
    public_key = _normalized_path_key(public_target)
    private_key = _normalized_path_key(private_target)
    if _paths_overlap(public_key, private_key):
        raise ValueError("Public and private export paths must not overlap")
    artifact_key = _normalized_path_key(artifact_root)
    if _paths_overlap(public_key, artifact_key) or _paths_overlap(private_key, artifact_key):
        raise ValueError("Export paths must not overlap the private artifact root")


def export_dataset(
    root: Path | None = None,
    *,
    public_path: Path | None = None,
    private_path: Path | None = None,
    policy: ValidationPolicy = DEFAULT_VALIDATION_POLICY,
) -> ExportArtifacts:
    """Write the exact answer-free public input and separate private answer join."""
    artifact_root = root or default_artifact_root()
    repo_root = repository_root()
    public_target = public_path or (repo_root / "benchmarks/eval_v2/questions/query_gold.jsonl")
    private_target = private_path or (
        repo_root / "benchmarks/eval_v2/answers/query_gold_answers.jsonl"
    )
    ensure_safe_path(artifact_root)
    ensure_safe_path(public_target)
    ensure_safe_path(private_target)
    _validate_export_targets(artifact_root, public_target, private_target)

    cases = load_canonical_cases(artifact_root)
    report = _base_validation(cases, artifact_root, policy)
    _write_failure_reports(artifact_root, report)
    if not report.valid:
        raise DatasetFailure("Canonical dataset failed validation; exports were not replaced.")

    manifest_path = artifact_root / "manifest.json"
    try:
        manifest = read_json(manifest_path)
    except (FileNotFoundError, ValueError):
        raise DatasetFailure("A valid assembly manifest is required before export.") from None
    if not isinstance(manifest, dict) or manifest.get("datasetSha256") != report.datasetSha256:
        raise DatasetFailure("Assembly manifest digest does not match canonical cases.jsonl.")

    public_rows = [PublicBenchmarkCase(id=case.id, prompt=case.query) for case in cases]
    private_rows = [
        PrivateBenchmarkAnswer(
            id=case.id,
            prompt=case.query,
            answer=case.gold.answer,
            goldUrls=_unique_urls(case),
        )
        for case in cases
    ]
    validate_export_join(public_rows, private_rows)
    public_content = jsonl_bytes(public_rows)
    private_content = jsonl_bytes(private_rows)
    public_digest = sha256_bytes(public_content)
    private_digest = sha256_bytes(private_content)
    manifest["exports"] = {
        "public": {
            "path": str(public_target.relative_to(repo_root))
            if public_target.is_relative_to(repo_root)
            else public_target.name,
            "sha256": public_digest,
            "caseCount": len(public_rows),
            "fields": ["id", "prompt"],
        },
        "private": {
            "path": str(private_target.relative_to(repo_root))
            if private_target.is_relative_to(repo_root)
            else private_target.name,
            "sha256": private_digest,
            "caseCount": len(private_rows),
            "fields": ["id", "prompt", "answer", "goldUrls"],
        },
        "exportedAtUTC": _timestamp_utc(),
    }
    atomic_write_many(
        {
            public_target: public_content,
            private_target: private_content,
            manifest_path: json_bytes(manifest, pretty=True),
        }
    )
    return ExportArtifacts(
        public_path=public_target,
        private_path=private_target,
        public_sha256=public_digest,
        private_sha256=private_digest,
        case_count=len(cases),
    )
