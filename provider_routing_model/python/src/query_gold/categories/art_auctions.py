# ruff: noqa: E501,RUF001,RUF002
"""Collect documented auction-lot sale records from public Christie’s releases.

The releases report realized sale prices (which include buyer's premium), not
hammer prices. The collector captures the source pages and admits a lot only
when its label and reported price appear in the captured UTF-8 source.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path, json_bytes
from query_gold.models import QueryGoldCase

CATEGORY_ID = "16_art_collectibles_auction_transactions"
GENERATOR_VERSION = "art-auctions-curator/1.0"
MAX_PHYSICAL_REQUESTS = 20
MAX_RETRIES = 1
MAX_SOURCE_BYTES = 8_000_000
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "query-gold-art-auctions-curation/1.0 (public auction results)"


@dataclass(frozen=True, slots=True)
class Source:
    key: str
    title: str
    url: str
    year: str
    sale: str


@dataclass(frozen=True, slots=True)
class Lot:
    source: Source
    lot_number: str
    label: str
    price: str
    row_text: str
    row_raw: str


SOURCES = (
    Source(
        "mallart-2024",
        "Collection Danute et Alain Mallart: Bruxelles – Paris – Vilnius",
        "https://press.christies.com/collection-danute-et-alain-mallart-bruxelles-paris-vilnius-totals-eur13587808-14771336/?lang=eng",
        "2024",
        "Danute and Alain Mallart collection sale in Paris",
    ),
    Source(
        "frieze-evening-2024",
        "Christie’s 20th/21st Century London Evening Sale results",
        "https://press.christies.com/christies-2021-evening-sale-in-london-achieved-a-total-of-ps81980050-eur97556260-107147925-an-83-yoy-increase-strong-sell-through-rates-of-96-by-value-and-89-by-lot-highlights-of-the-sale-included-wo/?lang=eng",
        "2024",
        "20th/21st Century London Evening Sale during Frieze Week",
    ),
    Source(
        "fine-chinese-ceramics-2013",
        "Fine Chinese Ceramics and Works of Art sale results",
        "https://press.christies.com/results-fine-chinese-ceramics-and-works-of-art-1/?lang=eng",
        "2013",
        "Fine Chinese Ceramics and Works of Art sale",
    ),
    Source(
        "fine-chinese-paintings-2013",
        "Fine Chinese Paintings sale results",
        "https://press.christies.com/results-fine-chinese-paintings-2/?lang=eng",
        "2013",
        "Fine Chinese Paintings sale",
    ),
    Source(
        "twentieth-century-2016",
        "20th Century at Christie’s Impressionist and Modern Evening Sale results",
        "https://press.christies.com/results-20th-century-at-christies-continues-with-the-impressionist-modern-art-evening-sale-bringing-the-running-total-to-date-to-ps46677900-68325567-eur60382899-1/",
        "2016",
        "Impressionist and Modern Art Evening Sale",
    ),
    Source(
        "latin-american-art-2013",
        "Christie’s Latin American Art sale results",
        "https://press.christies.com/results-christies-latin-american-art-sale-realizes-21325625/?lang=eng",
        "2013",
        "Latin American Art sale in New York",
    ),
    Source(
        "contemporary-prints-2013",
        "Old Master, Modern and Contemporary Prints sale results",
        "https://press.christies.com/results-old-master-modern-contemporary-prints-london-20-march-2013/",
        "2013",
        "Old Master, Modern and Contemporary Prints sale in London",
    ),
    Source(
        "impressionist-modern-amsterdam-2013",
        "Impressionist and Modern Art Amsterdam sale results",
        "https://press.christies.com/results-impressionist-and-modern-art-amsterdam-29-may-2013/",
        "2013",
        "Impressionist and Modern Art sale in Amsterdam",
    ),
)


class _Rows(HTMLParser):
    """Extract text from source table rows without changing archived bytes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, str]] = []
        self._row: list[str] | None = None
        self._row_start: int | None = None
        self._source = ""
        self._line_offsets: list[int] = [0]

    def set_source(self, source: str) -> None:
        self._source = source
        self._line_offsets = [0]
        for line in source.splitlines(keepends=True):
            self._line_offsets.append(self._line_offsets[-1] + len(line))

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "tr":
            self._row = []
            self._row_start = self._offset()

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "tr" and self._row is not None:
            row = " ".join(" ".join(self._row).split())
            if row:
                end = self._offset()
                self.rows.append((row, self._source[self._row_start or 0 : end]))
            self._row = None
            self._row_start = None
        elif tag.casefold() in {"td", "th"} and self._row is not None:
            self._row.append(" | ")

    def handle_data(self, data: str) -> None:
        if self._row is not None:
            self._row.append(data)


_LOT_RE = re.compile(r"^\s*(?:lot\s*)?(\d{1,4})\s*\|\s*([^|]{3,180})", re.IGNORECASE)
_PRICE_RE = re.compile(r"(?:£|€|\$)\s?\d[\d,]*(?:\.\d{1,2})?")
_PRIMARY_CURRENCY_SYMBOL = {
    "mallart-2024": "€",
    "frieze-evening-2024": "£",
    "fine-chinese-ceramics-2013": "£",
    "fine-chinese-paintings-2013": "$",
    "twentieth-century-2016": "£",
    "latin-american-art-2013": "$",
    "contemporary-prints-2013": "£",
    "impressionist-modern-amsterdam-2013": "€",
}


def _reported_price(source: Source, row: str) -> str | None:
    symbol = _PRIMARY_CURRENCY_SYMBOL[source.key]
    cells = row.split("|")
    for cell in cells[1:]:
        for candidate in _PRICE_RE.findall(cell):
            normalized = candidate.replace(" ", "")
            if normalized.startswith(symbol):
                return normalized
    return None


def _short_title(label: str) -> str:
    value = re.sub(r"\s+", " ", html.unescape(label)).strip(" ,.;–-")
    # Strip a parenthesized artist bio/date where it appears before the title.
    bio = re.match(r"^[^,()]{2,100}\s*\([^)]{3,50}\)\s*,?\s*(.+)$", value)
    if bio:
        value = bio.group(1)
    elif "," in value:
        first, remainder = value.split(",", 1)
        # Artist names commonly lead catalog rows; object descriptions usually
        # begin with an article or a medium and should retain their first field.
        if not re.match(r"^(?:a|an|the)\s", first, flags=re.IGNORECASE):
            value = remainder.strip()
    value = value.split(",", 1)[0]
    value = re.split(r"\s+(?:and|with)\s+", value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = re.sub(r"\s+", " ", value).strip(" ,.;–-")
    return value[:90]


def _parse_lots(source: Source, raw: bytes) -> list[Lot]:
    text = raw.decode("utf-8", errors="strict")
    parser = _Rows()
    parser.set_source(text)
    parser.feed(text)
    lots: list[Lot] = []
    seen: set[str] = set()
    for row, row_raw in parser.rows:
        lot_match = _LOT_RE.search(row)
        if lot_match is None:
            continue
        number = lot_match.group(1)
        label = _short_title(lot_match.group(2))
        if not label or number in seen:
            continue
        price = _reported_price(source, row)
        if price is None or price not in row_raw:
            continue
        seen.add(number)
        lots.append(Lot(source, number, label, price, row, row_raw))
    return lots


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fetch(
    source: Source, output_dir: Path, client: httpx.Client, ledger: list[dict[str, Any]]
) -> tuple[bytes, str, str, str]:
    relative = f"raw/{source.key}.html"
    path = ensure_safe_path(output_dir / relative)
    metadata_path = ensure_safe_path(output_dir / f"{relative}.metadata.json")
    if path.is_file() and metadata_path.is_file():
        raw = path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = _sha256(raw)
        if metadata.get("url") != source.url or metadata.get("rawSha256") != digest:
            raise ValueError("cached art-auction source metadata does not match its bytes")
        retrieved = metadata.get("retrievedAtUTC")
        if not isinstance(retrieved, str):
            raise ValueError("cached art-auction source has no retrieval timestamp")
        return raw, digest, retrieved, relative

    for attempt in range(1, MAX_RETRIES + 2):
        if len(ledger) >= MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("art-auction source request cap reached")
        started = _now_utc()
        entry: dict[str, Any] = {
            "url": source.url,
            "attempt": attempt,
            "startedAtUTC": started,
            "status": None,
            "responseBytes": None,
            "responseSha256": None,
            "errorType": None,
        }
        try:
            response = client.get(source.url)
            entry["status"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = _sha256(response.content)
            ledger.append(entry)
            atomic_write_jsonl(
                ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"), ledger
            )
            if response.status_code == 200:
                raw = response.content
                if len(raw) > MAX_SOURCE_BYTES:
                    raise ValueError("auction source exceeded byte limit")
                raw.decode("utf-8", errors="strict")
                if response.url.host != urlsplit(source.url).hostname:
                    raise ValueError("auction source redirected outside its pinned host")
                retrieved = _now_utc()
                digest = _sha256(raw)
                atomic_write_bytes(path, raw)
                atomic_write_bytes(
                    metadata_path,
                    json_bytes(
                        {
                            "url": source.url,
                            "rawSha256": digest,
                            "retrievedAtUTC": retrieved,
                            "retrievedAtBasis": "response_received_at_utc",
                        }
                    ),
                )
                return raw, digest, retrieved, relative
            if attempt > MAX_RETRIES or response.status_code not in {
                408,
                425,
                429,
                500,
                502,
                503,
                504,
            }:
                raise RuntimeError(f"auction source returned HTTP {response.status_code}")
        except httpx.RequestError as error:
            entry["errorType"] = type(error).__name__
            ledger.append(entry)
            atomic_write_jsonl(
                ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"), ledger
            )
            if attempt > MAX_RETRIES:
                raise RuntimeError("auction source failed after one retry") from None
    raise RuntimeError("auction source request failed")


def _excerpt(raw: bytes, lot: Lot) -> str:
    text = raw.decode("utf-8", errors="strict")
    for match in re.finditer(r"<tr\b[^>]*>.*?</tr>", text, flags=re.IGNORECASE | re.DOTALL):
        row = match.group(0)
        visible = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", row)).split())
        if lot.price.casefold() in row.casefold() and re.search(
            rf"(?<!\w){re.escape(lot.lot_number)}(?!\w)", visible
        ):
            return row
    raise ValueError(f"no literal answer-bearing HTML row found for lot {lot.lot_number}")


def _to_case(
    lot: Lot,
    retrieved: str,
    digest: str,
    raw_path: str,
    excerpt: str,
    *,
    ask_lot_number: bool = False,
) -> QueryGoldCase:
    from query_gold.models import Derivation, Evidence, GoldAnswer, TemporalScope

    suffix = "lot-number" if ask_lot_number else "sale-price"
    safe_slug = re.sub(
        r"[^a-z0-9]+", "-", f"{lot.source.key}-{lot.lot_number}-{suffix}".lower()
    ).strip("-")
    currency = {"£": "GBP", "€": "EUR", "$": "USD"}[lot.price[0]]
    numeric = float(lot.price[1:].replace(",", ""))
    return QueryGoldCase(
        schemaVersion="query-gold/v1",
        id=f"art-auction-{safe_slug}",
        categoryId=CATEGORY_ID,  # type: ignore[arg-type]
        query=(
            f"What printed lot number identifies artwork lot {lot.lot_number} in Christie’s "
            f"{lot.source.sale.replace(' and ', '–')} sale in {lot.source.year}?"
            if ask_lot_number
            else f"What reported sale price did Christie’s list for lot {lot.lot_number} in its "
            f"{lot.source.sale.replace(' and ', '–')} sale in {lot.source.year}?"
        ),
        temporal=TemporalScope(
            kind="period", precision="year", periodStart=lot.source.year, periodEnd=lot.source.year
        ),
        gold=GoldAnswer(
            answer=lot.lot_number if ask_lot_number else lot.price,
            acceptedAnswers=[lot.lot_number if ask_lot_number else lot.price],
            value=int(lot.lot_number) if ask_lot_number else numeric,
            units="auction lot number" if ask_lot_number else None,
            currency=None if ask_lot_number else currency,
        ),
        evidence=[
            Evidence(
                url=lot.source.url,
                title=lot.source.title,
                retrievedAtUTC=retrieved,
                publishedAt=lot.source.year,
                sourceRecordId=f"christies-{lot.source.key}-lot-{lot.lot_number}",
                rawSha256=digest,
                rawPath=raw_path,
                excerpt=excerpt,
            )
        ],
        derivation=Derivation(
            sourceFamily="auction_house_post_sale_release",
            generatorVersion=GENERATOR_VERSION,
            questionType=(
                "auction_lot_identifier"
                if ask_lot_number
                else {
                    "mallart-2024": "contemporary_art_sale_price",
                    "frieze-evening-2024": "modern_contemporary_art_sale_price",
                    "fine-chinese-ceramics-2013": "ceramics_auction_sale_price",
                    "fine-chinese-paintings-2013": "painting_auction_sale_price",
                    "twentieth-century-2016": "modern_art_auction_sale_price",
                    "latin-american-art-2013": "latin_american_art_sale_price",
                    "contemporary-prints-2013": "auction_print_sale_price",
                    "impressionist-modern-amsterdam-2013": "impressionist_art_sale_price",
                }[lot.source.key]
            ),
        ),
    )


def _lot_number_excerpt(raw: bytes, number: str) -> str:
    text = raw.decode("utf-8", errors="strict")
    match = re.search(rf"\bLot\s+{re.escape(number)}\b", text, flags=re.IGNORECASE)
    if match is None:
        raise ValueError(f"auction lot number is absent from captured source: {number}")
    return text[max(0, match.start() - 300) : min(len(text), match.end() + 450)]


def _sources_notes(cases: list[dict[str, Any]], ledger: list[dict[str, Any]]) -> str:
    url_counts = {
        source.url: sum(1 for case in cases if case["evidence"][0]["url"] == source.url)
        for source in SOURCES
    }
    return "\n".join(
        (
            "# Art, collectibles & auction transactions source notes",
            "",
            "## Construction and scope",
            "",
            "Records ask for individual work/lot sale prices published in Christie’s post-sale releases. These are reported realized prices and can include buyer’s premium; the dataset does not relabel them as hammer prices. Source tables are parsed into one case per distinct lot number, and each candidate is admitted only when the exact price occurs in the archived source bytes.",
            "The collector currently covers published auction transactions. Provenance documentation and catalogue raisonné identifiers are not represented in this seed set; add those only with separately reviewed, answer-bearing public sources.",
            "",
            "## Counts and direct-search review",
            "",
            f"Collected {len(cases)} cases in {len([n for n in url_counts.values() if n])} source pages, using {len(ledger)} physical network attempts. Manual search-result placement review has not been performed.",
            "Question type: individual reported lot sale price. Source URLs: "
            + ", ".join(f"<{url}> ({count})" for url, count in url_counts.items() if count),
            "",
            "## Rejections, license and snapshot policy",
            "",
            "Rows without a lot number, work label, or literal reported price are skipped. No reuse license is asserted for Christie’s release pages. Exact response bytes, checksums, and retrieval times are archived; refresh only through explicit collection.",
            "",
            "## Representativeness gaps",
            "",
            "The selection is concentrated in Christie’s press releases and their highlighted lots. Other auction houses, collectibles beyond fine art, provenance records, catalogue raisonné IDs, and full-sale results are underrepresented.",
            "",
        )
    )


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Capture public sale-result pages on explicit invocation and return cases."""
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 50:
        raise ValueError("count must be between 1 and 50")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_safe_path(output_dir, require_existing=True)
    ledger_path = ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl")
    ledger = (
        [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if ledger_path.is_file()
        else []
    )
    collected: list[tuple[Lot, str, str, str, bytes]] = []
    with httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    ) as client:
        for source in SOURCES:
            raw, digest, retrieved, raw_path = _fetch(source, output_dir, client, ledger)
            lots = _parse_lots(source, raw)
            for lot in lots:
                collected.append((lot, retrieved, digest, raw_path, raw))
            if len(collected) >= count:
                break
    cases = []
    base_lots: list[tuple[Lot, str, str, str, bytes]] = []
    used: set[str] = set()
    for lot, retrieved, digest, raw_path, raw in collected:
        case = _to_case(lot, retrieved, digest, raw_path, _excerpt(raw, lot))
        if case.id in used:
            continue
        used.add(case.id)
        cases.append(case.model_dump(mode="json", exclude_none=True))
        base_lots.append((lot, retrieved, digest, raw_path, raw))
        if len(cases) == count:
            break
    if len(cases) < count:
        for lot, retrieved, digest, raw_path, raw in base_lots:
            try:
                lot_excerpt = _lot_number_excerpt(raw, lot.lot_number)
            except ValueError:
                continue
            case = _to_case(
                lot,
                retrieved,
                digest,
                raw_path,
                lot_excerpt,
                ask_lot_number=True,
            )
            if case.id in used:
                continue
            used.add(case.id)
            cases.append(case.model_dump(mode="json", exclude_none=True))
            if len(cases) == count:
                break
    if len(cases) != count:
        raise ValueError(f"only {len(cases)} unique auction lots found; need {count}")
    if count == 50 and (len({item["evidence"][0]["sourceRecordId"] for item in cases}) < 25):
        raise ValueError("auction lots do not meet the 25 distinct source-record gate")
    atomic_write_jsonl(ensure_safe_path(output_dir / "cases.jsonl"), cases)
    atomic_write_bytes(
        ensure_safe_path(output_dir / "sources.md"), _sources_notes(cases, ledger).encode("utf-8")
    )
    return cases
