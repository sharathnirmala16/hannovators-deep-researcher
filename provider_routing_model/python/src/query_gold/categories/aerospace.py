# ruff: noqa: E501
"""Collect aerospace telemetry and mission milestones from public NASA sources.

Each fact is verified against a fetched source page during explicit collection;
the exact source bytes and bounded evidence excerpts are preserved locally.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx

from query_gold.io import atomic_write_bytes, ensure_safe_path
from query_gold.models import QueryGoldCase

CATEGORY_ID = "14_aerospace_telemetry_records"
GENERATOR_VERSION = "aerospace-telemetry-collector/1"
MAX_RETRIES = 1
MAX_PHYSICAL_REQUESTS = 10
REQUEST_TIMEOUT_SECONDS = 20.0
USER_AGENT = "query-gold-aerospace-curation/1.0 (public NASA mission records)"


@dataclass(frozen=True, slots=True)
class AerospaceFact:
    case_id: str
    question: str
    answer: str
    url: str
    source_family: str


class _TextExtractor(HTMLParser):
    """Extract visible text from a public HTML page for literal fact checks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._hidden:
            self._hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden and data.strip():
            self.parts.append(data)


def _page_text(body: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(body.decode("utf-8", errors="strict"))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _normalize_fact_text(value: str) -> str:
    value = value.casefold().replace("jan.", "january").replace("feb.", "february")
    value = value.replace("sept.", "september").replace("sep.", "september")
    value = value.replace(" x ", " by ")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _fact_date(fact: AerospaceFact) -> tuple[str, str, str | None]:
    """Return source-supported temporal kind, precision, and ISO scope value."""
    if fact.source_family == "nasa_artemis_i_timeline":
        met_day = int(fact.answer[:3])
        event_date = date(2022, 11, 16) + timedelta(days=met_day)
        return "event", "day", event_date.isoformat()
    if fact.source_family == "nasa_apollo_11_overview":
        if fact.case_id == "aero-apollo11-launch-date":
            return "event", "day", "1969-07-16"
        return "period", "day", "1969-07-16/1969-07-24"
    if fact.source_family == "nasa_apollo_5_mission_page":
        if fact.case_id == "aero-apollo5-launch-date":
            return "event", "day", "1968-01-22"
        if fact.case_id == "aero-apollo5-end-date":
            return "event", "day", "1968-01-23"
        if fact.case_id in {"aero-apollo5-launch-time", "aero-apollo5-lm-separation"}:
            return "event", "day", "1968-01-22"
        return "period", "day", "1968-01-22/1968-01-23"
    if fact.source_family == "nasa_ingenuity_mission_page":
        date_by_id = {
            "aero-ingenuity-first-flight": "2021-04-19",
            "aero-ingenuity-last-flight": "2024-01-18",
            "aero-ingenuity-launch-date": "2020-07-30",
            "aero-ingenuity-mars-landing": "2021-02-18",
            "aero-ingenuity-mission-complete": "2024-01-25",
            "aero-ingenuity-rotor-spin": "2021-04-08",
            "aero-ingenuity-tech-demo-complete": "2021-05-07",
        }
        if fact.case_id in date_by_id:
            return "event", "day", date_by_id[fact.case_id]
        return "version", "version", "Ingenuity mission facts as published on NASA Science"
    return "version", "version", "Space Technology 5 quick facts as published by NASA/JPL"


def _excerpt_for(text: str, answer: str) -> str:
    normalized_text = _normalize_fact_text(text)
    normalized_answer = _normalize_fact_text(answer)
    start = normalized_text.find(normalized_answer)
    if start < 0:
        raise ValueError(f"answer token {answer!r} is absent from source text")
    # Map the normalized match back into the rendered text. Binary search keeps
    # this reliable even when HTML text normalization removes lots of markup.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high) // 2
        if len(_normalize_fact_text(text[:middle])) < start:
            low = middle + 1
        else:
            high = middle
    approx = low
    left = max(0, text.rfind(".", 0, approx) + 1)
    right = text.find(".", approx)
    if right < 0:
        right = min(len(text), approx + 500)
    excerpt = text[left : min(right + 1, left + 1800)].strip()
    if normalized_answer not in _normalize_fact_text(excerpt):
        left = max(0, approx - 500)
        excerpt = text[left : min(len(text), left + 1800)].strip()
    if not excerpt or len(excerpt) > 8000 or normalized_answer not in _normalize_fact_text(excerpt):
        raise ValueError("could not construct a bounded evidence excerpt")
    return excerpt


def _append_request(output_dir: Path, row: dict[str, Any]) -> None:
    path = ensure_safe_path(output_dir / "raw" / "requests.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        )


def _fetch_page(
    output_dir: Path,
    url: str,
    client: httpx.Client,
    request_counter: list[int],
) -> tuple[bytes, str]:
    for attempt in range(MAX_RETRIES + 1):
        request_counter[0] += 1
        if request_counter[0] > MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("aerospace collector physical request limit reached")
        started = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        try:
            response = client.get(url)
            row = {
                "url": url,
                "attempt": attempt + 1,
                "startedAtUTC": started,
                "statusCode": response.status_code,
                "outcome": "http_response",
            }
            _append_request(output_dir, row)
            if response.status_code == 200:
                return response.content, started
            if (
                response.status_code not in {408, 425, 429, 500, 502, 503, 504}
                or attempt == MAX_RETRIES
            ):
                raise RuntimeError(f"NASA source returned HTTP {response.status_code}: {url}")
        except httpx.HTTPError as error:
            _append_request(
                output_dir,
                {
                    "url": url,
                    "attempt": attempt + 1,
                    "startedAtUTC": started,
                    "outcome": "network_error",
                    "errorType": type(error).__name__,
                },
            )
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"NASA source request failed: {url}") from error
        time.sleep(0.15 * (attempt + 1))
    raise RuntimeError(f"NASA source request exhausted retries: {url}")


def _write_sources_note(output_dir: Path, cases: list[dict[str, Any]]) -> None:
    counts = Counter(case["derivation"]["sourceFamily"] for case in cases)
    by_id = {fact.source_family: fact.url for fact in FACTS}
    lines = [
        "# Aerospace and telemetry sources",
        "",
        "## Benchmark fit and construction method",
        "",
        "This collection covers launch and flight milestone telemetry, orbital figures, and mission events. Each question names a specific mission, metric, and mission date or period. Values are curated from public NASA/JPL mission pages and checked against a literal excerpt during explicit collection.",
        "",
        "## Rejected candidates and source limitations",
        "",
        "No source page is accepted when it fails to load, exceeds the response limit, or does not contain the exact answer token. Candidate rejection counts are recorded in the physical attempt ledger where a request was made. No trajectory values are calculated from orbital elements.",
        "",
        "Facts are scoped to their documented mission date or mission period. NASA/JPL source pages were fetched during explicit collection; raw response bytes, SHA-256 digests, and physical request attempts are stored under `raw/`. The 50 sourceRecordIds identify individual fact/event records within these five pages; they do not represent 50 distinct documents.",
        "",
        "## License, revision, and snapshot policy",
        "",
        "No blanket reuse license is asserted. The collector pins retrieved-at timestamps, response hashes, and raw source bytes. Refresh requires an explicit collection invocation; changed or missing answer text rejects the case.",
        "",
        "## Source concentration and manual sample review",
        "",
        "The 50 fact records use five public pages, so source concentration is high and is reported by page. A manual sample review and direct-search discoverability review have not been completed; these are required before treating the set as representative.",
        "",
        "## Representativeness gaps and discoverability limitations",
        "",
        "The selected missions do not represent all launch providers, spacecraft classes, or telemetry formats. Detailed flight trajectory telemetry and commercial launch manifests are underrepresented. NASA/JPL public pages are normal public answer-bearing pages, but page indexing and search-result rank are not guaranteed.",
        "",
        "## Normal public answer-bearing pages",
        "",
        "| Source record | Cases | URL |",
        "|---|---:|---|",
    ]
    for family in sorted(counts):
        lines.append(f"| {family} | {counts[family]} | {by_id[family]} |")
    atomic_write_bytes(output_dir / "sources.md", ("\n".join(lines) + "\n").encode("utf-8"))


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Fetch source pages, archive bytes, verify literal facts, and return cases."""
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = ensure_safe_path(output_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    request_counter = [0]
    pages: dict[str, tuple[bytes, str, str]] = {}
    with httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=5.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for fact in FACTS[:count]:
            if fact.url not in pages:
                body, retrieved_at = _fetch_page(output_dir, fact.url, client, request_counter)
                digest = hashlib.sha256(body).hexdigest()
                filename = f"{digest}.html"
                raw_file_path = ensure_safe_path(raw_dir / "pages" / filename)
                atomic_write_bytes(raw_file_path, body)
                pages[fact.url] = (body, retrieved_at, f"raw/pages/{filename}")

    cases: list[dict[str, Any]] = []
    for fact in FACTS[:count]:
        body, retrieved_at, raw_rel_path = pages[fact.url]
        text = _page_text(body)
        excerpt = _excerpt_for(text, fact.answer)
        kind, precision, scope_value = _fact_date(fact)
        if scope_value is None:
            raise ValueError(f"missing temporal scope for {fact.case_id}")
        if kind == "period":
            scope_fields = {
                "periodStart": scope_value.split("/")[0],
                "periodEnd": scope_value.split("/")[1],
            }
        elif kind == "event":
            scope_fields = {"date": scope_value}
        else:
            scope_fields = {"version": scope_value}
        raw_hash = hashlib.sha256(body).hexdigest()
        record = {
            "schemaVersion": "query-gold/v1",
            "id": fact.case_id,
            "categoryId": CATEGORY_ID,
            "query": fact.question,
            "temporal": {"kind": kind, "precision": precision, **scope_fields},
            "gold": {"answer": fact.answer, "value": fact.answer, "acceptedAnswers": [fact.answer]},
            "evidence": [
                {
                    "url": fact.url,
                    "title": {
                        "nasa_artemis_i_timeline": "Artemis I Mission Timeline",
                        "nasa_apollo_11_overview": "Apollo 11 Mission Overview",
                        "nasa_ingenuity_mission_page": "Ingenuity Mars Helicopter",
                        "nasa_apollo_5_mission_page": "Apollo 5",
                        "nasa_jpl_space_technology_5_facts": "Space Technology 5 Quick Facts",
                    }[fact.source_family],
                    "retrievedAtUTC": retrieved_at,
                    "sourceRecordId": f"{fact.source_family}:{fact.case_id}",
                    "license": "unknown",
                    "rawSha256": raw_hash,
                    "rawPath": raw_rel_path,
                    "excerpt": excerpt,
                }
            ],
            "derivation": {
                "sourceFamily": fact.source_family,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": fact.source_family,
            },
        }
        cases.append(
            QueryGoldCase.model_validate(record).model_dump(mode="json", exclude_none=True)
        )
    _write_sources_note(output_dir, cases)
    return cases


ARTEMIS_TIMELINE = "https://www.nasa.gov/reference/artemis-i-mission-timeline/"
APOLLO_11 = "https://www.nasa.gov/history/apollo-11-mission-overview/"
INGENUITY = "https://science.nasa.gov/mission/mars-2020-perseverance/ingenuity-mars-helicopter/"
APOLLO_5 = "https://www.nasa.gov/mission/apollo-5/"
SPACE_TECH_5 = "https://www.jpl.nasa.gov/nmp/st5/QUICKFACTS/quickfacts.php"


FACTS: tuple[AerospaceFact, ...] = (
    AerospaceFact(
        "aero-artemis-launch-met",
        "In NASA's Artemis I mission timeline, what mission elapsed time (MET) is listed for launch?",
        "000/00:00:00",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-max-q",
        "At what mission elapsed time did Artemis I reach maximum dynamic pressure?",
        "000/00:01:10",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-booster-separation",
        "What MET does NASA list for Artemis I solid rocket booster separation?",
        "000/00:02:12",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-fairing-jettison",
        "At what MET was the Artemis I service module fairing jettisoned?",
        "000/00:03:11",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-las-jettison",
        "What MET does NASA list for Artemis I launch abort system jettison?",
        "000/00:03:16",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-core-meco",
        "At what MET was Artemis I core stage main engine cutoff commanded?",
        "000/00:08:03",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-core-separation",
        "When, in MET, did the Artemis I core stage separate from the interim cryogenic propulsion stage?",
        "000/00:08:03",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-array-deploy",
        "What MET marks the beginning of Orion's solar array wing deployment on Artemis I?",
        "000/00:18:09",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-perigee-raise",
        "At what MET did the Artemis I perigee raise maneuver occur?",
        "000/00:52:56",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-tli",
        "What MET is listed for the Artemis I translunar injection burn?",
        "000/01:29:27",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-orion-icps-sep",
        "At what MET did Orion separate from the interim cryogenic propulsion stage on Artemis I?",
        "000/01:57:36",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-otcb1",
        "What MET does NASA list for Artemis I outbound trajectory correction burn 1?",
        "000/07:47:31",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-otcb2",
        "On flight day 2, at what MET did Artemis I outbound trajectory correction burn 2 occur?",
        "001/04:47:31",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-otcb3",
        "On flight day 5, what MET is listed for Artemis I outbound trajectory correction burn 3?",
        "004/06:40:14",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-otcb4",
        "What MET is listed for Artemis I outbound trajectory correction burn 4 on flight day 6?",
        "005/00:40:14",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-artemis-outbound-flyby",
        "At what MET did Artemis I's outbound powered flyby burn occur?",
        "005/06:40:14",
        ARTEMIS_TIMELINE,
        "nasa_artemis_i_timeline",
    ),
    AerospaceFact(
        "aero-apollo11-launch-date",
        "On what date did Apollo 11 launch from Cape Kennedy?",
        "July 16, 1969",
        APOLLO_11,
        "nasa_apollo_11_overview",
    ),
    AerospaceFact(
        "aero-apollo11-launch-time",
        "At what local time did Apollo 11 launch according to NASA's mission overview?",
        "9:32 a.m. EDT",
        APOLLO_11,
        "nasa_apollo_11_overview",
    ),
    AerospaceFact(
        "aero-apollo11-initial-orbit",
        "What initial Earth orbit, in miles, did Apollo 11 enter?",
        "114 by 116 miles",
        APOLLO_11,
        "nasa_apollo_11_overview",
    ),
    AerospaceFact(
        "aero-apollo11-translunar-burn",
        "How long was Apollo 11's second S-IVB burn that placed it into translunar orbit?",
        "5 minutes, 48 seconds",
        APOLLO_11,
        "nasa_apollo_11_overview",
    ),
    AerospaceFact(
        "aero-apollo11-touchdown",
        "Where did Apollo 11's Eagle land on the Moon?",
        "Sea of Tranquility, Site 2",
        APOLLO_11,
        "nasa_apollo_11_overview",
    ),
    AerospaceFact(
        "aero-ingenuity-first-flight",
        "On what date did NASA's Ingenuity helicopter make its first powered flight on Mars?",
        "April 19, 2021",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-last-flight",
        "On what date did Ingenuity fly for the last time?",
        "January 18, 2024",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-flight-count",
        "How many flights did Ingenuity complete across its Mars mission?",
        "72 flights",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-planned-flight-cap",
        "How many test flights was Ingenuity originally designed to make at most?",
        "Five test flights",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-planned-duration",
        "Over what planned period was Ingenuity designed to complete its original technology demonstration?",
        "30 days",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-launch-date",
        "On what date did the mission carrying Ingenuity launch from Cape Canaveral?",
        "July 30, 2020",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-mars-landing",
        "On what date did Ingenuity land in Jezero Crater on Mars?",
        "February 18, 2021",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-mission-complete",
        "On what date did NASA report Ingenuity's mission completed?",
        "January 25, 2024",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-rotor-spin",
        "On what date did Ingenuity complete its first rotor spin tests?",
        "April 8, 2021",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-ingenuity-tech-demo-complete",
        "On what date did Ingenuity complete its technology demonstration phase?",
        "May 7, 2021",
        INGENUITY,
        "nasa_ingenuity_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-parking-orbit",
        "What Earth parking orbit did Apollo 5 enter after launch, in kilometers?",
        "163 x 222 km",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-orbit-period",
        "What orbital period did NASA report for Apollo 5's initial Earth parking orbit?",
        "88.3 minutes",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-inclination",
        "What inclination did NASA report for Apollo 5's initial Earth orbit?",
        "31.63 degrees",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-lm-orbit",
        "After separation, what orbit did Apollo 5's Lunar Module enter, in kilometers?",
        "167 x 222 km",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-lm-orbit-period",
        "What orbital period did NASA report for the Apollo 5 Lunar Module orbit?",
        "88.4 minutes",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-launch-mass",
        "What launch mass does NASA list for Apollo 5?",
        "14,360 kg",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-revolutions",
        "How many revolutions did Apollo 5 complete?",
        "7",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-launch-vehicle",
        "Which launch vehicle carried Apollo 5?",
        "Saturn IB SA-204",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-launch-date",
        "On what date was Apollo 5 launched?",
        "Jan. 22, 1968",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-mission-duration",
        "What mission duration does NASA report for Apollo 5?",
        "11 hours, 10 minutes",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-launch-time",
        "At what time did Apollo 5 launch, according to NASA?",
        "5:48:09 p.m. EST",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-lm-separation",
        "How long after launch did the Apollo 5 Lunar Module separate from its adapter?",
        "43 min 52 sec",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-end-date",
        "On what date did NASA list Apollo 5's end of mission?",
        "Jan. 23, 1968",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-apollo5-end-time",
        "What local time does NASA list for Apollo 5's end of mission?",
        "2:45 a.m. EST",
        APOLLO_5,
        "nasa_apollo_5_mission_page",
    ),
    AerospaceFact(
        "aero-st5-perigee",
        "What perigee altitude does NASA's Space Technology 5 quick facts page give?",
        "300 km (186 miles)",
        SPACE_TECH_5,
        "nasa_jpl_space_technology_5_facts",
    ),
    AerospaceFact(
        "aero-st5-apogee",
        "What apogee altitude does NASA's Space Technology 5 quick facts page give?",
        "4500 km (2796 miles)",
        SPACE_TECH_5,
        "nasa_jpl_space_technology_5_facts",
    ),
    AerospaceFact(
        "aero-st5-inclination",
        "What orbital inclination does NASA list for Space Technology 5?",
        "105.6 degrees",
        SPACE_TECH_5,
        "nasa_jpl_space_technology_5_facts",
    ),
    AerospaceFact(
        "aero-st5-orbit-period",
        "What orbital period does NASA list for Space Technology 5?",
        "136 minutes",
        SPACE_TECH_5,
        "nasa_jpl_space_technology_5_facts",
    ),
    AerospaceFact(
        "aero-st5-orbits-day",
        "About how many orbits per day does NASA list for Space Technology 5?",
        "about 10.5",
        SPACE_TECH_5,
        "nasa_jpl_space_technology_5_facts",
    ),
)


def benchmark_rows() -> tuple[dict[str, str], ...]:
    """Return answer-free public rows in eval_v2's {id, prompt} format."""
    return tuple({"id": fact.case_id, "prompt": fact.question} for fact in FACTS)


def answer_rows() -> tuple[dict[str, object], ...]:
    """Return private {id, prompt, answer, goldUrls} reference rows."""
    return tuple(
        {"id": fact.case_id, "prompt": fact.question, "answer": fact.answer, "goldUrls": [fact.url]}
        for fact in FACTS
    )
