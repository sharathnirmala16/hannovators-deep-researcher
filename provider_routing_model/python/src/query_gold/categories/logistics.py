# ruff: noqa: E501,RUF001
"""Public port throughput, ship capacity, IMO registry, and incident facts.

Deterministic seeds are source-scoped questions. The explicit collector
captures pinned public pages and literal answer excerpts before producing
canonical QueryGoldCase records.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path, json_bytes
from query_gold.models import QueryGoldCase

CATEGORY_ID = "13_logistics_freight_supply_chain"
GENERATOR_VERSION = "logistics-curator/1.0"

LA_URL = "https://portoflosangeles.org/business/statistics/container-statistics"
ROTTERDAM_URL = "https://www.portofrotterdam.com/en/news-and-press-releases/cargo-throughput-port-rotterdam-slightly-decreased-2024"
IMO_URL = "https://www.imo.org/en/ourwork/msas/pages/imo-identification-number-scheme.aspx"
MAX_PHYSICAL_REQUESTS = 150
MAX_RETRIES = 1
MAX_SOURCE_BYTES = 5_000_000
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "query-gold-logistics-curation/1.0 (official public sources)"


@dataclass(frozen=True, slots=True)
class LogisticsFact:
    id: str
    prompt: str
    answer: str
    url: str
    title: str
    excerpt: str
    period: str
    source_record_id: str


# The Port of Los Angeles calendar-year table reports total container counts
# in TEUs. Values are transcribed exactly from the official historical table.
_LA_ANNUAL: tuple[tuple[int, str], ...] = (
    (2004, "7,321,440"),
    (2005, "7,484,624"),
    (2006, "8,469,853"),
    (2007, "8,355,039"),
    (2008, "7,849,985"),
    (2009, "6,748,995"),
    (2010, "7,831,902"),
    (2011, "7,940,511"),
    (2012, "8,077,714"),
    (2013, "7,868,582"),
    (2014, "8,340,066"),
    (2015, "8,160,458"),
    (2016, "8,856,783"),
    (2017, "9,343,193"),
    (2018, "9,458,748"),
    (2019, "9,337,632"),
    (2020, "9,213,396"),
)


def _make_facts() -> tuple[LogisticsFact, ...]:
    facts = [
        LogisticsFact(
            id=f"log-la-calendar-{year}-total-teu",
            prompt=(
                f"According to the Port of Los Angeles annual container statistics, "
                f"how many total TEUs did the port handle in calendar year {year}?"
            ),
            answer=value,
            url=LA_URL,
            title="Port of Los Angeles Container Statistics",
            excerpt=f"{year}  |  {value}",
            period=str(year),
            source_record_id=f"port-los-angeles-calendar-{year}",
        )
        for year, value in _LA_ANNUAL
    ]
    rotterdam = (
        (
            "total-throughput-tonnes",
            "435.8 million tonnes",
            "In 2024, total throughput amounted to 435.8 million tonnes, compared to 438.8 million tonnes in the same period last year.",
        ),
        (
            "prior-year-total-throughput-tonnes",
            "438.8 million tonnes",
            "In 2024, total throughput amounted to 435.8 million tonnes, compared to 438.8 million tonnes in the same period last year.",
        ),
        (
            "container-throughput-teu",
            "13.8 million TEU",
            "Container throughput in 2024 increased by 2.8% in TEU to 13.8 million TEU.",
        ),
        (
            "container-throughput-tonnes",
            "133.4 million tonnes",
            "Container throughput in 2024 increased by 2.5% in tonnes to 133.4 million tonnes.",
        ),
        (
            "liquid-bulk-throughput-tonnes",
            "200 million tonnes",
            "The liquid bulk segment declined by 2.7% to 200 million tonnes.",
        ),
    )
    for key, answer, excerpt in rotterdam:
        facts.append(
            LogisticsFact(
                id=f"log-rotterdam-2024-{key}",
                prompt=(
                    "According to the Port of Rotterdam Authority's 2024 throughput "
                    f"release, what was Rotterdam's {key.replace('-', ' ')}?"
                ),
                answer=answer,
                url=ROTTERDAM_URL,
                title="Cargo throughput in the port of Rotterdam slightly decreased in 2024",
                excerpt=excerpt,
                period="2024",
                source_record_id=f"port-rotterdam-2024-{key}",
            )
        )
    imo_facts = (
        (
            "scheme-introduction-year",
            "1987",
            "The IMO ship identification number scheme was introduced in 1987 through adoption of resolution A.600(15).",
        ),
        (
            "scheme-mandatory-date",
            "1 January 1996",
            "The implementation of the scheme became mandatory as of 1 January 1996.",
        ),
        (
            "number-length",
            "seven digit number",
            "This is a unique seven digit number that is assigned to propelled, sea-going merchant ships of 100 GT and above.",
        ),
        (
            "number-prefix",
            "IMO",
            'The IMO ship identification number is made of the three letters "IMO" followed by the seven-digit number.',
        ),
        (
            "number-reassignment",
            "never reassigned to another ship",
            "The IMO number is never reassigned to another ship and is shown on the ship’s certificates.",
        ),
    )
    for key, answer, excerpt in imo_facts:
        facts.append(
            LogisticsFact(
                id=f"log-imo-{key}",
                prompt=(
                    "According to the IMO Ship Identification Number Scheme page, "
                    f"{key.replace('-', ' ')}: what is the stated value or rule?"
                ),
                answer=answer,
                url=IMO_URL,
                title="IMO identification number schemes",
                excerpt=excerpt,
                period="immutable",
                source_record_id=f"imo-ship-identification-{key}",
            )
        )
    incident_facts = (
        (
            "dali-2024-length",
            "984-foot-long",
            "Dali",
            "March 26, 2024",
            "https://www.ntsb.gov/investigations/Pages/DCA24MM031.aspx",
            "Contact of Containership Dali with Francis Scott Key Bridge and Subsequent Bridge Collapse",
            "On March 26, 2024, about 0129 local time, the 984-foot-long Singapore-flagged cargo vessel (containership) Dali was transiting out of Baltimore Harbor.",
        ),
        (
            "president-eisenhower-2021-crew",
            "22 crewmembers",
            "President Eisenhower",
            "April 28, 2021",
            "https://www.ntsb.gov/investigations/pages/DCA21FM026.aspx",
            "Engine Room Fire aboard Containership President Eisenhower",
            "No pollution or injuries among the 22 crewmembers were reported.",
        ),
        (
            "maunalei-2022-damage",
            "$3.03 million",
            "Maunalei",
            "August 11, 2022",
            "https://www.ntsb.gov/investigations/Pages/dca22fm039.aspx",
            "Loss of Propulsion aboard Containership Maunalei",
            "Damage to the vessel was estimated at $3.03 million.",
        ),
        (
            "kevin-michael-2021-tow",
            "15-barge tow",
            "Kevin Michael",
            "March 19, 2021",
            "https://www.ntsb.gov/investigations/pages/DCA21FM021.aspx",
            "Contact of Kevin Michael Tow with Melvin Price Locks and Dam Guide Wall",
            "The towing vessel Kevin Michael was transiting down river on the Mississippi River with a crew of nine pushing a 15-barge tow.",
        ),
        (
            "miss-dorothy-2021-barges",
            "14 barges",
            "Miss Dorothy",
            "March 17, 2021",
            "https://www.ntsb.gov/investigations/pages/DCA21FM018.aspx",
            "Engine Room Fire aboard Towing Vessel Miss Dorothy",
            "The towing vessel Miss Dorothy was pushing 14 barges upbound on the Lower Mississippi River.",
        ),
        (
            "summer-wind-2014-spill",
            "168,000 gallons",
            "Summer Wind",
            "March 22, 2014",
            "https://www.ntsb.gov/investigations/pages/DCA14FM008.aspx",
            "Collision between Bulk Carrier Summer Wind and the Miss Susan Tow",
            "The collision breached the hull of the forward tank barge in the Miss Susan tow, and about 168,000 gallons of fuel oil spilled into the waterway.",
        ),
        (
            "bunun-queen-2022-location",
            "66 miles south of Port Fourchon",
            "Bunun Queen",
            "July 23, 2022",
            "https://www.ntsb.gov/investigations/pages/DCA22FM030.aspx",
            "Collision between Bulk Carrier Bunun Queen and Offshore Supply Vessel Thunder",
            "The vessels collided about 66 miles south of Port Fourchon, Louisiana.",
        ),
        (
            "yangze-7-2024-damage",
            "$3.7 million",
            "Yangze 7",
            "July 19, 2024",
            "https://www.ntsb.gov/investigations/pages/dca24fm051.aspx",
            "Collision of Bulk Carrier Yangze 7 and Towing Vessel Miss Peggy",
            "Total damages, including salvage of the Miss Peggy and pollution mitigation, were estimated at $3.7 million.",
        ),
        (
            "natalie-jean-2018-fatalities",
            "Two",
            "Natalie Jean",
            "March 12, 2018",
            "https://www.ntsb.gov/investigations/pages/dca18fm017.aspx",
            "Capsizing and Sinking of Towing Vessel Natalie Jean",
            "Two of the three crewmembers on board the towboat died in the accident.",
        ),
        (
            "jw-herron-2017-damage",
            "$1.5 million",
            "J.W. Herron",
            "December 13, 2017",
            "https://www.ntsb.gov/investigations/pages/DCA18FM008.aspx",
            "Engine Room Fire aboard Towing Vessel J.W. Herron",
            "No pollution or injuries were reported. The estimated damage to the vessel was $1.5 million.",
        ),
        (
            "cosco-busan-2007-spill",
            "53,500 gallons of fuel oil",
            "Cosco Busan",
            "November 7, 2007",
            "https://www.ntsb.gov/investigations/Pages/DCA08MM004.aspx",
            "Allision of Hong Kong-Registered Containership M/V Cosco Busan With the Delta Tower of the San Francisco-Oakland Bay Bridge",
            "As a result of the breached fuel tanks, about 53,500 gallons of fuel oil were released into San Francisco Bay.",
        ),
        (
            "gunde-maersk-2015-damage",
            "$380,000",
            "Gunde Maersk",
            "December 8, 2015",
            "https://www.ntsb.gov/investigations/pages/DCA16FM009.aspx",
            "Fire Aboard Containership Gunde Maersk",
            "Damage was estimated at $380,000.",
        ),
        (
            "alaganik-2019-fuel",
            "1,896 gallons",
            "Alaganik",
            "July 7, 2019",
            "https://www.ntsb.gov/investigations/pages/DCA19FM042.aspx",
            "Explosion and Subsequent Sinking of Barge Alaganik",
            "About 1,896 gallons of gasoline and diesel fuel stored on board the vessel were consumed by the fire or released into the environment.",
        ),
        (
            "phillip-george-2024-spill",
            "20,000 gallons of vacuum gas oil",
            "LCPL Phillip C George",
            "May 15, 2024",
            "https://www.ntsb.gov/investigations/pages/DCA24FM040.aspx",
            "Contact of LCPL Phillip C George Tow with Terminal Dolphin, Power Transmission Pole, and Pelican Island Bridge",
            "There were no injuries, and about 20,000 gallons of vacuum gas oil was released into the waterway.",
        ),
        (
            "margaret-2015-loss",
            "$2 million",
            "Margaret",
            "August 31, 2015",
            "https://www.ntsb.gov/investigations/pages/DCA15LM032.aspx",
            "Sinking of Deck Barge Margaret",
            "The barge owner estimated the loss at $2 million.",
        ),
        (
            "jalma-topic-2021-damage",
            "$6 million",
            "Jalma Topic",
            "July 12, 2021",
            "https://www.ntsb.gov/investigations/pages/DCA21FM032.aspx",
            "Contact of Bulk Carrier Jalma Topic with Floating Office Structure",
            "The office barge and moorings sustained damages estimated at $6 million.",
        ),
        (
            "asia-zircon-2015-injuries",
            "Two",
            "Asia Zircon II",
            "July 8, 2015",
            "https://www.ntsb.gov/investigations/pages/DCA15LM026.aspx",
            "Marine Accident Brief: Equipment Failure on Bulk Carrier Asia Zircon II",
            "Two of the five longshoremen inside the cargo hold at the time suffered non-life threatening injuries.",
        ),
        (
            "yochow-2018-damage",
            "$21,338,000",
            "Yochow",
            "June 13, 2018",
            "https://www.ntsb.gov/investigations/pages/DCA18FM026.aspx",
            "Collision of Bulk Carrier Yochow with Articulated Tug and Barge OSG Independence/OSG 243",
            "Damage to the facility ($20 million), the barge ($1 million), and the bulk carrier ($338,000) amounted to an estimated $21,338,000.",
        ),
    )
    for key, answer, _vessel, event_date, url, title, excerpt in incident_facts:
        question_by_id = {
            "dali-2024-length": "How long was containership Dali in the NTSB account of the March 26, 2024 Key Bridge contact?",
            "president-eisenhower-2021-crew": "How many crewmembers were reported uninjured in the April 28, 2021 President Eisenhower fire?",
            "maunalei-2022-damage": "What damage estimate did the NTSB report for the August 11, 2022 loss of propulsion aboard Maunalei?",
            "kevin-michael-2021-tow": "What size tow was Kevin Michael pushing during its March 19, 2021 contact with the Melvin Price Locks and Dam guide wall?",
            "miss-dorothy-2021-barges": "How many barges was Miss Dorothy pushing when its engine room fire began on March 17, 2021?",
            "summer-wind-2014-spill": "How much fuel oil spilled after the March 22, 2014 collision involving bulk carrier Summer Wind?",
            "bunun-queen-2022-location": "How far south of Port Fourchon, Louisiana did the July 23, 2022 collision involving Bunun Queen occur?",
            "yangze-7-2024-damage": "What total damage estimate did the NTSB report for the July 19, 2024 Yangze 7 and Miss Peggy collision?",
            "natalie-jean-2018-fatalities": "How many of the three crewmembers aboard Natalie Jean died when it sank on March 12, 2018?",
            "jw-herron-2017-damage": "What damage estimate did the NTSB report for the December 13, 2017 J.W. Herron engine room fire?",
            "cosco-busan-2007-spill": "How much fuel oil was released into San Francisco Bay after the November 7, 2007 Cosco Busan allision?",
            "gunde-maersk-2015-damage": "What damage estimate did the NTSB report for the December 8, 2015 Gunde Maersk fire?",
            "alaganik-2019-fuel": "How much gasoline and diesel fuel was consumed or released in the July 7, 2019 Alaganik explosion and sinking?",
            "phillip-george-2024-spill": "How much vacuum gas oil was released in the May 15, 2024 LCPL Phillip C George tow incident?",
            "margaret-2015-loss": "What loss did the owner estimate after deck barge Margaret sank on August 31, 2015?",
            "jalma-topic-2021-damage": "What damage estimate did the NTSB report after Jalma Topic contacted a floating office structure on July 12, 2021?",
            "asia-zircon-2015-injuries": "How many longshoremen were injured during the July 8, 2015 Asia Zircon II crane incident?",
            "yochow-2018-damage": "What total damage estimate did the NTSB report for the June 13, 2018 Yochow collision?",
        }
        prompt = question_by_id[key]
        facts.append(
            LogisticsFact(
                id=f"log-incident-{key}",
                prompt=prompt,
                answer=answer,
                url=url,
                title=title,
                excerpt=excerpt,
                period=datetime.strptime(event_date, "%B %d, %Y").date().isoformat(),
                source_record_id=f"ntsb-marine-{key}",
            )
        )
    capacity_facts = (
        (
            "little-concert",
            "2,433 TEU",
            "Little Concert",
            "March 4, 2025",
            "https://www.hapag-lloyd.com/en/company/about-us/newsletter/2025/03/breaking-the-million-mark--hapag-lloyd-s-charter-fleet-reaches-n.html",
            "Breaking the million mark: Hapag-Lloyd’s charter fleet reaches new heights",
            "Mid February, the addition of the 2,433 TEU vessel “Little Concert” propelled our charter fleet capacity beyond the 1 million TEU threshold.",
        ),
        (
            "nordatlantic",
            "1,930 TEU",
            "Nordatlantic",
            "January 2025",
            "https://www.hapag-lloyd.com/fr/company/about-us/newsletter/2025/01/hapag-lloyd-breaks-record-with-over-300-ships-in-its-fleet.html",
            "Hapag-Lloyd surpasses 300 ships in its fleet for the first time",
            "Cargo Capacity | 1,930 TEU",
        ),
        (
            "hamburg-express",
            "23,660 TEU",
            "Hamburg Express",
            "November 2024",
            "https://www.hapag-lloyd.com/es/company/press/releases/2024/11/hapag-lloyd-christens-the--hamburg-express--in-the-port-of-hambu.html",
            "Hapag-Lloyd christens the Hamburg Express in the Port of Hamburg",
            "Seventh of 12 ships with 23,660 TEU capacity and dual-fuel technology.",
        ),
        (
            "company-fleet-2024",
            "2.2 million TEU",
            "Hapag-Lloyd fleet",
            "November 2024",
            "https://www.hapag-lloyd.com/es/company/press/releases/2024/11/hapag-lloyd-christens-the--hamburg-express--in-the-port-of-hambu.html",
            "Hapag-Lloyd christens the Hamburg Express in the Port of Hamburg",
            "With a fleet of 287 modern container ships and a total transport capacity of 2.2 million TEU, Hapag-Lloyd is one of the world’s leading liner shipping companies.",
        ),
        (
            "three-vessel-addition-2024",
            "over 60,000 TEU",
            "Damietta Express, Singapore Express, and Iquique Express",
            "May 2024",
            "https://www.hapag-lloyd.com/es/company/about-us/newsletter/2024/05/historic-capacity-increase-in-a-single-week-for-hapag-lloyd.html",
            "Historic capacity increase in a single week for Hapag-Lloyd",
            "The Damietta Express, the Singapore Express and the Iquique Express together add over 60,000 TEU to our total capacity.",
        ),
    )
    for key, answer, vessel, period, url, title, excerpt in capacity_facts:
        facts.append(
            LogisticsFact(
                id=f"log-capacity-{key}",
                prompt=f"According to Hapag-Lloyd's {period} fleet announcement, what container capacity in TEU was reported for {vessel}?",
                answer=answer,
                url=url,
                title=title,
                excerpt=excerpt,
                period=period[-4:],
                source_record_id=f"hapag-lloyd-capacity-{key}",
            )
        )
    return tuple(facts)


LOGISTICS_FACTS = _make_facts()


def to_query_gold_case(
    fact: LogisticsFact,
    *,
    retrieved_at_utc: str,
    raw_sha256: str,
    raw_path: str,
    excerpt: str,
) -> QueryGoldCase:
    """Build a validated canonical case after the source has been archived."""
    from query_gold.models import Derivation, Evidence, GoldAnswer, TemporalScope

    currency = "USD" if fact.answer.startswith("$") else None
    if fact.id.startswith(("log-la-", "log-capacity-")):
        units = "TEU"
    elif fact.id.startswith("log-rotterdam-"):
        units = "TEU" if "TEU" in fact.answer else "tonnes"
    elif currency:
        units = "USD"
    elif "gallon" in fact.answer.casefold():
        units = "gallons"
    elif "foot" in fact.answer.casefold():
        units = "feet"
    elif "barge" in fact.answer.casefold():
        units = "barges"
    elif fact.answer == "Two" or "crewmember" in fact.answer:
        units = "people"
    else:
        units = None

    if fact.period == "immutable":
        temporal = TemporalScope(
            kind="immutable",
            precision="immutable",
            immutableReason="The cited IMO identification scheme rule is a stable designation rule.",
        )
    elif fact.id.startswith("log-incident-"):
        temporal = TemporalScope(kind="event", precision="day", date=fact.period)
    else:
        temporal = TemporalScope(
            kind="period", precision="year", periodStart=fact.period, periodEnd=fact.period
        )
    return QueryGoldCase(
        schemaVersion="query-gold/v1",
        id=fact.id,
        categoryId=CATEGORY_ID,  # type: ignore[arg-type]
        query=fact.prompt,
        temporal=temporal,
        gold=GoldAnswer(
            answer=fact.answer,
            acceptedAnswers=[fact.answer],
            units=units,
            currency=currency,
        ),
        evidence=[
            Evidence(
                url=fact.url,
                title=fact.title,
                retrievedAtUTC=retrieved_at_utc,
                sourceRecordId=fact.source_record_id,
                rawSha256=raw_sha256,
                rawPath=raw_path,
                excerpt=excerpt,
            )
        ],
        derivation=Derivation(
            sourceFamily=(
                "imo_ship_identification_scheme"
                if fact.id.startswith("log-imo-")
                else "port_of_rotterdam_statistics"
                if fact.id.startswith("log-rotterdam-")
                else "ntsb_marine_incident_report"
                if fact.id.startswith("log-incident-")
                else "shipping_line_vessel_fleet_announcement"
                if fact.id.startswith("log-capacity-")
                else "port_of_los_angeles_statistics"
            ),
            generatorVersion=GENERATOR_VERSION,
            questionType=(
                "ship_identification_rule"
                if fact.id.startswith("log-imo-")
                else "port_segment_throughput"
                if fact.id.startswith("log-rotterdam-")
                else "marine_incident_record"
                if fact.id.startswith("log-incident-")
                else "container_vessel_capacity"
                if fact.id.startswith("log-capacity-")
                else "annual_port_throughput"
            ),
        ),
    )


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _cache_name(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def _append_attempt(output_dir: Path, ledger: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    ledger.append(entry)
    path = ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl")
    atomic_write_jsonl(path, ledger)


def _fetch_source(
    output_dir: Path,
    url: str,
    client: httpx.Client,
    ledger: list[dict[str, Any]],
) -> tuple[bytes, str, str, str]:
    """Read a pinned source or fetch it with bounded retries and an attempt ledger."""
    relative = f"raw/sources/{_cache_name(url)}.html"
    source_path = ensure_safe_path(output_dir / relative)
    metadata_path = ensure_safe_path(output_dir / f"{relative}.metadata.json")
    if source_path.is_file() and metadata_path.is_file():
        raw = source_path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = _sha256(raw)
        if metadata.get("url") != url or metadata.get("rawSha256") != digest:
            raise ValueError("cached logistics source metadata does not match its bytes")
        retrieved = metadata.get("retrievedAtUTC")
        if not isinstance(retrieved, str):
            raise ValueError("cached logistics source has no retrieval timestamp")
        return raw, digest, retrieved, relative

    host = urlsplit(url).hostname
    for attempt in range(1, MAX_RETRIES + 2):
        if len(ledger) >= MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("logistics source request limit reached")
        started = _now_utc()
        entry: dict[str, Any] = {
            "url": url,
            "attempt": attempt,
            "startedAtUTC": started,
            "status": None,
            "responseBytes": None,
            "responseSha256": None,
            "errorType": None,
        }
        try:
            response = client.get(url)
            entry["status"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = _sha256(response.content)
            _append_attempt(output_dir, ledger, entry)
            if response.status_code == 200:
                if len(response.content) > MAX_SOURCE_BYTES:
                    raise ValueError("logistics source exceeds the per-file byte limit")
                response.content.decode("utf-8", errors="strict")
                if response.url.host != host:
                    raise ValueError("logistics source redirected outside its pinned host")
                retrieved = _now_utc()
                atomic_write_bytes(source_path, response.content)
                atomic_write_bytes(
                    metadata_path,
                    json_bytes(
                        {
                            "url": url,
                            "rawSha256": _sha256(response.content),
                            "retrievedAtUTC": retrieved,
                            "retrievedAtBasis": "response_received_at_utc",
                        }
                    ),
                )
                return response.content, _sha256(response.content), retrieved, relative
            if attempt > MAX_RETRIES or response.status_code not in {
                408,
                425,
                429,
                500,
                502,
                503,
                504,
            }:
                raise RuntimeError(f"logistics source returned HTTP {response.status_code}")
        except httpx.RequestError as error:
            entry["errorType"] = type(error).__name__
            _append_attempt(output_dir, ledger, entry)
            if attempt > MAX_RETRIES:
                raise RuntimeError("logistics source failed after one retry") from None
    raise RuntimeError("logistics source request failed")


def _literal_excerpt(raw: bytes, answer: str) -> str:
    """Select a literal UTF-8 byte-source excerpt that includes the exact answer."""
    text = raw.decode("utf-8", errors="strict")
    match = re.search(re.escape(answer), text, flags=re.IGNORECASE)
    if match is None:
        raise ValueError(f"answer is absent from the captured source: {answer}")
    return text[max(0, match.start() - 300) : min(len(text), match.end() + 500)]


def _sources_markdown(cases: list[dict[str, Any]], ledger: list[dict[str, Any]]) -> str:
    url_counts: dict[str, int] = {}
    for case in cases:
        for evidence in case["evidence"]:
            url_counts[evidence["url"]] = url_counts.get(evidence["url"], 0) + 1
    sources = sorted(url_counts)
    type_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for case in cases:
        question_type = case["derivation"]["questionType"]
        type_counts[question_type] = type_counts.get(question_type, 0) + 1
        source_id = case["evidence"][0]["sourceRecordId"]
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
    source_concentration = max(source_counts.values(), default=0)
    return "\n".join(
        (
            "# Logistics, freight & supply chain source notes",
            "",
            "## Benchmark fit and construction",
            "",
            "The seeds cover annual Port of Los Angeles TEUs, Rotterdam's 2024 throughput, IMO ship identification rules, individual NTSB marine incident records, and container vessel/fleet capacities published by Hapag-Lloyd. Incident and capacity cases are a small selected sample and do not represent the full logistics sector.",
            "The collector fetches only when explicitly invoked, archives exact UTF-8 response bytes, and admits a case only if its literal gold answer occurs in the captured bytes. It retries once for retryable HTTP statuses or request errors and records each physical attempt, including failures.",
            "",
            "## Source and question-type concentration",
            "",
            f"Collected {len(cases)} cases from {len(sources)} distinct answer-bearing URLs in {len(ledger)} physical attempts; the most-used source record appears {source_concentration} time(s), and the most-used URL supports {max(url_counts.values(), default=0)} case(s).",
            "Question-type counts: "
            + ", ".join(f"{key}={value}" for key, value in sorted(type_counts.items())),
            "Source URLs: " + ", ".join(f"<{url}>" for url in sources),
            "",
            "## Rejections and review",
            "",
            "Cases whose HTTPS source is unavailable, exceeds the byte limit, is invalid UTF-8, or does not literally contain the answer are rejected. Manual sample review and direct-search discoverability review have not been performed by this collector.",
            "## Representativeness gaps and direct-search discoverability",
            "",
            "The Port of Los Angeles historical series is concentrated in one answer-bearing page. Incident questions use individual NTSB records, while the five capacity questions depend on a small number of Hapag-Lloyd fleet announcements. Freight rate, other carrier, container specification, and port telemetry sources are underrepresented. Normal public answer-bearing pages are cited below; direct-search discoverability has not been manually reviewed.",
            "",
            "## License and snapshot policy",
            "",
            "No blanket reuse license is asserted for the port-authority and IMO pages. Source snapshots, SHA-256 digests, and retrieval timestamps are pinned per URL. Refresh only through an explicit collection invocation.",
            "",
            "## Normal public answer-bearing pages",
            "",
            "The cited port, IMO, NTSB, and carrier pages are public answer-bearing pages. Their availability and search-result placement can change; each successful response is archived for later exact-evidence validation.",
            "",
        )
    )


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Capture public evidence on explicit invocation and return canonical records."""
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not 1 <= count <= len(LOGISTICS_FACTS)
    ):
        raise ValueError(f"count must be between 1 and {len(LOGISTICS_FACTS)}")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_safe_path(output_dir, require_existing=True)
    ledger_path = ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl")
    ledger: list[dict[str, Any]] = []
    if ledger_path.is_file():
        ledger = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    source_cache: dict[str, tuple[bytes, str, str, str]] = {}
    cases: list[dict[str, Any]] = []
    with httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    ) as client:
        for fact in LOGISTICS_FACTS[:count]:
            parsed = urlsplit(fact.url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("logistics sources must use HTTPS")
            if fact.url not in source_cache:
                source_cache[fact.url] = _fetch_source(output_dir, fact.url, client, ledger)
            raw, digest, retrieved, raw_path = source_cache[fact.url]
            case = to_query_gold_case(
                fact,
                retrieved_at_utc=retrieved,
                raw_sha256=digest,
                raw_path=raw_path,
                excerpt=_literal_excerpt(raw, fact.answer),
            )
            cases.append(case.model_dump(mode="json", exclude_none=True))
    source_ids = {item["sourceRecordId"] for case in cases for item in case["evidence"]}
    question_types = {case["derivation"]["questionType"] for case in cases}
    if count == 50 and (len(source_ids) < 25 or len(question_types) < 3):
        raise ValueError("logistics cases do not meet source-record and question-type gates")
    atomic_write_jsonl(ensure_safe_path(output_dir / "cases.jsonl"), cases)
    atomic_write_bytes(
        ensure_safe_path(output_dir / "sources.md"),
        _sources_markdown(cases, ledger).encode("utf-8"),
    )
    return cases
