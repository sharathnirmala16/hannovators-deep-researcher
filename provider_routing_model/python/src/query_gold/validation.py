"""Dataset-level integrity, evidence, temporal, and curation quality gates."""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from query_gold.io import sha256_bytes
from query_gold.models import CategoryId, QueryGoldCase, _check_path_is_lexically_safe
from query_gold.validation_rules import (
    _CONTEXT_DEPENDENT_PATTERN,
    _CURRENCY_PATTERN,
    _CURRENCY_SYMBOLS,
    _DERIVED_OR_MULTI_HOP_PATTERN,
    _DURATION_ANSWER_PATTERN,
    _FIELD_TERMS,
    _INLINE_MARKUP_RE,
    _QUESTION_STOPWORDS,
    _SEARCH_INSTRUCTION_PATTERN,
    _UNBOUNDED_TIME_PATTERN,
    _UNIT_QUALIFIERS,
    _UNIT_TERM_ALIASES,
)

CATEGORY_IDS: tuple[CategoryId, ...] = (
    "01_earnings_corporate_finance",
    "02_biomedical_clinical_trials",
    "03_code_api_documentation",
    "04_venture_capital_funding_ma",
    "05_government_courts_legal",
    "06_hardware_product_specifications",
    "07_static_mathematics_stem",
    "08_sports_box_scores_game_stats",
    "09_real_estate_land_registries",
    "10_academic_literature_citations",
    "11_cybersecurity_vulnerability_tracking",
    "12_municipal_code_zoning_local_law",
    "13_logistics_freight_supply_chain",
    "14_aerospace_telemetry_records",
    "15_cloud_infrastructure_service_pricing",
    "16_art_collectibles_auction_transactions",
    "17_local_graph_municipal_pois_directory_lookups",
    "18_entertainment_box_office_media_registries",
    "19_immigration_visa_bulletins_consular_policies",
    "20_historical_meteorology_disaster_telemetry",
    "21_gaming_software_release_patch_telemetry",
    "22_consumer_ecommerce_msrp_recall_notices",
    "23_executive_directory_corporate_leadership",
    "24_standards_rfcs_technical_specifications",
)


@dataclass(frozen=True)
class ValidationPolicy:
    """Configurable thresholds; production defaults enforce the first-five contract."""

    categories: tuple[CategoryId, ...] = CATEGORY_IDS
    expected_count_per_category: int | None = 50
    min_distinct_source_ids: int = 25
    min_question_types: int = 3
    require_all_categories: bool = True
    source_concentration_warning_cases: int = 5


DEFAULT_VALIDATION_POLICY = ValidationPolicy()


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    caseId: str | None = None
    categoryId: str | None = None


@dataclass
class ValidationReport:
    valid: bool = True
    caseCount: int = 0
    categoryCounts: dict[str, int] = field(default_factory=dict)
    datasetSha256: str | None = None
    sourceConcentration: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "error":
            self.valid = False

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "caseCount": self.caseCount,
            "categoryCounts": self.categoryCounts,
            "datasetSha256": self.datasetSha256,
            "sourceConcentration": self.sourceConcentration,
            "quality": self.quality,
            "errors": [asdict(issue) for issue in self.errors],
            "warnings": [asdict(issue) for issue in self.warnings],
        }


def normalize_text(value: str) -> str:
    """Normalization used for query de-duplication and exact answer-leak checks."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _safe_evidence_file(category_dir: Path, raw_path: str) -> Path:
    """Resolve a raw file without following symlinks or touching credential paths."""
    _check_path_is_lexically_safe(raw_path)
    for part in category_dir.parts:
        lowered = part.casefold()
        if lowered == ".env" or lowered.startswith(".env."):
            raise ValueError("credential path")
        if lowered in {".netrc", ".npmrc", ".pypirc", "credentials", "credentials.json"}:
            raise ValueError("credential path")

    root = Path(os.path.abspath(category_dir))
    root_parts = root.parts
    cursor = Path(root_parts[0]) if root_parts else root
    for index, part in enumerate(root_parts[1:], start=1):
        cursor = cursor / part
        mode = cursor.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("category path contains a symlink")
        if index < len(root_parts) - 1 and not stat.S_ISDIR(mode):
            raise ValueError("category path contains a non-directory component")
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError("category output directory does not exist")

    candidate = root
    for part in PurePosixPath(raw_path).parts:
        candidate = candidate / part
        mode = candidate.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("evidence path contains a symlink")
    if not stat.S_ISREG(candidate.lstat().st_mode):
        raise ValueError("evidence path is not a regular file")
    return candidate


def _validate_evidence(
    case: QueryGoldCase,
    category_dirs: Mapping[str, Path],
    raw_cache: dict[Path, tuple[str, str]],
    report: ValidationReport,
) -> None:
    category_dir = category_dirs.get(case.categoryId)
    if category_dir is None:
        report.add(
            ValidationIssue(
                "error",
                "missing_category_directory",
                "Evidence cannot be checked because its category output directory is missing.",
                case.id,
                case.categoryId,
            )
        )
        return

    for evidence in case.evidence:
        try:
            path = _safe_evidence_file(category_dir, evidence.rawPath)
            if path not in raw_cache:
                raw = path.read_bytes()
                decoded = raw.decode("utf-8", errors="strict")
                raw_cache[path] = (sha256_bytes(raw), decoded)
            digest, decoded = raw_cache[path]
        except FileNotFoundError:
            report.add(
                ValidationIssue(
                    "error",
                    "evidence_file_missing",
                    "A referenced evidence cache file is missing.",
                    case.id,
                    case.categoryId,
                )
            )
            continue
        except UnicodeDecodeError:
            report.add(
                ValidationIssue(
                    "error",
                    "evidence_not_utf8",
                    "A referenced evidence cache file is not strict UTF-8.",
                    case.id,
                    case.categoryId,
                )
            )
            continue
        except (OSError, ValueError):
            report.add(
                ValidationIssue(
                    "error",
                    "evidence_path_unsafe",
                    "A referenced evidence path is unsafe or inaccessible.",
                    case.id,
                    case.categoryId,
                )
            )
            continue

        if digest != evidence.rawSha256:
            report.add(
                ValidationIssue(
                    "error",
                    "evidence_sha256_mismatch",
                    "Evidence rawSha256 does not match the cached source bytes.",
                    case.id,
                    case.categoryId,
                )
            )
        if evidence.excerpt not in decoded:
            report.add(
                ValidationIssue(
                    "error",
                    "evidence_excerpt_not_literal",
                    "Evidence excerpt is not a literal UTF-8 substring of the cached bytes.",
                    case.id,
                    case.categoryId,
                )
            )


def _date_mentions(query: str, value: str, precision: str) -> bool:
    lowered = normalize_text(query)
    if value in query:
        return True
    if precision == "version":
        return normalize_text(value) in lowered
    if precision == "year":
        return re.search(rf"(?<!\d){re.escape(value)}(?!\d)", query) is not None

    try:
        if precision == "month":
            parsed_month = date.fromisoformat(f"{value}-01")
            year = f"{parsed_month.year:04d}"
            month_name = parsed_month.strftime("%B").casefold()
            month_abbr = parsed_month.strftime("%b").casefold()
            return year in query and (month_name in lowered or month_abbr in lowered)
        if precision == "day":
            parsed_day = date.fromisoformat(value)
            year = f"{parsed_day.year:04d}"
            month_name = parsed_day.strftime("%B").casefold()
            month_abbr = parsed_day.strftime("%b").casefold()
            alternatives = (
                f"{parsed_day.month}/{parsed_day.day}/{year}",
                f"{parsed_day.month:02d}/{parsed_day.day:02d}/{year}",
                f"{parsed_day.day} {month_name} {year}",
                f"{month_name} {parsed_day.day}, {year}",
                f"{month_abbr} {parsed_day.day}, {year}",
            )
            return any(normalize_text(item) in lowered for item in alternatives)
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        date_text = timestamp.date().isoformat()
        time_text = timestamp.strftime("%H:%M:%S")
        return date_text in query and time_text in query
    except ValueError:
        return False


def _query_scope_is_obvious(case: QueryGoldCase) -> bool:
    temporal = case.temporal
    if temporal.kind == "immutable":
        return True
    if temporal.kind == "version":
        return temporal.version is not None and _date_mentions(
            case.query, temporal.version, "version"
        )

    values = {
        "as_of": [temporal.asOf],
        "event": [temporal.date],
        "period": [temporal.periodStart, temporal.periodEnd],
    }[temporal.kind]
    required = [value for value in values if value is not None]
    if all(_date_mentions(case.query, value, temporal.precision) for value in required):
        return True

    if temporal.kind == "period" and temporal.periodStart and temporal.periodEnd:
        start = temporal.periodStart
        end = temporal.periodEnd
        if len(start) >= 4 and start[:4] == end[:4]:
            year = start[:4]
            if re.search(rf"(?<!\d){year}(?!\d)", case.query):
                return True
    return False


def _query_has_entity_or_identifier(query: str) -> bool:
    title_tokens = re.findall(r"\b[A-Z][A-Za-z0-9&.'-]{1,}\b", query)
    uppercase_tokens = re.findall(r"\b[A-Z0-9][A-Z0-9._/-]{1,}\b", query)
    candidates = {token.casefold().strip(".'-") for token in title_tokens + uppercase_tokens}
    candidates -= _QUESTION_STOPWORDS
    if candidates:
        return True
    identifier_patterns = (
        r"\bNCT\d{6,}\b",
        r"\bCVE-\d{4}-\d{3,}\b",
        r"\b\d{1,2}-\d{1,2}-\d{4}-[A-Z]+-\d+\b",
        r"\b\d{4}-\d{5,}\b",
        r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\b",
        r"\b[A-Za-z0-9.-]+\.(?:com|org|gov|edu|io|dev|net)\b",
        r"`[A-Za-z_][A-Za-z0-9_.]*`",
    )
    return any(re.search(pattern, query, re.IGNORECASE) for pattern in identifier_patterns)


def _query_has_metric_or_field(query: str, category: str) -> bool:
    lowered = normalize_text(query)
    return any(normalize_text(term) in lowered for term in _FIELD_TERMS[category])


def _query_is_compound(query: str, category: str) -> bool:
    if query.count("?") > 1 or re.search(
        r"\b(?:and then|also find|as well as|in addition to)\b", query, re.I
    ):
        return True
    if re.search(r"\band\b", query, re.I):
        lowered = normalize_text(query)
        matched_fields = sum(
            1 for term in _FIELD_TERMS[category] if normalize_text(term) in lowered
        )
        return matched_fields >= 2
    return False


def _is_public_answer_page(evidence: Any) -> bool:
    parsed = urlsplit(evidence.url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    path = parsed.path.casefold()
    if not host or host.startswith("api.") or ".api." in host or host.startswith("raw."):
        return False
    api_route = path == "/api" or path.startswith("/api/")
    docs_host = host.startswith(("docs.", "developer.", "developers."))
    if api_route and not docs_host:
        return False
    if any(segment in path for segment in ("/graphql", "/openapi.json", "/swagger.json")):
        return False
    if re.search(r"\.(?:json|jsonl|ndjson|csv|tsv|parquet|xml|zip|gz|yaml|yml)$", path):
        return False
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in {"format", "output", "type"} and value.casefold() in {
            "json",
            "csv",
            "xml",
            "parquet",
        }:
            return False
    if host == "github.com":
        return any(segment in {"blob", "releases", "wiki"} for segment in path.split("/"))
    return True


def _answer_appears(answer: str, excerpt: str) -> bool:
    normalized_answer = normalize_text(_INLINE_MARKUP_RE.sub(r"\2", answer))
    normalized_excerpt = normalize_text(_INLINE_MARKUP_RE.sub(r"\2", excerpt))
    if not normalized_answer:
        return False
    if any(character.isalpha() for character in normalized_answer):
        return normalized_answer in normalized_excerpt
    return (
        re.search(rf"(?<![\w]){re.escape(normalized_answer)}(?![\w])", normalized_excerpt)
        is not None
    )


def _gold_is_explicit(case: QueryGoldCase, evidence_entries: Iterable[Any] | None = None) -> bool:
    excerpts = [evidence.excerpt for evidence in (evidence_entries or case.evidence)]
    acceptable = [case.gold.answer, *case.gold.acceptedAnswers]
    if any(_answer_appears(answer, excerpt) for answer in acceptable for excerpt in excerpts):
        return True
    value = case.gold.value
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        value_text = str(value)
        if any(_answer_appears(value_text, excerpt) for excerpt in excerpts):
            return True
    return False


def _scope_is_explicit_in_evidence(
    case: QueryGoldCase, evidence_entries: Iterable[Any] | None = None
) -> bool:
    temporal = case.temporal
    if temporal.kind == "immutable":
        return True
    entries = list(evidence_entries or case.evidence)
    text = " ".join(
        [
            evidence.title
            + " "
            + evidence.excerpt
            + " "
            + " ".join(
                value
                for value in (
                    evidence.publishedAt,
                    evidence.effectiveDate,
                    evidence.upstreamRevision,
                )
                if value is not None
            )
            for evidence in entries
        ]
    )
    if temporal.kind == "version":
        return temporal.version is not None and _date_mentions(text, temporal.version, "version")
    scope_values = {
        "as_of": [temporal.asOf],
        "event": [temporal.date],
        "period": [temporal.periodStart, temporal.periodEnd],
    }[temporal.kind]
    required = [value for value in scope_values if value is not None]
    if all(_date_mentions(text, value, temporal.precision) for value in required):
        return True
    if (
        temporal.kind == "period"
        and temporal.periodStart
        and temporal.periodEnd
        and temporal.periodStart[:4] == temporal.periodEnd[:4]
    ):
        year = temporal.periodStart[:4]
        return re.search(rf"(?<!\d){year}(?!\d)", text) is not None
    return False


def _currency_is_explicit(currency: str, text: str) -> bool:
    normalized_currency = normalize_text(currency)
    aliases = _CURRENCY_SYMBOLS.get(normalized_currency, (currency,))
    normalized_text = normalize_text(text)
    for alias in aliases:
        if alias in {"$", "€", "£", "¥"}:
            if alias in text:
                return True
        elif normalize_text(alias) in normalized_text:
            return True
    return False


def _units_are_explicit(case: QueryGoldCase, evidence_entries: Iterable[Any] | None = None) -> bool:
    if not case.gold.units:
        return True
    entries = list(evidence_entries or case.evidence)
    text = " ".join(evidence.excerpt for evidence in entries)
    if normalize_text(case.gold.units) in normalize_text(text):
        return True
    units_without_currency = re.sub(
        r"\b(?:USD|EUR|GBP|JPY|CAD|AUD|CNY)\b|[$€£¥]", " ", case.gold.units, flags=re.I
    )
    unit_words = [
        word
        for word in re.findall(r"[a-z0-9%]+", normalize_text(units_without_currency))
        if word not in {"a", "an", "each", "number", "of", "one", "per", "the"}
        and word not in _UNIT_QUALIFIERS
    ]
    normalized_text = normalize_text(text)
    if not unit_words:
        currency = case.gold.currency
        if currency is None:
            currency_match = re.search(r"\b(USD|EUR|GBP|JPY|CAD|AUD|CNY)\b", case.gold.units, re.I)
            currency = currency_match.group(1) if currency_match is not None else None
        return currency is not None and _currency_is_explicit(currency, text)
    return bool(
        all(
            any(
                re.search(rf"(?<![\w]){re.escape(term)}(?:s|es)?(?![\w])", normalized_text)
                for term in _UNIT_TERM_ALIASES.get(word, (word,))
            )
            for word in unit_words
        )
    )


def _evidence_supports_case(case: QueryGoldCase, evidence: Any) -> bool:
    return (
        _gold_is_explicit(case, [evidence])
        and _scope_is_explicit_in_evidence(case, [evidence])
        and _units_are_explicit(case, [evidence])
        and (
            case.gold.currency is None
            or _currency_is_explicit(
                case.gold.currency,
                f"{evidence.title} {evidence.excerpt} {evidence.publishedAt or ''} "
                f"{evidence.effectiveDate or ''}",
            )
        )
    )


def _is_numeric_or_date_answer(answer: str) -> bool:
    stripped = answer.strip()
    if not any(character.isalpha() for character in stripped):
        return True
    return bool(
        re.fullmatch(
            r"\d{4}(?:-\d{2}(?:-\d{2})?)?(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?",
            stripped,
        )
    )


def _validate_case_query(case: QueryGoldCase, report: ValidationReport) -> tuple[bool, bool, bool]:
    category = case.categoryId
    red_flags = (
        (
            _CONTEXT_DEPENDENT_PATTERN,
            "query_context_dependent",
            "Query contains a vague reference that depends on hidden context.",
        ),
        (
            _DERIVED_OR_MULTI_HOP_PATTERN,
            "query_derived_or_multi_hop",
            "Query asks for calculation, synthesis, or multi-document research.",
        ),
        (
            _SEARCH_INSTRUCTION_PATTERN,
            "query_contains_navigation_instructions",
            "Query must be a direct question, not instructions for search navigation.",
        ),
    )
    for pattern, code, message in red_flags:
        if pattern.search(case.query):
            report.add(ValidationIssue("error", code, message, case.id, category))
    if _query_is_compound(case.query, category):
        report.add(
            ValidationIssue(
                "error",
                "query_compound",
                "Query combines multiple questions or independently answerable fields.",
                case.id,
                category,
            )
        )
    scope_is_obvious = _query_scope_is_obvious(case)
    if case.temporal.kind != "immutable" and not scope_is_obvious:
        report.add(
            ValidationIssue(
                "error",
                "temporal_scope_not_obvious_in_query",
                "Mutable query scope must be stated clearly in natural language.",
                case.id,
                category,
            )
        )
    if _UNBOUNDED_TIME_PATTERN.search(case.query) and (
        case.temporal.kind == "immutable" or not scope_is_obvious
    ):
        report.add(
            ValidationIssue(
                "error",
                "query_uses_unbounded_current_time",
                "Latest/current wording needs an explicit matching date, period, or version.",
                case.id,
                category,
            )
        )

    has_entity = _query_has_entity_or_identifier(case.query)
    if not has_entity:
        report.add(
            ValidationIssue(
                "warning",
                "query_entity_or_identifier_unclear",
                "Heuristic did not identify an entity or unique identifier; review manually.",
                case.id,
                category,
            )
        )
    has_field = _query_has_metric_or_field(case.query, category)
    if not has_field:
        report.add(
            ValidationIssue(
                "warning",
                "query_metric_or_field_unclear",
                "Heuristic did not identify a requested metric/field; review manually.",
                case.id,
                category,
            )
        )
    return scope_is_obvious, has_entity, has_field


def _validate_case_evidence(case: QueryGoldCase, report: ValidationReport) -> tuple[bool, bool]:
    category = case.categoryId
    public_evidence = [evidence for evidence in case.evidence if _is_public_answer_page(evidence)]
    if not public_evidence:
        report.add(
            ValidationIssue(
                "error",
                "public_answer_page_missing",
                "Evidence is API/raw-data-only; add a plausible public answer-bearing page.",
                case.id,
                category,
            )
        )
        complete_public_support = False
    else:
        complete_public_support = any(
            _evidence_supports_case(case, evidence) for evidence in public_evidence
        )
        if not complete_public_support:
            report.add(
                ValidationIssue(
                    "error",
                    "public_page_does_not_support_complete_gold",
                    "No public page excerpt supports answer, scope, and units together.",
                    case.id,
                    category,
                )
            )
    has_gold = _gold_is_explicit(case)
    if not has_gold:
        report.add(
            ValidationIssue(
                "error",
                "gold_not_explicit_in_evidence",
                "No supplied excerpt literally states the canonical or accepted gold answer.",
                case.id,
                category,
            )
        )
    if case.temporal.kind != "immutable" and not _scope_is_explicit_in_evidence(case):
        report.add(
            ValidationIssue(
                "error",
                "temporal_scope_not_explicit_in_evidence",
                "No excerpt/date/revision explicitly supports the declared temporal scope.",
                case.id,
                category,
            )
        )
    if not _units_are_explicit(case):
        report.add(
            ValidationIssue(
                "error",
                "gold_units_not_explicit_in_evidence",
                "Declared gold.units are not stated with the source answer.",
                case.id,
                category,
            )
        )
    if case.gold.currency and not _currency_is_explicit(
        case.gold.currency,
        " ".join(evidence.excerpt for evidence in case.evidence),
    ):
        report.add(
            ValidationIssue(
                "error",
                "gold_currency_not_explicit_in_evidence",
                "Declared gold.currency is not explicit in the supplied source excerpts.",
                case.id,
                category,
            )
        )
    return bool(public_evidence), complete_public_support


def _report_answer_annotations(
    case: QueryGoldCase, report: ValidationReport
) -> tuple[int, int, int, int]:
    category = case.categoryId
    duration_missing = int(
        bool(_DURATION_ANSWER_PATTERN.fullmatch(case.gold.answer)) and not case.gold.units
    )
    if duration_missing:
        report.add(
            ValidationIssue(
                "warning",
                "duration_units_missing",
                "A duration-like answer has no explicit gold.units value.",
                case.id,
                category,
            )
        )

    financial_case = category in {
        "01_earnings_corporate_finance",
        "04_venture_capital_funding_ma",
    }
    currency_like = financial_case and bool(_CURRENCY_PATTERN.search(case.gold.answer))
    financial_units_missing = int(currency_like and not case.gold.units)
    financial_currency_missing = int(currency_like and not case.gold.currency)
    if financial_units_missing:
        report.add(
            ValidationIssue(
                "warning",
                "financial_units_missing",
                "A currency-like answer has no explicit gold.units value.",
                case.id,
                category,
            )
        )
    if financial_currency_missing:
        report.add(
            ValidationIssue(
                "warning",
                "financial_currency_missing",
                "A currency-like answer has no explicit gold.currency value.",
                case.id,
                category,
            )
        )

    normalized_answer = normalize_text(case.gold.answer)
    answer_leak = int(
        len(normalized_answer) >= 5
        and not _is_numeric_or_date_answer(case.gold.answer)
        and normalized_answer in normalize_text(case.query)
    )
    if answer_leak:
        report.add(
            ValidationIssue(
                "warning",
                "canonical_answer_in_query",
                "The non-numeric canonical answer appears verbatim in the query.",
                case.id,
                category,
            )
        )
    if case.temporal.kind not in {"immutable", "version"} and not any(
        e.publishedAt or e.effectiveDate for e in case.evidence
    ):
        report.add(
            ValidationIssue(
                "warning",
                "evidence_source_date_missing",
                "Mutable-scope evidence has no publishedAt/effectiveDate metadata.",
                case.id,
                category,
            )
        )
    return duration_missing, financial_units_missing, financial_currency_missing, answer_leak


def _category_concentration(
    report: ValidationReport,
    policy: ValidationPolicy,
    source_ids: dict[str, Counter[str]],
    source_families: dict[str, Counter[str]],
    question_types: dict[str, Counter[str]],
    evidence_date_cases: Counter[str],
    clinical_date_cases: Counter[str],
) -> dict[str, Any]:
    concentration: dict[str, Any] = {}
    for category in policy.categories:
        ids = source_ids[category]
        family_counts = source_families[category]
        subtype_counts = question_types[category]
        cases_in_category = report.categoryCounts.get(category, 0)
        concentration[category] = {
            "distinctSourceRecordIds": len(ids),
            "sourceRecordCaseCounts": dict(sorted(ids.items())),
            "sourceFamilies": dict(sorted(family_counts.items())),
            "questionTypes": dict(sorted(subtype_counts.items())),
            "distinctQuestionTypes": len(subtype_counts),
            "evidenceDateCases": evidence_date_cases[category],
            "evidenceDateCoverage": (
                evidence_date_cases[category] / cases_in_category if cases_in_category else 0.0
            ),
            "clinicalTrialDateCases": clinical_date_cases[category],
        }
        if len(ids) < policy.min_distinct_source_ids:
            report.add(
                ValidationIssue(
                    "error",
                    "source_record_diversity_below_minimum",
                    f"Category has fewer than {policy.min_distinct_source_ids} distinct "
                    "sourceRecordIds.",
                    categoryId=category,
                )
            )
        if len(subtype_counts) < policy.min_question_types:
            report.add(
                ValidationIssue(
                    "error",
                    "question_type_diversity_below_minimum",
                    f"Category has fewer than {policy.min_question_types} distinct questionTypes.",
                    categoryId=category,
                )
            )
        if ids:
            most_common_id, top_count = ids.most_common(1)[0]
            if top_count >= policy.source_concentration_warning_cases:
                report.add(
                    ValidationIssue(
                        "warning",
                        "source_record_concentration",
                        f"One sourceRecordId appears in {top_count} cases; inspect concentration.",
                        categoryId=category,
                    )
                )
            concentration[category]["mostRepeatedSourceRecordId"] = most_common_id
    return concentration


def _collect_quality(
    cases: list[QueryGoldCase], report: ValidationReport, policy: ValidationPolicy
) -> None:
    source_ids: dict[str, Counter[str]] = defaultdict(Counter)
    source_families: dict[str, Counter[str]] = defaultdict(Counter)
    question_types: dict[str, Counter[str]] = defaultdict(Counter)
    evidence_date_cases: Counter[str] = Counter()
    clinical_date_cases: Counter[str] = Counter()
    duration_missing = 0
    financial_units_missing = 0
    financial_currency_missing = 0
    exact_answer_leaks = 0
    obvious_temporal_scopes = 0
    entity_missing = 0
    field_missing = 0
    public_page_cases = 0
    public_answer_supported_cases = 0

    for case in cases:
        category = case.categoryId
        question_types[category][case.derivation.questionType] += 1
        source_families[category][case.derivation.sourceFamily] += 1
        scope_is_obvious, has_entity, has_field = _validate_case_query(case, report)
        entity_missing += int(not has_entity)
        field_missing += int(not has_field)
        obvious_temporal_scopes += int(scope_is_obvious)

        has_public_page, has_public_support = _validate_case_evidence(case, report)
        public_page_cases += int(has_public_page)
        public_answer_supported_cases += int(has_public_support)

        duration_count, financial_unit_count, currency_count, answer_leak_count = (
            _report_answer_annotations(case, report)
        )
        duration_missing += duration_count
        financial_units_missing += financial_unit_count
        financial_currency_missing += currency_count
        exact_answer_leaks += answer_leak_count

        source_record_ids = {
            evidence.sourceRecordId
            for evidence in case.evidence
            if evidence.sourceRecordId is not None
        }
        for source_record_id in source_record_ids:
            source_ids[category][source_record_id] += 1
        has_evidence_date = any(
            evidence.publishedAt or evidence.effectiveDate for evidence in case.evidence
        )
        if has_evidence_date:
            evidence_date_cases[category] += 1
        if category == "02_biomedical_clinical_trials" and has_evidence_date:
            clinical_date_cases[category] += 1

    concentration = _category_concentration(
        report,
        policy,
        source_ids,
        source_families,
        question_types,
        evidence_date_cases,
        clinical_date_cases,
    )
    clinical_count = report.categoryCounts.get("02_biomedical_clinical_trials", 0)
    clinical_coverage = (
        clinical_date_cases["02_biomedical_clinical_trials"] / clinical_count
        if clinical_count
        else 0.0
    )
    report.sourceConcentration = concentration
    report.quality = {
        "temporalScopeExplicitHeuristicCases": obvious_temporal_scopes,
        "queryEntityOrIdentifierUnclear": entity_missing,
        "queryMetricOrFieldUnclear": field_missing,
        "canonicalAnswerLeakWarnings": exact_answer_leaks,
        "durationUnitsMissing": duration_missing,
        "financialUnitsMissing": financial_units_missing,
        "financialCurrencyMissing": financial_currency_missing,
        "publicAnswerPageCoverage": public_page_cases / len(cases) if cases else 0.0,
        "publicPageCompleteGoldSupportCoverage": (
            public_answer_supported_cases / len(cases) if cases else 0.0
        ),
        "clinicalTrialEvidenceDateCoverage": clinical_coverage,
        "domainSubstantiveReview": (
            "manual sample review required; search discoverability/top-five "
            "appearance is not inferred"
        ),
    }


def validate_records(
    records: Iterable[QueryGoldCase],
    *,
    category_dirs: Mapping[str, Path] | None = None,
    policy: ValidationPolicy = DEFAULT_VALIDATION_POLICY,
    dataset_sha256: str | None = None,
) -> ValidationReport:
    """Validate canonical records and return machine-readable errors/warnings."""
    cases = list(records)
    report = ValidationReport(caseCount=len(cases), datasetSha256=dataset_sha256)
    category_counts = Counter(case.categoryId for case in cases)
    report.categoryCounts = {category: category_counts[category] for category in policy.categories}

    ids: dict[str, str] = {}
    queries: dict[str, str] = {}
    for case in cases:
        previous_id = ids.get(case.id)
        if previous_id is not None:
            report.add(
                ValidationIssue(
                    "error",
                    "duplicate_id",
                    "Case ID is not unique.",
                    case.id,
                    case.categoryId,
                )
            )
        else:
            ids[case.id] = case.categoryId
        normalized_query = normalize_text(case.query)
        if normalized_query in queries:
            report.add(
                ValidationIssue(
                    "error",
                    "duplicate_normalized_query",
                    "Normalized query duplicates another case.",
                    case.id,
                    case.categoryId,
                )
            )
        else:
            queries[normalized_query] = case.id
        if case.categoryId not in policy.categories:
            report.add(
                ValidationIssue(
                    "error",
                    "unexpected_category",
                    "Case category is outside the configured dataset categories.",
                    case.id,
                    case.categoryId,
                )
            )

    if policy.require_all_categories:
        for category in policy.categories:
            if category_counts[category] == 0:
                report.add(
                    ValidationIssue(
                        "error",
                        "category_missing",
                        "A required category has no cases.",
                        categoryId=category,
                    )
                )
    if policy.expected_count_per_category is not None:
        for category in policy.categories:
            actual = category_counts[category]
            if actual != policy.expected_count_per_category:
                report.add(
                    ValidationIssue(
                        "error",
                        "category_count_mismatch",
                        f"Expected {policy.expected_count_per_category} cases; found {actual}.",
                        categoryId=category,
                    )
                )

    if category_dirs is not None:
        raw_cache: dict[Path, tuple[str, str]] = {}
        for case in cases:
            _validate_evidence(case, category_dirs, raw_cache, report)

    _collect_quality(cases, report, policy)
    return report


def rejection_report(report: ValidationReport) -> dict[str, Any]:
    """Project validation errors into a private rejected-candidate report."""
    rejected: dict[str, list[str]] = defaultdict(list)
    for issue in report.errors:
        key = issue.caseId or issue.categoryId or "dataset"
        rejected[key].append(issue.code)
    return {
        "schemaVersion": "query-gold-rejections/v1",
        "valid": report.valid,
        "rejectedCount": len(rejected),
        "rejections": [
            {"recordOrCategoryId": key, "reasonCodes": sorted(set(codes))}
            for key, codes in sorted(rejected.items())
        ],
    }
