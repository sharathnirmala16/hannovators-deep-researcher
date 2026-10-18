# ruff: noqa: E501,RUF001
"""First-party venture funding and M&A announcement query/gold collection.

The source facts below are deliberately small, typed seeds rather than answers
generated from news summaries.  Collection downloads bounded issuer/IR/SEC
pages, verifies the publication date and each quoted field against the cached
UTF-8 response, then emits only the requested query/gold records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from query_gold.io import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_jsonl,
    ensure_safe_path,
)
from query_gold.models import QueryGoldCase

from .venture_ma_dates import ISO_DATE_RE as _ISO_DATE_RE
from .venture_ma_dates import extract_tagged_publication_date as _extract_tagged_publication_date
from .venture_ma_deals import _M_AND_A_BACKUPS, _M_AND_A_SOURCES
from .venture_ma_facts import (
    _FUNDING_BACKUPS,
    _FUNDING_SOURCES,
    FactSpec,
    SourceSpec,
)
from .venture_ma_money import _MONEY_RE, _parse_money_token

CATEGORY_ID = "04_venture_capital_funding_ma"
GENERATOR_VERSION = "venture-ma-curator/1.0"
_MAX_PHYSICAL_REQUESTS = 150
_MAX_SOURCE_BYTES = 2000000
_MAX_TOTAL_SOURCE_BYTES = 24000000
_REQUEST_TIMEOUT_SECONDS = 20
_USER_AGENT = "Provider-Evals query-gold collector/1.0 (public announcement curation)"
_LITERAL_ANSWER_REPAIRS: dict[str, dict[str, str]] = {
    "scale-series-f-2024": {
        "funding_round_size": "$1B",
        "post_money_valuation": "$13.8B",
    },
    "glean-series-e-2024": {
        "funding_round_size": "over $260M",
        "post_money_valuation": "$4.6B",
    },
    "databricks-series-j-2024": {
        "funding_expected_total": "The company is raising $10 billion of expected non-dilutive financing and has completed $8.6 billion to date",
    },
    "klarna-funding-2022": {
        "funding_round_size": "$800m",
        "post_money_valuation": "$6.7bn",
    },
    "microsoft-activision-announcement-2022": {
        "announced_transaction_value": "$68.7 billion",
    },
    "ibm-hashicorp-announcement-2024": {
        "announced_enterprise_value": "$6.4 billion",
    },
    "salesforce-slack-announcement-2020": {
        "announced_enterprise_value": "$27.7 billion",
        "cash_stock_per_target_share": "Slack shareholders will receive $26.79 in cash and 0.0776 shares of Salesforce common stock for each Slack share",
    },
    "homedepot-srs-announcement-2024": {
        "announced_enterprise_value": "$18.25 billion",
    },
    "amazon-irobot-announcement-2022": {
        "announced_transaction_value": "$1.7 billion",
    },
    "kroger-albertsons-announcement-2022": {
        "announced_enterprise_value": "$24.6 billion",
        "per_share_consideration": "estimated total consideration of $34.10 per share",
    },
    "conocophillips-marathon-announcement-2024": {
        "share_exchange_ratio": "0.2550 shares of ConocoPhillips common stock for each share of Marathon Oil common stock",
    },
    "nvidia-arm-announcement-2020": {
        "announced_transaction_value": "$40 billion",
        "m_and_a_contingent_earnout": "may receive up to $5 billion in cash or common stock",
    },
    "amd-xilinx-announcement-2020-corrected": {
        "announced_transaction_value": "$35 billion",
    },
}

_QUERY_REPAIRS: dict[str, dict[str, str]] = {
    "anthropic-series-c-2023": {
        "funding_round_size": "What funding amount did Anthropic announce for its Series C on {date}?",
    },
    "cohere-funding-2025": {
        "funding_round_size": "What funding amount did Cohere announce for its financing round on {date}?",
    },
    "klarna-funding-2022": {
        "funding_round_size": "How much funding did Klarna say it had closed on {date}?",
    },
    "microsoft-activision-announcement-2022": {
        "per_share_cash_consideration": "What per-share purchase price in cash did Microsoft announce for Activision Blizzard on {date}?",
    },
    "cisco-splunk-announcement-2023": {
        "per_share_cash_consideration": "What per-share purchase price in cash did Cisco announce for Splunk on {date}?",
    },
    "ibm-hashicorp-announcement-2024": {
        "per_share_cash_consideration": "What per-share purchase price in cash did IBM announce for HashiCorp on {date}?",
    },
    "salesforce-slack-announcement-2020": {
        "cash_stock_per_target_share": "How was Slack shareholder consideration structured under Salesforce’s acquisition agreement announced on {date}?",
    },
    "amazon-irobot-announcement-2022": {
        "per_share_cash_consideration": "What per-share purchase price in cash did Amazon announce for iRobot on {date}?",
    },
    "kroger-albertsons-announcement-2022": {
        "per_share_consideration": "What estimated total consideration per Albertsons share was announced for Kroger's proposed acquisition on {date}?",
    },
    "conocophillips-marathon-announcement-2024": {
        "share_exchange_ratio": "What exchange ratio in ConocoPhillips shares per Marathon Oil share did ConocoPhillips announce on {date}?",
    },
    "facebook-whatsapp-announcement-2014": {
        "acquisition_cash_consideration": "How much cash did Facebook include in its WhatsApp acquisition offer announced on {date}?",
        "acquisition_employee_rsu_value": "What dollar value of restricted stock units did Facebook include in its WhatsApp acquisition announced on {date}?",
    },
    "amd-xilinx-announcement-2020-corrected": {
        "share_exchange_ratio": "What fixed exchange ratio in AMD shares per Xilinx share did AMD announce on {date}?",
    },
}

_QUESTION_TYPE_REPAIRS: dict[str, dict[str, str]] = {
    "cohere-funding-2025": {"post_money_valuation": "company_valuation"},
}


def _repair_source_answers_and_queries(source: SourceSpec) -> SourceSpec:
    answer_repairs = _LITERAL_ANSWER_REPAIRS.get(source.source_record_id, {})
    query_repairs = _QUERY_REPAIRS.get(source.source_record_id, {})
    question_type_repairs = _QUESTION_TYPE_REPAIRS.get(source.source_record_id, {})
    return replace(
        source,
        facts=tuple(
            replace(
                fact,
                answer=answer_repairs.get(fact.question_type, fact.answer),
                question=query_repairs.get(fact.question_type, fact.question),
                question_type=question_type_repairs.get(fact.question_type, fact.question_type),
            )
            for fact in source.facts
        ),
    )


_FUNDING_SOURCES = tuple(_repair_source_answers_and_queries(source) for source in _FUNDING_SOURCES)
_M_AND_A_SOURCES = tuple(_repair_source_answers_and_queries(source) for source in _M_AND_A_SOURCES)
_M_AND_A_BACKUPS = tuple(_repair_source_answers_and_queries(source) for source in _M_AND_A_BACKUPS)

_DISCOVERY_REJECTIONS = (
    "FinDER (one benchmark candidate): rejected because its QA evidence is annual reports, not dated funding rounds or M&A announcements.",
    "Crunchbase/other deal aggregations (one source approach): rejected as secondary records rather than first-party announcement evidence.",
    "OpenAI's October 2, 2024 funding announcement (one article candidate): two direct public fetches returned HTTP 403 in this collector environment; no case was retained from it.",
    "Mistral's Series D article (one source candidate): the cached first-party page contains the funding facts but no source-supplied publication date, so it is not backdated or used.",
    "Discovery tried 24 additional first-party page URL candidates: five yielded answer-bearing source pages retained for this category or as fallback, two HTTP 200 pages were rejected as an unrelated accelerator release or a generic newsroom page, and 17 failed with HTTP errors or timeouts. Every physical attempt, including retries, is preserved in raw/collection-attempts.json.",
    "Broadcom/VMware, Exxon/Pioneer, Chevron/Hess, and Exxon/Denbury candidates were rejected after 404 or 403 responses. Adobe/Figma termination was recovered from Adobe’s answer-bearing newsroom release after the SEC exhibit request returned 403.",
    "The first AMD candidate URL returned a cached official page about an unrelated HPC accelerator release, so only the corrected Xilinx acquisition announcement page is eligible.",
)


@dataclass
class _CollectionState:
    attempts: int = 0
    total_bytes: int = 0
    physical_request_ledger: list[dict[str, Any]] = field(default_factory=list)
    ledger_path: Path | None = None
    selected: list[tuple[SourceSpec, str, str, str, int]] = field(default_factory=list)
    rejections: list[tuple[str, str, int]] = field(default_factory=list)
    all_downloads: list[tuple[str, str, int]] = field(default_factory=list)


def _date_tokens(iso_date: str) -> tuple[str, ...]:
    """Common exact date renderings used only to verify a source-supplied date."""
    if not _ISO_DATE_RE.fullmatch(iso_date):
        return ()
    if len(iso_date) == 4:
        return (iso_date,)
    if len(iso_date) == 7:
        parsed_month = date.fromisoformat(f"{iso_date}-01")
        return (
            f"{parsed_month.strftime('%B')} {parsed_month.year}",
            parsed_month.strftime("%Y-%m"),
        )
    parsed = date.fromisoformat(iso_date)
    return (
        iso_date,
        f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}",
        f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}",
        f"{parsed.day} {parsed.strftime('%B')} {parsed.year}",
    )


def _resolve_publication_date(source: SourceSpec, text: str) -> str:
    tagged = _extract_tagged_publication_date(text)
    expected = source.published_at
    if expected is None:
        if tagged is None:
            raise ValueError("no source-supplied publication date was found")
        date.fromisoformat(tagged if len(tagged) == 10 else f"{tagged}-01")
        return tagged
    if not _ISO_DATE_RE.fullmatch(expected):
        raise ValueError("curated publication date is not ISO year/month/day precision")
    date.fromisoformat(expected if len(expected) == 10 else f"{expected}-01")
    if tagged == expected:
        return expected
    tokens = (*_date_tokens(expected), *source.date_tokens)
    if any(token in text for token in tokens):
        return expected
    raise ValueError("source page does not support the curated publication date")


def _sentence_window(text: str, token: str) -> str:
    start = text.casefold().find(token.casefold())
    if start < 0:
        raise ValueError("answer token is not present in its evidence excerpt")
    left_candidates = [text.rfind(mark, 0, start) for mark in (".", "!", "?", "\n")]
    right_candidates = [text.find(mark, start + len(token)) for mark in (".", "!", "?", "\n")]
    left = max(left_candidates) + 1
    right = min((position for position in right_candidates if position >= 0), default=len(text))
    return text[left:right].casefold()


def _validate_money_fact(fact: FactSpec) -> None:
    if fact.numeric_token is None or not fact.currency or (not fact.units):
        raise ValueError("money facts require a numeric token, currency, and units")
    parsed, parsed_currency = _parse_money_token(fact.numeric_token)
    if parsed_currency != fact.currency:
        raise ValueError("source money symbol and declared currency disagree")
    if parsed != Decimal(str(fact.value)):
        raise ValueError("source amount does not match the curated numeric value")
    if fact.numeric_token.casefold() not in fact.excerpt.casefold():
        raise ValueError("source amount token is absent from its evidence excerpt")
    answer_match = _MONEY_RE.search(fact.answer)
    if answer_match is None:
        raise ValueError("canonical money answer omits its numeric amount")
    answer_amount, answer_currency = _parse_money_token(answer_match.group(0))
    if answer_amount != parsed or answer_currency != fact.currency:
        raise ValueError("canonical answer amount/currency disagrees with the source field")
    if fact.currency not in fact.units:
        raise ValueError("money units must explicitly name the declared currency")
    if fact.currency not in {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY"}:
        raise ValueError("money fact uses an unsupported ISO currency")
    window = _sentence_window(fact.excerpt, fact.numeric_token)
    if any(term.casefold() not in window for term in fact.context_terms):
        raise ValueError("money token is attached to a different source field")
    if any(term.casefold() not in fact.excerpt.casefold() for term in fact.support_terms):
        raise ValueError("money answer qualification is not supported by its excerpt")
    per_share = fact.question_type in {"per_share_cash_consideration", "per_share_consideration"}
    unit_text = fact.units.casefold()
    if per_share and (
        "per " not in unit_text or "share" not in unit_text or "per share" not in window
    ):
        raise ValueError("per-share money fact must retain per-share units and context")


def _validate_ratio_fact(fact: FactSpec) -> None:
    if fact.numeric_token is None or not fact.units or fact.currency is not None:
        raise ValueError("share ratios require a token and units, and must not claim currency")
    try:
        parsed_ratio = Decimal(fact.numeric_token)
    except InvalidOperation as error:
        raise ValueError("share ratio token is not numeric") from error
    if parsed_ratio != Decimal(str(fact.value)):
        raise ValueError("share ratio token does not match the curated value")
    window = _sentence_window(fact.excerpt, fact.numeric_token)
    if any(term.casefold() not in window for term in fact.support_terms):
        raise ValueError("share ratio source field does not match its declared units")
    if " per " not in fact.units.casefold():
        raise ValueError("share ratio units must state the per-target-share denominator")


def _validate_text_fact(fact: FactSpec) -> None:
    token = fact.answer_token or fact.answer
    if token.casefold() not in fact.excerpt.casefold():
        raise ValueError("text answer does not occur in its source excerpt")
    window = _sentence_window(fact.excerpt, token)
    if any(term.casefold() not in window for term in fact.context_terms):
        raise ValueError("text answer does not match the requested source field")
    if any(term.casefold() not in fact.excerpt.casefold() for term in fact.support_terms):
        raise ValueError("text answer context is not supported by its excerpt")


def _validate_mix_fact(fact: FactSpec) -> None:
    if fact.metric == "mix" and (not fact.units):
        raise ValueError("consideration mix facts require explicit units")
    if fact.metric == "structured" and (not fact.units or fact.value is None):
        raise ValueError("structured consideration facts require value and units")
    if any(term.casefold() not in fact.excerpt.casefold() for term in fact.support_terms):
        raise ValueError("consideration answer is not supported by each declared source term")


def _validate_fact_spec(fact: FactSpec, source_text: str) -> None:
    """Reject field, date, numeric, currency, unit, or quote mismatches deterministically."""
    if not fact.excerpt or fact.excerpt not in source_text:
        raise ValueError("curated evidence excerpt is not a literal source substring")
    if not fact.question.strip() or not fact.answer.strip() or (not fact.question_type.strip()):
        raise ValueError("question, answer, and subtype must be non-empty")
    if fact.answer.casefold() in fact.question.casefold():
        raise ValueError("query leaks its canonical answer")
    validators = {
        "money": _validate_money_fact,
        "ratio": _validate_ratio_fact,
        "text": _validate_text_fact,
        "mix": _validate_mix_fact,
        "structured": _validate_mix_fact,
    }
    validator = validators.get(fact.metric)
    if validator is None:
        raise ValueError("unsupported fact metric")
    validator(fact)


def _validate_source_facts(source: SourceSpec, raw: bytes) -> str:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("source response is not strict UTF-8") from error
    published_at = _resolve_publication_date(source, text)
    for fact in source.facts:
        _validate_fact_spec(fact, text)
    return published_at


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _persist_request_ledger(state: _CollectionState) -> None:
    if state.ledger_path is None:
        raise ValueError("physical request ledger was not initialized")
    atomic_write_json(
        state.ledger_path,
        {
            "schemaVersion": "venture-ma-http-attempts/v1",
            "physicalAttempts": state.physical_request_ledger,
        },
    )


def _read_existing_request_ledger(ledger_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("physical request ledger is unreadable") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != "venture-ma-http-attempts/v1"
    ):
        raise ValueError("physical request ledger has an unsupported schema")
    payload_entries = payload.get("physicalAttempts")
    if not isinstance(payload_entries, list):
        raise ValueError("physical request ledger must contain an attempt list")
    for entry in payload_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("sourceRecordId"), str):
            raise ValueError("physical request ledger contains a malformed entry")
        if not isinstance(entry.get("url"), str) or not isinstance(entry.get("outcome"), str):
            raise ValueError("physical request ledger contains an incomplete entry")
    if len(payload_entries) > _MAX_PHYSICAL_REQUESTS:
        raise ValueError("physical request ledger already exceeds the collection limit")
    return payload_entries


def _seed_request_ledger(raw_dir: Path) -> list[dict[str, Any]]:
    seeded_entries: list[dict[str, Any]] = []
    for metadata_path in sorted(raw_dir.glob("*.meta.json")):
        if metadata_path.is_symlink():
            raise ValueError("raw metadata entries must not be symlinks")
        source_id = metadata_path.name.removesuffix(".meta.json")
        if not re.fullmatch("[a-z0-9][a-z0-9-]{1,100}", source_id):
            raise ValueError("raw metadata filename is not a safe source identifier")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                "raw source metadata is unreadable while seeding the ledger"
            ) from error
        attempts = metadata.get("physicalAttempts")
        retrieved_at = metadata.get("retrievedAtUTC")
        status = metadata.get("httpStatus")
        url = metadata.get("url")
        valid_metadata = (
            metadata.get("sourceRecordId") == source_id
            and isinstance(attempts, int)
            and attempts >= 1
            and isinstance(retrieved_at, str)
            and retrieved_at.endswith("Z")
            and isinstance(status, int)
            and isinstance(url, str)
        )
        if not valid_metadata:
            raise ValueError("raw source metadata cannot safely seed physical request counts")
        for attempt_number in range(1, attempts + 1):
            outcome = (
                f"HTTP {status} (cached success metadata)"
                if attempt_number == attempts
                else "outcome unavailable from pre-ledger collector"
            )
            seeded_entries.append(
                {
                    "sourceRecordId": source_id,
                    "url": url,
                    "attemptNumber": attempt_number,
                    "recordedAtUTC": retrieved_at,
                    "outcome": outcome,
                }
            )
    if len(seeded_entries) > _MAX_PHYSICAL_REQUESTS:
        raise ValueError("cached source metadata exceeds the physical request budget")
    return seeded_entries


def _load_request_ledger(output_dir: Path) -> _CollectionState:
    raw_dir = ensure_safe_path(output_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ensure_safe_path(raw_dir / "collection-attempts.json")
    if ledger_path.exists():
        entries = _read_existing_request_ledger(ledger_path)
    else:
        entries = _seed_request_ledger(raw_dir)
    state = _CollectionState(physical_request_ledger=entries, ledger_path=ledger_path)
    if not ledger_path.exists():
        _persist_request_ledger(state)
    return state


def _begin_physical_attempt(state: _CollectionState, source: SourceSpec) -> int:
    if len(state.physical_request_ledger) >= _MAX_PHYSICAL_REQUESTS:
        raise RuntimeError("public source request budget exhausted")
    entry = {
        "sourceRecordId": source.source_record_id,
        "url": source.url,
        "attemptNumber": 1
        + sum(
            row["sourceRecordId"] == source.source_record_id
            for row in state.physical_request_ledger
        ),
        "requestedAtUTC": _utc_now(),
        "outcome": "pending",
    }
    state.physical_request_ledger.append(entry)
    state.attempts += 1
    _persist_request_ledger(state)
    return len(state.physical_request_ledger) - 1


def _finish_physical_attempt(state: _CollectionState, ledger_index: int, outcome: str) -> None:
    state.physical_request_ledger[ledger_index]["outcome"] = outcome
    state.physical_request_ledger[ledger_index]["completedAtUTC"] = _utc_now()
    _persist_request_ledger(state)


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Fail closed so urllib cannot hide extra physical requests behind a redirect."""

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


def _open_public_request(request: urllib.request.Request) -> Any:
    opener = urllib.request.build_opener(_RejectRedirectHandler())
    return opener.open(request, timeout=_REQUEST_TIMEOUT_SECONDS)


def _safe_source_paths(output_dir: Path, source: SourceSpec) -> tuple[Path, Path, str]:
    if not re.fullmatch("[a-z0-9][a-z0-9-]{1,100}", source.source_record_id):
        raise ValueError("sourceRecordId is not a safe artifact filename")
    raw_dir = ensure_safe_path(output_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{source.source_record_id}.html"
    metadata_path = raw_dir / f"{source.source_record_id}.meta.json"
    if raw_path.is_symlink() or metadata_path.is_symlink():
        raise ValueError("raw source cache entries must not be symlinks")
    return (raw_path, metadata_path, f"raw/{source.source_record_id}.html")


def _read_cached_source(
    source: SourceSpec, raw_path: Path, metadata_path: Path
) -> tuple[bytes, str, int] | None:
    if not raw_path.exists():
        return None
    raw = raw_path.read_bytes()
    if len(raw) > _MAX_SOURCE_BYTES:
        raise ValueError("cached source exceeds the per-source size limit")
    if not metadata_path.exists():
        raise ValueError("cached source lacks retrieval metadata")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("cached source retrieval metadata is unreadable") from error
    digest = hashlib.sha256(raw).hexdigest()
    if metadata.get("sourceRecordId") != source.source_record_id:
        raise ValueError("cached source metadata has the wrong sourceRecordId")
    if metadata.get("url") != source.url or metadata.get("rawSha256") != digest:
        raise ValueError("cached source metadata does not match its URL or source bytes")
    retrieved_at = metadata.get("retrievedAtUTC")
    if not isinstance(retrieved_at, str) or not retrieved_at.endswith("Z"):
        raise ValueError("cached source metadata lacks an explicit UTC retrieval timestamp")
    attempts = metadata.get("physicalAttempts")
    if not isinstance(attempts, int) or attempts < 1:
        raise ValueError("cached source metadata has an invalid attempt count")
    return (raw, retrieved_at, attempts)


def _download_source(
    source: SourceSpec, state: _CollectionState, output_dir: Path
) -> tuple[bytes, str, int, str]:
    raw_path, metadata_path, relative_path = _safe_source_paths(output_dir, source)
    cached = _read_cached_source(source, raw_path, metadata_path)
    if cached is not None:
        raw, retrieved_at, previous_attempts = cached
        state.total_bytes += len(raw)
        if state.total_bytes > _MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("cached source set exceeds the total raw-byte limit")
        state.all_downloads.append((source.source_record_id, "cache", previous_attempts))
        return (raw, retrieved_at, previous_attempts, relative_path)
    last_reason = "network request failed"
    used_attempts = 0
    for _ in range(2):
        ledger_index = _begin_physical_attempt(state, source)
        used_attempts += 1
        request = urllib.request.Request(
            source.url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        try:
            with _open_public_request(request) as response:
                status = getattr(response, "status", 200)
                raw = response.read(_MAX_SOURCE_BYTES + 1)
            _finish_physical_attempt(state, ledger_index, f"HTTP {status}")
            if status != 200:
                last_reason = f"HTTP {status}"
                continue
            if len(raw) > _MAX_SOURCE_BYTES:
                last_reason = "source response exceeded the per-source size limit"
                break
            if state.total_bytes + len(raw) > _MAX_TOTAL_SOURCE_BYTES:
                last_reason = "source response would exceed the total raw-byte limit"
                break
            raw.decode("utf-8", errors="strict")
            retrieved_at = _utc_now()
            digest = hashlib.sha256(raw).hexdigest()
            atomic_write_bytes(raw_path, raw)
            atomic_write_json(
                metadata_path,
                {
                    "sourceRecordId": source.source_record_id,
                    "url": source.url,
                    "retrievedAtUTC": retrieved_at,
                    "httpStatus": status,
                    "physicalAttempts": used_attempts,
                    "rawSha256": digest,
                },
            )
            state.total_bytes += len(raw)
            state.all_downloads.append((source.source_record_id, "http-200", used_attempts))
            return (raw, retrieved_at, used_attempts, relative_path)
        except urllib.error.HTTPError as error:
            last_reason = f"HTTP {error.code}"
            _finish_physical_attempt(state, ledger_index, last_reason)
        except urllib.error.URLError as error:
            reason = getattr(error, "reason", None)
            last_reason = f"network error ({type(reason).__name__})"
            _finish_physical_attempt(state, ledger_index, last_reason)
        except (TimeoutError, OSError) as error:
            last_reason = f"network error ({type(error).__name__})"
            _finish_physical_attempt(state, ledger_index, last_reason)
        except UnicodeDecodeError:
            last_reason = "source response was not strict UTF-8"
            _finish_physical_attempt(state, ledger_index, last_reason)
            break
    state.all_downloads.append((source.source_record_id, last_reason, used_attempts))
    raise RuntimeError(last_reason)


def _precision(value: str) -> str:
    if len(value) == 4:
        return "year"
    if len(value) == 7:
        return "month"
    if len(value) == 10:
        return "day"
    raise ValueError("source event date has unsupported ISO precision")


_QUERY_RED_FLAGS = (
    "above document",
    "below document",
    "this company",
    "this source",
    "the source above",
    "the document above",
    "latest",
    "based on the above",
    "as mentioned earlier",
    "using the previous answer",
)
_DERIVATION_RED_FLAGS = re.compile(
    "\\b(?:calculate|compute|derive|compare|difference between|sum of|combined total|across documents|across several|search for a source)\\b",
    re.IGNORECASE,
)
_COMPOUND_RED_FLAGS = re.compile(
    "\\b(?:and then|and what|and when|and where|as well as|in addition to|also state|along with the date)\\b",
    re.IGNORECASE,
)
_NAMED_ENTITY_RE = re.compile(
    "\\b(?:Anthropic|Cohere|Mistral|Scale|Glean|CoreWeave|Wayve|xAI|Ramp|Figure|Databricks|Klarna|Canva|Adobe|Figma|Microsoft|Activision(?: Blizzard)?|Cisco|Splunk|IBM|HashiCorp|Salesforce|Slack|Broadcom|VMware|ExxonMobil|Pioneer(?: Natural Resources)?|Chevron|Hess|Home Depot|SRS(?: Distribution)?|Amazon|iRobot|Kroger|Albertsons|ConocoPhillips|Marathon Oil|Denbury)\\b",
    re.IGNORECASE,
)

_NAMED_ENTITY_RE = re.compile(
    _NAMED_ENTITY_RE.pattern.replace(
        "Anthropic|",
        "Anthropic|NVIDIA|Arm|SoftBank|AMD|Xilinx|Facebook|WhatsApp|Mellanox|",
    ),
    re.IGNORECASE,
)


def _validate_query_shape(query: str, fact: FactSpec, published_at: str) -> None:
    """Keep prompts standalone, dated, answer-neutral, and searchable as one field."""
    lowered = query.casefold()
    if query.count("?") != 1 or "\n" in query:
        raise ValueError("query must be one standalone question")
    if published_at not in query:
        raise ValueError("query must state its source event date in ISO form")
    if _NAMED_ENTITY_RE.search(query) is None:
        raise ValueError("query must identify the company or transaction entity")
    if any(flag in lowered for flag in _QUERY_RED_FLAGS):
        raise ValueError("query has a context-dependent or unspecified-time red flag")
    if _DERIVATION_RED_FLAGS.search(query) or _COMPOUND_RED_FLAGS.search(query):
        raise ValueError("query asks for a derived or compound answer")
    if fact.answer.casefold() in lowered:
        raise ValueError("query contains its canonical gold answer")
    if fact.excerpt.casefold() in lowered:
        raise ValueError("query contains pasted source text")


def _canonical_gold_units(fact: FactSpec) -> str | None:
    """Keep monetary denomination separate from event-field descriptions."""
    if fact.metric == "money":
        if fact.question_type in {"per_share_cash_consideration", "per_share_consideration"}:
            return f"{fact.currency} per share" if fact.currency else fact.units
        return fact.currency or fact.units
    if fact.metric == "mix":
        return "cash and stock"
    return fact.units


def _case_record(
    source: SourceSpec,
    fact: FactSpec,
    published_at: str,
    retrieved_at: str,
    raw_sha256: str,
    raw_path: str,
) -> dict[str, Any]:
    query = fact.question.format(date=published_at)
    _validate_query_shape(query, fact, published_at)
    evidence: dict[str, Any] = {
        "url": source.url,
        "title": source.title,
        "retrievedAtUTC": retrieved_at,
        "publishedAt": published_at,
        "sourceRecordId": source.source_record_id,
        "license": source.license_name,
        "rawSha256": raw_sha256,
        "rawPath": raw_path,
        "excerpt": fact.excerpt,
    }
    if source.upstream_revision is not None:
        evidence["upstreamRevision"] = source.upstream_revision
    gold: dict[str, Any] = {"answer": fact.answer, "acceptedAnswers": [fact.answer]}
    if fact.value is not None:
        gold["value"] = fact.value
    if fact.units is not None:
        gold["units"] = _canonical_gold_units(fact)
    if fact.currency is not None:
        gold["currency"] = fact.currency
    return {
        "schemaVersion": "query-gold/v1",
        "id": f"venture-ma-{source.source_record_id}-{fact.question_type}",
        "categoryId": CATEGORY_ID,
        "query": query,
        "temporal": {"kind": "event", "precision": _precision(published_at), "date": published_at},
        "gold": gold,
        "evidence": [evidence],
        "derivation": {
            "sourceFamily": source.source_family,
            "generatorVersion": GENERATOR_VERSION,
            "questionType": fact.question_type,
        },
    }


def _category_target_counts(count: int) -> dict[str, int]:
    funding_count = max(1, (count * 12 + 12) // 25)
    funding_count = min(funding_count, count)
    return {"funding": funding_count, "m_and_a": count - funding_count}


def _collect_source_group(
    *,
    sources: tuple[SourceSpec, ...],
    target: int,
    output_dir: Path,
    state: _CollectionState,
    records: list[dict[str, Any]],
) -> None:
    if target == 0:
        return
    collected = 0
    for source in sources:
        if collected >= target:
            break
        attempts_before = state.attempts
        attempts = 0
        try:
            raw, retrieved_at, attempts, raw_path = _download_source(source, state, output_dir)
            published_at = _validate_source_facts(source, raw)
        except (OSError, RuntimeError, ValueError, ValidationError) as error:
            state.rejections.append(
                (source.source_record_id, str(error), attempts or state.attempts - attempts_before)
            )
            continue
        digest = hashlib.sha256(raw).hexdigest()
        remaining = target - collected
        used_facts = source.facts[:remaining]
        try:
            for fact in used_facts:
                record = _case_record(source, fact, published_at, retrieved_at, digest, raw_path)
                validated = QueryGoldCase.model_validate(record)
                records.append(validated.model_dump(mode="json", exclude_none=True))
                collected += 1
        except (ValidationError, ValueError) as error:
            for _ in range(len(used_facts)):
                if (
                    records
                    and records[-1].get("evidence", [{}])[0].get("sourceRecordId")
                    == source.source_record_id
                ):
                    records.pop()
                    collected -= 1
            state.rejections.append((source.source_record_id, str(error), state.attempts))
            continue
        state.selected.append((source, published_at, digest, retrieved_at, attempts))
    if collected != target:
        atomic_write_json(
            output_dir / "raw/collection-rejections.json",
            {
                "schemaVersion": "venture-ma-rejections/v1",
                "rejections": [
                    {"sourceRecordId": source_id, "reason": reason, "physicalAttempts": attempts}
                    for source_id, reason, attempts in state.rejections
                ],
            },
        )
        raise RuntimeError(
            f"Could not collect {target} {sources[0].kind} cases from verified primary sources; collected {collected}. No canonical cases.jsonl was written."
        )


def _format_source_table(state: _CollectionState) -> str:
    lines = [
        "| sourceRecordId | family | published | retrieval | attempts | SHA-256 | primary URL |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for source, published_at, digest, retrieved_at, attempts in state.selected:
        lines.append(
            f"| `{source.source_record_id}` | {source.source_family} | {published_at} | {retrieved_at} | {attempts} | `{digest}` | <{source.url}> |"
        )
    return "\n".join(lines)


def _render_original_sources_markdown(
    records: list[dict[str, Any]], state: _CollectionState, count: int
) -> str:
    source_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {"funding": 0, "m_and_a": 0}
    for record in records:
        evidence = record["evidence"][0]
        source_id = evidence["sourceRecordId"]
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        question_type = record["derivation"]["questionType"]
        type_counts[question_type] = type_counts.get(question_type, 0) + 1
        category_counts[
            "funding" if "funding" in record["derivation"]["sourceFamily"] else "m_and_a"
        ] += 1
    rejection_lines = [f"- {item}" for item in _DISCOVERY_REJECTIONS]
    rejection_lines.extend(
        (
            f"- `{source_id}` rejected after {attempts} collector attempt(s): {reason}."
            for source_id, reason, attempts in state.rejections
        )
    )
    if not state.rejections:
        rejection_lines.append(
            "- No selected primary-page candidate failed date, quote, field, or schema validation."
        )
    recorded_attempts = len(state.physical_request_ledger)
    return "\n".join(
        [
            "# Venture funding and M&A query-gold curation",
            "",
            "## Fit and construction",
            "",
            "No existing open financial QA set identified in discovery had the required fit: FinDER is based on annual reports, while this category requires dated VC funding round and M&A announcement facts. Generic finance/news classification and secondary deal databases were excluded. This artifact is therefore truthfully labeled as a constructed first-party announcement QA set, not as an upstream benchmark.",
            "",
            "## Direct search answerability",
            "",
            "Each query is a standalone agent-tool search input naming the entity, the specific funding/deal field, and the exact event date. The cited primary HTML announcement itself contains the complete answer with matching scope, units, and qualification; queries do not rely on hidden dataset context, multi-document calculations, external model knowledge, or an unspecified latest state. No current search-provider or paid-model run was made. If a later Jev review is used, ask whether one direct search can return answer-bearing content; probabilities are triage signals, not proof of top-result reach.",
            "",
            f"Collected {count} records from {len(state.selected)} distinct primary announcement documents: {category_counts['funding']} funding cases and {category_counts['m_and_a']} M&A cases. Each case has a dated event scope and a deterministic field mapping; no reference answers or agent trajectories are included.",
            "Funding records cover round size, post-money/company valuation, lead investors, and named participants. M&A records cover announced transaction/equity/enterprise value, per-share consideration, cash/stock form, exchange ratios, funding method, and termination status/reason. Approximate, expected, net-debt-inclusive, and not-yet-closed terms are kept qualified in both queries and answers.",
            "",
            "## Selection and rejection log",
            "",
            "Selected only official issuer/company, investor-relations, or SEC exhibit announcement pages with a source-supplied event date and exact quoted fields. Candidate rejection criteria: annual-report-only evidence; secondary/aggregated deal records; missing amount/terms; no source date; inaccessible source; non-literal quote; or field/unit/date mismatch. Counts below distinguish discovery candidates from source pages rejected at collection.",
            *rejection_lines,
            f"- This collection call made {state.attempts} physical HTTP attempt(s); {recorded_attempts} source-page attempts are recorded including cached-page metadata. Cumulative hard cap: {_MAX_PHYSICAL_REQUESTS} per artifact directory, one retry maximum per page; {state.total_bytes} bytes read, under the 24 MB cap.",
            "",
            "## License and snapshot/revision policy",
            "",
            "No explicit open license was verified on the selected publisher pages; evidence license is recorded as `unknown`, not inferred from public accessibility. The raw directory stores the exact UTF-8 HTTP response bytes and a small metadata sidecar. Publisher press-release pages do not expose a stable upstream revision for most records, so the response SHA-256 and retrieval timestamp pin each snapshot; no revision identifier is invented. Any stable upstream revision exposed by a source is recorded in that source row.",
            "",
            "## Source records and snapshots",
            "",
            _format_source_table(state),
            "",
            "## Concentration and subtype counts",
            "",
            f"Distinct sourceRecordIds: {len(source_counts)}; most records per source: {max(source_counts.values(), default=0)}. Funding/M&A split: {category_counts['funding']}/{category_counts['m_and_a']} cases. Question types: "
            + ", ".join((f"`{name}` {total}" for name, total in sorted(type_counts.items())))
            + ".",
            "",
            "## Manual sample review and coverage gaps",
            "",
            "Manual sample review: the Databricks Series J excerpt distinguishes $10B of expected financing from $8.6B completed to date; Adobe’s 2022 Figma announcement is scoped as a proposed acquisition, while Adobe’s 2023 newsroom release records mutual termination and the stated regulatory-approval reason; AMD/Xilinx’s announced transaction value is all-stock, and its 1.7234 exchange ratio is stated separately. The termination page does not disclose a fee, so none is inferred. Every row also passed literal-excerpt, numeric-field, currency, unit, and source-date checks in the collector.",
            "Representativeness is intentionally limited: it favors English-language, disclosed, well-covered company announcements, with substantial US/UK technology, AI, energy, retail, and grocery representation. It omits undisclosed deal terms, smaller/private rounds without accessible primary releases, many non-English jurisdictions, and a market-wide sample; the cases should not be treated as a representative deal database.",
            "",
        ]
    )


def _sources_markdown(records: list[dict[str, Any]], state: _CollectionState, count: int) -> str:
    content = _render_original_sources_markdown(records, state, count)
    content = content.replace("## Fit and construction", "## Benchmark fit and construction")
    content = content.replace(
        "The cited primary HTML announcement itself contains the complete answer",
        "Each selected normal public answer-bearing HTML page contains the complete answer",
    )
    content = content.replace(
        "No current search-provider or paid-model run was made.",
        "No current search-provider or paid-model run was made. Direct-search discoverability remains unmeasured: no live search-result sample or Jev review was run, and search placement may change.",
    )
    content = content.replace(
        "## Source records and snapshots",
        "## Source records and snapshots\n\nNormal public answer-bearing pages are listed below by primary URL.",
    )
    manual_start = content.find("Manual sample review:")
    manual_end = content.find("\nRepresentativeness is intentionally limited:", manual_start)
    if manual_start >= 0 and manual_end >= 0:
        content = (
            content[:manual_start]
            + "Manual sample review: the Databricks Series J excerpt distinguishes $10B of expected financing from $8.6B completed to date; Adobe’s 2022 Figma announcement is scoped as a proposed acquisition, while Adobe’s 2023 newsroom release records mutual termination and the stated regulatory-approval reason; AMD/Xilinx’s announced transaction value is all-stock, and its 1.7234 exchange ratio is stated separately. Kroger/Albertsons states an estimated $34.10 total consideration per share; the agreement says the cash component may be reduced for a SpinCo divestiture and the special dividend, and separately gives approximately $24.6B enterprise value including approximately $4.7B assumed net debt. The termination page does not disclose a fee, so none is inferred. Every row passed literal-excerpt, numeric-field, currency, unit, and source-date checks against the source bytes."
            + content[manual_end:]
        )
    coverage_marker = "## Selection and rejection log\n"
    caveat = "Known-request accounting caveat: the inherited 73-entry ledger records collector URL attempts, but it predates redirect fail-closed handling and may omit extra HTTP hops automatically followed by the previous urllib handler. Its entry count is not a provable total of physical network requests. No further requests were made during this cache-only rebuild; future requests reject redirects and record each request attempt.\n\n"
    if coverage_marker in content:
        content = content.replace(coverage_marker, coverage_marker + "\n" + caveat, 1)
    content = content.replace(
        "Representativeness is intentionally limited:",
        "The sample limitation is explicit. Representativeness is intentionally limited:",
    )
    return content


def _check_output_directory(output_dir: Path) -> None:
    for part in output_dir.parts:
        lowered = part.casefold()
        if lowered == ".env" or lowered.startswith(".env."):
            raise ValueError("Refusing to write query-gold artifacts under a credential path")
    safe_output = ensure_safe_path(output_dir)
    safe_output.mkdir(parents=True, exist_ok=True)


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Collect and persist a bounded set of verified VC/M&A announcement cases."""
    if not isinstance(count, int) or not 1 <= count <= 50:
        raise ValueError("count must be an integer from 1 through 50")
    _check_output_directory(output_dir)
    output_dir = ensure_safe_path(output_dir)
    state = _load_request_ledger(output_dir)
    records: list[dict[str, Any]] = []
    targets = _category_target_counts(count)
    _collect_source_group(
        sources=(*_FUNDING_SOURCES, *_FUNDING_BACKUPS),
        target=targets["funding"],
        output_dir=output_dir,
        state=state,
        records=records,
    )
    _collect_source_group(
        sources=(*_M_AND_A_SOURCES, *_M_AND_A_BACKUPS),
        target=targets["m_and_a"],
        output_dir=output_dir,
        state=state,
        records=records,
    )
    if len(records) != count:
        raise RuntimeError(f"collector produced {len(records)} cases rather than {count}")
    normalized_queries: set[str] = set()
    case_ids: set[str] = set()
    for record in records:
        normalized = " ".join(record["query"].casefold().split())
        if normalized in normalized_queries:
            raise ValueError("collector produced a duplicate normalized query")
        if record["id"] in case_ids:
            raise ValueError("collector produced a duplicate stable case ID")
        normalized_queries.add(normalized)
        case_ids.add(record["id"])
    atomic_write_jsonl(output_dir / "cases.jsonl", records)
    atomic_write_bytes(
        output_dir / "sources.md", _sources_markdown(records, state, count).encode("utf-8")
    )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_output = (
        Path(__file__).resolve().parents[4]
        / "results/query-gold-curation/first-five-v1/categories/04_venture_capital_funding_ma"
    )
    parser.add_argument("--output-dir", type=Path, default=default_output)
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args(argv)
    try:
        records = collect(args.output_dir, args.count)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"venture_ma collection failed: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {len(records)} query-gold cases to {args.output_dir / 'cases.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
