# ruff: noqa: E501
"""Collect a small cloud pricing and service quota set from provider pages.

All numeric facts are fixed to literal entries or dated examples in official
provider pages. Collection captures those pages locally and rejects a source
whose answer-bearing table row or text no longer supports the selected fact.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from query_gold.io import (
    atomic_write_bytes,
    atomic_write_jsonl,
    ensure_safe_path,
    json_bytes,
    read_json,
    read_jsonl,
)
from query_gold.models import SCHEMA_VERSION, QueryGoldCase

CATEGORY_ID = "15_cloud_infrastructure_service_pricing"
GENERATOR_VERSION = "cloud-pricing-collector/1"
MAX_PHYSICAL_REQUESTS = 15
MAX_RETRIES = 1
MAX_REDIRECTS = 2
MAX_SOURCE_BYTES = 12_000_000
REQUEST_TIMEOUT_SECONDS = 18
MAX_COLLECTION_SECONDS = 120
USER_AGENT = "query-gold-cloud-pricing/1.0 (official public documentation)"


@dataclass(frozen=True, slots=True)
class CloudFact:
    case_id: str
    query: str
    answer: str
    value: int | float | str
    units: str
    source_id: str
    source_family: str
    source_title: str
    url: str
    temporal_version: str
    question_type: str
    must_contain: tuple[str, ...]
    row_key: str | None = None


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    family: str
    title: str
    url: str
    version: str
    raw_path: str


GCP_URL = "https://cloud.google.com/products/compute/pricing/general-purpose"
AZURE_URL = "https://azure.microsoft.com/pricing/reserved-vm-instances/"
AWS_SPOT_URL = "https://aws.amazon.com/ec2/spot/pricing/"
AWS_HISTORY_URL = (
    "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances-history.html"
)
AWS_FEED_URL = "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-data-feeds.html"
AWS_BEDROCK_URL = "https://docs.aws.amazon.com/general/latest/gr/bedrock.html"

SOURCES: dict[str, SourceSpec] = {
    "gcp-general-purpose-pricing": SourceSpec(
        "gcp-general-purpose-pricing",
        "official_cloud_compute_pricing_page",
        "General Purpose VM pricing | Google Cloud",
        GCP_URL,
        "Google Cloud General Purpose VM pricing page",
        "raw/google-cloud/general-purpose-pricing.html",
    ),
    "azure-reserved-vm-pricing": SourceSpec(
        "azure-reserved-vm-pricing",
        "official_reserved_compute_pricing_page",
        "Azure Reserved Virtual Machine Instances",
        AZURE_URL,
        "Azure Reserved VM pricing page; dated examples identify 2022-02-22 pricing",
        "raw/microsoft-azure/reserved-vm-pricing.html",
    ),
    "aws-ec2-spot-pricing": SourceSpec(
        "aws-ec2-spot-pricing",
        "official_spot_compute_pricing_page",
        "Amazon EC2 Spot Instances Pricing",
        AWS_SPOT_URL,
        "Amazon EC2 Spot pricing page",
        "raw/aws/ec2-spot-pricing.html",
    ),
    "aws-spot-price-history": SourceSpec(
        "aws-spot-price-history",
        "official_spot_price_history_documentation",
        "View Spot Instance pricing history",
        AWS_HISTORY_URL,
        "Amazon EC2 User Guide spot price history documentation",
        "raw/aws/spot-price-history.html",
    ),
    "aws-spot-cost-feed": SourceSpec(
        "aws-spot-cost-feed",
        "official_spot_cost_feed_documentation",
        "Track your Spot Instance costs using the Spot Instance data feed",
        AWS_FEED_URL,
        "Amazon EC2 User Guide Spot cost data feed documentation",
        "raw/aws/spot-cost-feed.html",
    ),
    "aws-bedrock-token-quotas": SourceSpec(
        "aws-bedrock-token-quotas",
        "official_model_api_quota_reference",
        "Amazon Bedrock endpoints and quotas | AWS General Reference",
        AWS_BEDROCK_URL,
        "Amazon Bedrock quota reference page",
        "raw/aws/bedrock-quotas.html",
    ),
}

_GCP_ROWS = (
    (
        "e2-standard-2",
        "2",
        "8 GiB",
        ("0.06701142", "0.048248226", "0.036186166", "0.042217196", "0.030155144"),
    ),
    (
        "e2-standard-4",
        "4",
        "16 GiB",
        ("0.13402284", "0.096496452", "0.072372332", "0.084434392", "0.060310288"),
    ),
    (
        "e2-standard-8",
        "8",
        "32 GiB",
        ("0.26804568", "0.192992904", "0.144744664", "0.168868784", "0.120620576"),
    ),
)
_GCP_TIERS = (
    "on-demand",
    "Compute Flexible CUD - 1 Year",
    "Compute Flexible CUD - 3 Year",
    "Compute Resource CUDs - 1 Year",
    "Compute Resource CUDs - 3 Year",
)

_facts: list[CloudFact] = []
for _instance, _vcpu, _ram, _prices in _GCP_ROWS:
    for _tier_index, _tier in enumerate(_GCP_TIERS):
        _price = _prices[_tier_index]
        _facts.append(
            CloudFact(
                case_id=f"cloud-gcp-{_instance}-{_tier.lower().replace(' ', '-')}",
                query=(
                    f"On the Google Cloud General Purpose VM pricing page, what hourly USD price "
                    f"is listed for {_instance} ({_vcpu} vCPUs and {_ram}) under {_tier}?"
                ),
                answer=f"${_price} per hour",
                value=float(_price),
                units="USD per hour",
                source_id="gcp-general-purpose-pricing",
                source_family=SOURCES["gcp-general-purpose-pricing"].family,
                source_title=SOURCES["gcp-general-purpose-pricing"].title,
                url=GCP_URL,
                temporal_version=SOURCES["gcp-general-purpose-pricing"].version,
                question_type="compute_hourly_price",
                must_contain=(_instance, _vcpu, _ram, *_prices),
                row_key=_instance,
            )
        )


def _fact(
    case_id: str,
    query: str,
    answer: str,
    value: int | float | str,
    units: str,
    source_id: str,
    question_type: str,
    must_contain: tuple[str, ...],
    *,
    row_key: str | None = None,
) -> CloudFact:
    source = SOURCES[source_id]
    return CloudFact(
        case_id,
        query,
        answer,
        value,
        units,
        source_id,
        source.family,
        source.title,
        source.url,
        source.version,
        question_type,
        must_contain,
        row_key,
    )


# Historical Azure examples are explicitly dated by Microsoft; these are not
# presented as current offers. Remaining entries are literal terms/FAQs.
_facts.extend(
    (
        _fact(
            "cloud-azure-m32ts-payg-2022",
            "In Microsoft's Azure Reserved VM pricing example dated 2022-02-22, what was the West US 2 monthly pay-as-you-go rate for one M32ts SUSE Linux Enterprise VM with 24x7 support?",
            "$1,976.11/month",
            "$1,976.11/month",
            "USD per month",
            "azure-reserved-vm-pricing",
            "historical_payg_vm_rate",
            ("M32ts", "$1,976.11/month", "February 22, 2022"),
        ),
        _fact(
            "cloud-azure-m32ts-reserved-2022",
            "In Microsoft's Azure Reserved VM pricing example dated 2022-02-22, what was the West US 2 monthly rate for the three-year reserved M32ts SUSE Linux Enterprise VM with 24x7 support?",
            "$552.85/month",
            "$552.85/month",
            "USD per month",
            "azure-reserved-vm-pricing",
            "historical_reserved_vm_rate",
            ("M32ts", "$552.85/month", "February 22, 2022"),
        ),
        _fact(
            "cloud-azure-d8sv4-payg-2022",
            "In Microsoft's Azure Reserved VM pricing example dated 2022-02-22, what was the monthly pay-as-you-go rate for one D8s v4 Windows Server VM in West US 2?",
            "$548.96/month",
            "$548.96/month",
            "USD per month",
            "azure-reserved-vm-pricing",
            "historical_payg_vm_rate",
            ("D8s v4", "$548.96/month", "February 22, 2022"),
        ),
        _fact(
            "cloud-azure-d8sv4-reserved-ahb-2022",
            "In Microsoft's Azure Reserved VM pricing example dated 2022-02-22, what was the monthly three-year reserved rate for one D8s v4 Windows Server VM with Azure Hybrid Benefit in West US 2?",
            "$105.39/month",
            "$105.39/month",
            "USD per month",
            "azure-reserved-vm-pricing",
            "historical_reserved_vm_rate",
            ("D8s v4", "$105.39/month", "February 22, 2022"),
        ),
        _fact(
            "cloud-azure-reserved-terms",
            "What reservation terms does Microsoft list for Azure Reserved Virtual Machine Instances?",
            "One year or three years",
            "one year or three years",
            "reservation term",
            "azure-reserved-vm-pricing",
            "reserved_instance_term",
            ("one-year or three-year terms",),
        ),
        _fact(
            "cloud-azure-monthly-payment",
            "According to Microsoft's Azure Reserved VM FAQ, is a monthly payment option available at additional cost?",
            "No; monthly payment is available at no extra cost",
            "no extra cost",
            "payment option",
            "azure-reserved-vm-pricing",
            "reserved_instance_payment_option",
            ("monthly payment option is available at no extra cost",),
        ),
        _fact(
            "cloud-azure-upfront-payment",
            "What upfront payment option does Microsoft list for Azure Reserved VM Instances?",
            "A single upfront payment",
            "single upfront payment",
            "payment option",
            "azure-reserved-vm-pricing",
            "reserved_instance_payment_option",
            ("single, upfront payment",),
        ),
        _fact(
            "cloud-azure-refund-termination",
            "Does Microsoft's Azure Reserved VM FAQ state that reservation refunds currently incur early termination fees?",
            "Microsoft states it is not currently charging early termination fees for reservation refunds",
            "no early termination fees",
            "reservation refund policy",
            "azure-reserved-vm-pricing",
            "reserved_instance_refund_policy",
            ("not currently charging early termination fees",),
        ),
        _fact(
            "cloud-azure-savings-72",
            "In the Azure Reserved VM pricing example footnote dated 2022-02-22, what savings versus pay-as-you-go did Microsoft report for the three-year M32ts example?",
            "up to 72 percent",
            72,
            "percent savings",
            "azure-reserved-vm-pricing",
            "historical_reserved_vm_savings",
            ("up to 72 percent", "February 22, 2022", "M32ts"),
        ),
        _fact(
            "cloud-azure-savings-ahb-80",
            "In the Azure Reserved VM pricing example footnote dated 2022-02-22, what combined savings did Microsoft state could be achieved with Azure Hybrid Benefit and a three-year reservation?",
            "up to 80 percent",
            80,
            "percent savings",
            "azure-reserved-vm-pricing",
            "historical_reserved_vm_savings",
            ("up to 80 percent", "February 22, 2022", "Azure Hybrid Benefit"),
        ),
    )
)

_facts.extend(
    (
        _fact(
            "cloud-aws-spot-discount-cap",
            "According to the Amazon EC2 Spot pricing page, what is the maximum advertised discount compared with On-Demand pricing?",
            "Up to 90%",
            90,
            "percent discount",
            "aws-ec2-spot-pricing",
            "spot_discount",
            ("up to 90% off compared to On-Demand pricing",),
        ),
        _fact(
            "cloud-aws-spot-price-update",
            "How often does the table on the Amazon EC2 Spot pricing page say Spot prices are updated?",
            "Every 5 minutes",
            5,
            "minutes",
            "aws-ec2-spot-pricing",
            "spot_price_update_interval",
            ("updated every 5 minutes",),
        ),
        _fact(
            "cloud-aws-spot-history-days",
            "For how many past days does the EC2 User Guide say Spot price history can be viewed?",
            "90 days",
            90,
            "days",
            "aws-spot-price-history",
            "spot_history_window",
            ("last 90 days",),
        ),
        _fact(
            "cloud-aws-spot-history-max-types",
            "When comparing Spot price history by instance type, how many instance types can be selected at most?",
            "five",
            5,
            "instance types",
            "aws-spot-price-history",
            "spot_history_filter_limit",
            ("up to five Instance type(s)",),
        ),
        _fact(
            "cloud-aws-spot-below-ondemand",
            "When an EC2 Spot request is fulfilled, what price ceiling does the EC2 User Guide specify relative to On-Demand pricing?",
            "The current Spot price does not exceed the On-Demand price",
            "On-Demand price",
            "price ceiling",
            "aws-spot-price-history",
            "spot_price_ceiling",
            ("current Spot price, not exceeding the On-Demand price",),
        ),
        _fact(
            "cloud-aws-spot-history-filters",
            "When comparing Spot price history by Availability Zones, which instance details and time selection does the EC2 User Guide say to choose?",
            "Instance type, operating system (Platform), and date range",
            "instance type; operating system; date range",
            "history filters",
            "aws-spot-price-history",
            "spot_history_filters",
            ("choose the Instance type, operating system (Platform), and Date range",),
        ),
        _fact(
            "cloud-aws-spot-rolling-supply",
            "What does AWS say determines EC2 Spot prices over time?",
            "Long-term trends in supply and demand for Spot capacity",
            "long-term supply and demand",
            "pricing basis",
            "aws-ec2-spot-pricing",
            "spot_price_basis",
            ("long-term trends in supply and demand for Spot Instance capacity",),
        ),
        _fact(
            "cloud-aws-spot-history-example-instance",
            "Which EC2 instance type appears in the User Guide's AWS CLI example for requesting Spot price history?",
            "c6i.xlarge",
            "c6i.xlarge",
            "instance type",
            "aws-spot-price-history",
            "spot_history_cli_example",
            ("c6i.xlarge", "2025-04-01"),
        ),
        _fact(
            "cloud-aws-spot-feed-cadence",
            "How often does AWS say EC2 Spot Instance data feed files typically arrive in the configured S3 bucket?",
            "once an hour",
            1,
            "hour",
            "aws-spot-cost-feed",
            "spot_cost_feed_cadence",
            ("typically once an hour",),
        ),
        _fact(
            "cloud-aws-spot-no-use-feed",
            "If no Spot Instance is running during an hour, does AWS say a data feed file is delivered for that hour?",
            "you don't receive a data feed file",
            "no",
            "data feed behavior",
            "aws-spot-cost-feed",
            "spot_cost_feed_behavior",
            ("you don't receive a data feed file for that hour",),
        ),
    )
)

# Values and product names below are from the official quota table. Older,
# established model families are used; no names are extrapolated from trends.
_BEDROCK_QUOTAS = (
    ("Anthropic Claude 3 Haiku", "ap-southeast-1", 200_000, "ap-southeast-1: 200,000"),
    (
        "Anthropic Claude 3 Sonnet",
        "each supported Region",
        200_000,
        "each supported Region: 200,000",
    ),
    ("Anthropic Claude 3.5 Haiku", "us-west-1", 300_000, "us-west-1: 300,000"),
    ("Anthropic Claude 3.5 Sonnet", "ap-southeast-1", 200_000, "ap-southeast-1: 200,000"),
    (
        "Anthropic Claude 3.5 Sonnet V2",
        "each supported Region",
        400_000,
        "each supported Region: 400,000",
    ),
    (
        "Anthropic Claude 3.7 Sonnet V1",
        "each supported Region",
        500_000,
        "each supported Region: 500,000",
    ),
    (
        "Amazon Titan Text Express",
        "each supported Region",
        300_000,
        "each supported Region: 300,000",
    ),
    (
        "Amazon Titan Text Premier",
        "each supported Region",
        300_000,
        "each supported Region: 300,000",
    ),
    ("Cohere Command R", "each supported Region", 300_000, "each supported Region: 300,000"),
    ("Cohere Command R Plus", "each supported Region", 300_000, "each supported Region: 300,000"),
    (
        "Meta Llama 3.1 405B Instruct",
        "each supported Region",
        400_000,
        "each supported Region: 400,000",
    ),
    (
        "Meta Llama 3.1 70B Instruct",
        "each supported Region",
        300_000,
        "each supported Region: 300,000",
    ),
    (
        "Meta Llama 3.1 8B Instruct",
        "each supported Region",
        300_000,
        "each supported Region: 300,000",
    ),
    (
        "Meta Llama 3.2 11B Instruct",
        "each supported Region",
        300_000,
        "each supported Region: 300,000",
    ),
    (
        "Meta Llama 3.3 70B Instruct",
        "each supported Region",
        300_000,
        "each supported Region: 300,000",
    ),
)
for _model, _region, _limit, _region_value in _BEDROCK_QUOTAS:
    _facts.append(
        _fact(
            f"cloud-bedrock-{_model.lower().replace(' ', '-').replace('.', '-')}-tpm",
            f"In the AWS General Reference Bedrock on-demand quota table, what token-per-minute limit is listed for {_model} in {_region}?",
            f"{_limit:,}",
            _limit,
            "tokens per minute",
            "aws-bedrock-token-quotas",
            "on_demand_model_token_quota",
            (f"On-demand model inference tokens per minute for {_model}", _region_value),
            row_key=_model,
        )
    )

FACTS: tuple[CloudFact, ...] = tuple(_facts)
if len(FACTS) != 50 or len({fact.case_id for fact in FACTS}) != 50:
    raise RuntimeError("cloud pricing category must contain exactly 50 unique cases")


class _VisibleHTML(html.parser.HTMLParser):
    """Extract visible text as table rows and ordinary paragraph-like text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.text: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._ignore = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript", "template"}:
            self._ignore += 1
        elif not self._ignore and tag == "tr":
            self._row = []
        elif not self._ignore and tag in {"td", "th"}:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"} and self._ignore:
            self._ignore -= 1
        elif not self._ignore and tag in {"td", "th"} and self._cell is not None:
            cell = " ".join(" ".join(self._cell).split())
            if cell and self._row is not None:
                self._row.append(cell)
            self._cell = None
        elif not self._ignore and tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if not self._ignore:
            cleaned = " ".join(data.split())
            if cleaned:
                self.text.append(cleaned)
                if self._cell is not None:
                    self._cell.append(cleaned)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_path(output_dir: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError("unsafe cloud source cache path")
    root = ensure_safe_path(output_dir)
    path = root
    for part in posix.parts:
        path = ensure_safe_path(path / part)
    return path


def _ledger(output_dir: Path) -> list[dict[str, Any]]:
    path = _safe_path(output_dir, "raw/network-attempts.jsonl")
    if not path.exists():
        return []
    rows = read_jsonl(path)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid cloud source request ledger")
    return rows


def _load_or_fetch(  # noqa: C901
    output_dir: Path, source: SourceSpec, state: dict[str, Any]
) -> tuple[bytes, str, str]:
    raw_path = _safe_path(output_dir, source.raw_path)
    meta_path = _safe_path(output_dir, f"{source.raw_path}.metadata.json")
    if raw_path.is_file() and meta_path.is_file():
        content = raw_path.read_bytes()
        metadata = read_json(meta_path)
        if (
            not isinstance(metadata, dict)
            or metadata.get("url") != source.url
            or metadata.get("rawSha256") != _sha256(content)
            or not isinstance(metadata.get("retrievedAtUTC"), str)
        ):
            raise ValueError(f"cached source metadata mismatch for {source.source_id}")
        return content, metadata["retrievedAtUTC"], _sha256(content)

    if state["client"] is None:
        state["client"] = httpx.Client(
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=8.0),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
    client: httpx.Client = state["client"]
    ledger = state["ledger"]
    origin = urlsplit(source.url)
    for attempt in range(MAX_RETRIES + 1):
        request_url = source.url
        for redirect_count in range(MAX_REDIRECTS + 1):
            if len(ledger) >= MAX_PHYSICAL_REQUESTS:
                raise RuntimeError("cloud source physical request limit reached")
            if time.monotonic() - state["started"] > MAX_COLLECTION_SECONDS:
                raise TimeoutError("cloud collection time limit reached")
            entry: dict[str, Any] = {
                "url": request_url,
                "attempt": attempt + 1,
                "startedAtUTC": _now(),
                "status": None,
                "responseBytes": None,
                "responseSha256": None,
                "errorType": None,
            }
            try:
                response = client.get(request_url)
                entry["status"] = response.status_code
                entry["responseBytes"] = len(response.content)
                entry["responseSha256"] = _sha256(response.content)
                if response.status_code in {301, 302, 303, 307, 308}:
                    target_url = urljoin(request_url, response.headers.get("location", ""))
                    target = urlsplit(target_url)
                    entry["redirectTo"] = target_url
                    ledger.append(entry)
                    atomic_write_jsonl(_safe_path(output_dir, "raw/network-attempts.jsonl"), ledger)
                    if target.scheme != "https" or target.hostname != origin.hostname:
                        raise ValueError("provider page redirected outside its HTTPS host")
                    if redirect_count >= MAX_REDIRECTS:
                        raise RuntimeError("provider page exceeded redirect limit")
                    request_url = target_url
                    continue
                ledger.append(entry)
                atomic_write_jsonl(_safe_path(output_dir, "raw/network-attempts.jsonl"), ledger)
                if response.status_code == 200:
                    if len(response.content) > MAX_SOURCE_BYTES:
                        raise ValueError("cloud source snapshot exceeded size limit")
                    response.content.decode("utf-8", errors="strict")
                    atomic_write_bytes(raw_path, response.content)
                    retrieved = _now()
                    atomic_write_bytes(
                        meta_path,
                        json_bytes(
                            {
                                "url": source.url,
                                "rawSha256": _sha256(response.content),
                                "retrievedAtUTC": retrieved,
                                "retrievedAtBasis": "response_received_at_utc",
                            }
                        ),
                    )
                    return response.content, retrieved, _sha256(response.content)
                if attempt < MAX_RETRIES:
                    break
                raise RuntimeError(f"provider page returned HTTP {response.status_code}")
            except httpx.RequestError as error:
                entry["errorType"] = type(error).__name__
                ledger.append(entry)
                atomic_write_jsonl(_safe_path(output_dir, "raw/network-attempts.jsonl"), ledger)
                if attempt < MAX_RETRIES:
                    break
                raise RuntimeError("provider source fetch failed after one retry") from None
        else:
            raise RuntimeError("provider page exceeded redirect limit")
    raise RuntimeError("provider source fetch failed")


def _norm(value: str) -> str:
    return " ".join(value.casefold().replace("\u00a0", " ").split())


def _extract_excerpt(fact: CloudFact, raw: bytes, parsed: _VisibleHTML) -> str:
    rows = [" | ".join(row) for row in parsed.rows]
    if fact.row_key is not None:
        candidates = [row for row in rows if _norm(fact.row_key) in _norm(row)]
        candidates = [
            row
            for row in candidates
            if all(_norm(token) in _norm(row) for token in fact.must_contain)
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"{fact.case_id}: source table does not contain one exact matching row"
            )
        excerpt = candidates[0]
        if fact.question_type == "compute_hourly_price":
            page_text = _norm(" ".join(parsed.text))
            tiers = [
                "on-demand",
                "Compute Flexible CUD - 1 Year",
                "Compute Flexible CUD - 3 Year",
                "Compute Resource CUDs - 1 Year",
                "Compute Resource CUDs - 3 Year",
            ]
            if not all(_norm(tier) in page_text for tier in tiers):
                raise ValueError(
                    f"{fact.case_id}: provider page lacks the selected pricing tier headers"
                )
            tier_index = next(
                (i for i, tier in enumerate(tiers) if f"under {tier}" in fact.query), None
            )
            prices = fact.must_contain[3:]
            positions = [_norm(excerpt).find(_norm(price)) for price in prices]
            if (
                tier_index is None
                or any(position < 0 for position in positions)
                or positions != sorted(positions)
            ):
                raise ValueError(
                    f"{fact.case_id}: source price columns are not in the documented tier order"
                )
            answer_price = fact.answer.removeprefix("$").removesuffix(" per hour").strip()
            if answer_price != prices[tier_index]:
                raise ValueError(
                    f"{fact.case_id}: answer price does not match its selected tier column"
                )
    else:
        visible = " ".join(parsed.text)
        normalized = _norm(visible)
        missing = [token for token in fact.must_contain if _norm(token) not in normalized]
        if missing:
            raise ValueError(f"{fact.case_id}: provider page does not contain required evidence")
        keys = [token for token in fact.must_contain if len(token) >= 8]
        anchor = keys[0] if keys else fact.must_contain[0]
        at = normalized.find(_norm(anchor))
        excerpt = visible[max(0, at - 250) : min(len(visible), at + len(anchor) + 550)]
        if not all(_norm(token) in _norm(excerpt) for token in fact.must_contain):
            # Pull a wider literal visible-text window around all required tokens.
            positions = [normalized.find(_norm(token)) for token in fact.must_contain]
            lo, hi = (
                min(positions),
                max(
                    p + len(_norm(token))
                    for p, token in zip(positions, fact.must_contain, strict=True)
                ),
            )
            excerpt = visible[max(0, lo - 250) : min(len(visible), hi + 250)]
        if not all(_norm(token) in _norm(excerpt) for token in fact.must_contain):
            raise ValueError(f"{fact.case_id}: exact answer-bearing excerpt could not be isolated")
    # The excerpt is visible text from the captured HTML; the full HTML bytes
    # and SHA-256 remain archived as the evidence object.
    if not raw:
        raise ValueError("empty cloud source snapshot")
    return excerpt[:8000]


def _case(
    fact: CloudFact, excerpt: str, retrieved: str, digest: str, source: SourceSpec
) -> dict[str, Any]:
    retrieved_day = retrieved[:10]
    snapshot_version = f"{source.title} snapshot retrieved {retrieved_day}"
    historical_azure = fact.source_id == "azure-reserved-vm-pricing" and any(
        "February 22, 2022" in token for token in fact.must_contain
    )
    evidence = {
        "url": fact.url,
        "title": snapshot_version,
        "retrievedAtUTC": retrieved,
        "effectiveDate": "2022-02-22" if historical_azure else None,
        # One record ID identifies this specific answer-bearing provider row or
        # statement; multiple facts may still point to the same public page.
        "sourceRecordId": fact.case_id,
        "upstreamRevision": digest,
        "license": "unknown",
        "rawSha256": digest,
        "rawPath": source.raw_path,
        "excerpt": excerpt,
    }
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "id": fact.case_id,
        "categoryId": CATEGORY_ID,
        "query": f'{fact.query[:-1]} (snapshot version: "{snapshot_version}")?',
        "temporal": {"kind": "version", "precision": "version", "version": snapshot_version},
        "gold": {
            "answer": fact.answer,
            "value": fact.value,
            "acceptedAnswers": [fact.answer],
            "units": fact.units,
            "currency": "USD" if fact.units.startswith("USD") else None,
        },
        "evidence": [evidence],
        "derivation": {
            "sourceFamily": fact.source_family,
            "generatorVersion": GENERATOR_VERSION,
            "questionType": fact.question_type,
        },
    }
    QueryGoldCase.model_validate(result, strict=True)
    return result


def _sources_note(
    cases: list[dict[str, Any]], output_dir: Path, ledger: list[dict[str, Any]]
) -> str:
    counts = Counter(case["evidence"][0]["sourceRecordId"] for case in cases)
    page_counts = Counter(case["evidence"][0]["url"] for case in cases)
    types = Counter(case["derivation"]["questionType"] for case in cases)
    lines = [
        "# Cloud infrastructure and service pricing query-gold curation",
        "",
        "## Benchmark fit",
        "",
        "The set covers literal cloud compute hourly prices, documented spot-price behavior, dated reservation examples, and model token quotas. Queries name a product or model and the exact price field or quota requested.",
        "",
        "## Candidate rejection and construction",
        "",
        "Facts were retained only when an official provider page states the requested value or term directly. Generated estimates, cross-provider conversions, account-specific live quotas, and derived prices were excluded. The dated Azure examples retain Microsoft's stated 2022-02-22 price basis.",
        "",
        "## License and source revision policy",
        "",
        "Provider pages are archived verbatim under raw/ with SHA-256 metadata and retrieval timestamps. Reuse license is recorded as unknown. A changed page is rejected when its answer-bearing row or required text no longer matches; update the curated fact only after reviewing the new official page.",
        "",
        "## Source concentration and question types",
        "",
        f"Distinct answer-bearing record IDs: {len(counts)}; maximum cases per record ID: {max(counts.values(), default=0)}.",
        f"Cases by public page: {', '.join(f'`{key}` {value}' for key, value in sorted(page_counts.items()))}.",
        f"Question type counts: {', '.join(f'`{key}` {value}' for key, value in sorted(types.items()))}.",
        f"Physical network attempts recorded: {len(ledger)}. Every cached page is validated by metadata and SHA-256 before use.",
        "",
        "## Manual sample review",
        "",
        "The curated values are pinned to answer-bearing rows or directly stated visible text. The collector checks those support tokens against the exact row or a captured-text excerpt and validates each output against the strict QueryGoldCase schema.",
        "",
        "## Representativeness and limitations",
        "",
        "Pricing varies by region, operating system, purchase option, and date. Google Cloud rates are the explicitly listed table values for the cited machine sizes and commitment columns. Azure numerical examples are historical examples, not current quotes. Spot price history is constrained to the documented filters/window. Bedrock quotas are general-reference defaults and may vary by account and Region; questions preserve the page's stated Region scope.",
        "",
        "## Normal public answer-bearing pages and discoverability",
        "",
        "Evidence links point to normal public vendor documentation and pricing pages rather than console-only endpoints. The Amazon spot prices themselves are dynamic; the set asks source-supported history behavior instead of inventing a static spot quote. The complete snapshots are cached in this category's raw directory.",
        "",
        "## Sources",
        "",
        "| Source record | Cases | Public answer page |",
        "|---|---:|---|",
    ]
    by_url = {source.url: source for source in SOURCES.values()}
    for url, amount in sorted(page_counts.items()):
        source = by_url[url]
        lines.append(f"| `{source.source_id}` | {amount} | <{source.url}> |")
    lines.append("")
    return "\n".join(lines)


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Fetch/capture bounded official sources and return canonical case rows."""
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_safe_path(output_dir, require_existing=True)
    ledger = _ledger(output_dir)
    state: dict[str, Any] = {"client": None, "ledger": ledger, "started": time.monotonic()}
    fetched: dict[str, tuple[bytes, str, str, _VisibleHTML]] = {}
    cases: list[dict[str, Any]] = []
    try:
        for fact in FACTS[:count]:
            if fact.source_id not in fetched:
                source = SOURCES[fact.source_id]
                raw, retrieved, digest = _load_or_fetch(output_dir, source, state)
                parser = _VisibleHTML()
                parser.feed(raw.decode("utf-8", errors="strict"))
                parser.close()
                fetched[fact.source_id] = (raw, retrieved, digest, parser)
            raw, retrieved, digest, parser = fetched[fact.source_id]
            source = SOURCES[fact.source_id]
            excerpt = _extract_excerpt(fact, raw, parser)
            cases.append(_case(fact, excerpt, retrieved, digest, source))
            if time.monotonic() - state["started"] > MAX_COLLECTION_SECONDS:
                raise TimeoutError("cloud collection time limit reached")
    finally:
        client = state["client"]
        if client is not None:
            client.close()
    atomic_write_jsonl(output_dir / "cases.jsonl", cases)
    atomic_write_bytes(
        output_dir / "sources.md", _sources_note(cases, output_dir, ledger).encode("utf-8")
    )
    return cases


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    rows = collect(args.output_dir, args.count)
    print(f"Collected {len(rows)} cloud pricing and quota cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
