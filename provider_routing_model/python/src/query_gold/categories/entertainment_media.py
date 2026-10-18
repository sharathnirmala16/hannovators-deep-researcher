# ruff: noqa: E501
"""Collect entertainment facts from Box Office Mojo, Billboard, and AFI Catalog.

Collection is explicit and bounded. Each canonical answer is accepted only when
the pinned public page contains the selected answer text; the fetched response
bytes and exact excerpt are retained under the caller's output directory.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path
from query_gold.models import QueryGoldCase

CATEGORY_ID = "18_entertainment_box_office_media_registries"
GENERATOR_VERSION = "entertainment-media-collector/1"
MAX_RETRIES = 1
MAX_PHYSICAL_REQUESTS = 100
MAX_SOURCE_BYTES = 12_000_000
REQUEST_TIMEOUT_SECONDS = 20.0
USER_AGENT = "query-gold-entertainment-curation/1.0 (public media registries)"


@dataclass(frozen=True, slots=True)
class MediaFact:
    case_id: str
    query: str
    answer: str
    url: str
    title: str
    source_record_id: str
    source_family: str
    question_type: str
    scope_kind: str
    scope_value: str
    evidence_subject: str | None = None


class _TextExtractor(HTMLParser):
    """Read visible text from HTML for matching and exact excerpt selection."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())


def _page_text(body: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(body.decode("utf-8", errors="strict"))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _excerpt(
    raw_text: str,
    visible_text: str,
    answer: str,
    subject: str,
    question_type: str,
) -> str:
    """Return raw HTML bytes as an exact excerpt after validating page context."""
    visible = visible_text.casefold()
    subject_offset = visible.find(subject.casefold())
    answer_offset = visible.find(answer.casefold())
    if subject_offset < 0:
        raise ValueError(f"subject {subject!r} is not present in its public source page")
    if answer_offset < 0:
        raise ValueError(f"answer {answer!r} is not present in its public source page")
    if question_type == "weekly_chart_position":
        rank_before_song = visible[max(0, subject_offset - 24) : subject_offset]
        if not re.search(rf"(?:^|\s){re.escape(answer)}\s+(?:new\s+)?$", rank_before_song):
            raise ValueError("Billboard chart row does not place the song at the seeded rank")
    elif abs(subject_offset - answer_offset) > 2000:
        raise ValueError("answer and subject are too far apart in the visible source text")

    # HTML can place a title and a summary value far apart in raw markup. The
    # source title and URL identify the record; the quoted substring stays a
    # literal raw-byte excerpt centered on the supported answer field.
    normalized = raw_text.casefold()
    offset = normalized.find(answer.casefold())
    if offset < 0:
        raise ValueError(f"answer {answer!r} is not an exact substring of source bytes")
    raw_subject_offset = normalized.find(subject.casefold())
    if question_type == "weekly_chart_position" and raw_subject_offset >= 0:
        start = max(0, raw_subject_offset - 1000)
        end = min(len(raw_text), raw_subject_offset + len(subject) + 1000)
    else:
        start = max(0, offset - 250)
        end = min(len(raw_text), offset + len(answer) + 500)
    excerpt = raw_text[start:end]
    if answer.casefold() not in excerpt.casefold() or len(excerpt) > 8000:
        raise ValueError("could not construct a bounded raw answer excerpt")
    return excerpt


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fetch(
    output_dir: Path, url: str, client: httpx.Client, attempts: list[dict[str, Any]]
) -> tuple[bytes, str]:
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    rel_path = f"raw/pages/{cache_key}.html"
    raw_path = ensure_safe_path(output_dir / rel_path)
    meta_path = ensure_safe_path(output_dir / f"{rel_path}.metadata.json")
    if raw_path.is_file() and meta_path.is_file():
        raw = raw_path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("url") != url or meta.get("rawSha256") != hashlib.sha256(raw).hexdigest():
            raise ValueError("cached page metadata does not match its source bytes")
        retrieved_at = meta.get("retrievedAtUTC")
        if isinstance(retrieved_at, str):
            return raw, retrieved_at
        raise ValueError("cached page has no retrieval timestamp")

    host = urlsplit(url).hostname
    for attempt in range(1, MAX_RETRIES + 2):
        started = _now()
        entry: dict[str, Any] = {"url": url, "attempt": attempt, "startedAtUTC": started}
        try:
            response = client.get(url)
            entry["statusCode"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = hashlib.sha256(response.content).hexdigest()
            attempts.append(entry)
            atomic_write_jsonl(
                ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"), attempts
            )
            if response.status_code == 200:
                if len(response.content) > MAX_SOURCE_BYTES:
                    raise ValueError("source exceeds the per-page byte limit")
                response.content.decode("utf-8", errors="strict")
                if response.url.host != host:
                    raise ValueError("source redirected outside its pinned host")
                retrieved_at = _now()
                digest = hashlib.sha256(response.content).hexdigest()
                atomic_write_bytes(raw_path, response.content)
                atomic_write_bytes(
                    meta_path,
                    json.dumps(
                        {"url": url, "rawSha256": digest, "retrievedAtUTC": retrieved_at},
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                )
                return response.content, retrieved_at
            if (
                response.status_code not in {408, 425, 429, 500, 502, 503, 504}
                or attempt > MAX_RETRIES
            ):
                raise RuntimeError(f"media source returned HTTP {response.status_code}: {url}")
        except httpx.HTTPError as error:
            entry["errorType"] = type(error).__name__
            if not attempts or attempts[-1] is not entry:
                attempts.append(entry)
            atomic_write_jsonl(
                ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"), attempts
            )
            if attempt > MAX_RETRIES:
                raise RuntimeError(f"media source request failed: {url}") from error
        time.sleep(0.15 * attempt)
    raise RuntimeError(f"media source request exhausted retries: {url}")


def _fact(
    case_id: str,
    query: str,
    answer: str,
    url: str,
    title: str,
    record_id: str,
    family: str,
    question_type: str,
    scope_kind: str,
    scope_value: str,
    evidence_subject: str | None = None,
) -> MediaFact:
    return MediaFact(
        case_id,
        query,
        answer,
        url,
        title,
        record_id,
        family,
        question_type,
        scope_kind,
        scope_value,
        evidence_subject,
    )


# Facts use individual dated chart rows and film records as sourceRecordIds. The
# page itself remains the public answer-bearing evidence; collection rejects any
# seed whose answer is not present in the captured page.
BOM_FACTS: tuple[MediaFact, ...] = (
    _fact(
        "media-bom-barbie-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Barbie (2023)?",
        "$162,022,044",
        "https://www.boxofficemojo.com/title/tt1517268/",
        "Barbie",
        "bom-title-tt1517268-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2023",
    ),
    _fact(
        "media-bom-oppenheimer-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Oppenheimer (2023)?",
        "$82,455,420",
        "https://www.boxofficemojo.com/title/tt15398776/",
        "Oppenheimer",
        "bom-title-tt15398776-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2023",
    ),
    _fact(
        "media-bom-endgame-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Avengers: Endgame (2019)?",
        "$357,115,007",
        "https://www.boxofficemojo.com/title/tt4154796/",
        "Avengers: Endgame",
        "bom-title-tt4154796-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2019",
    ),
    _fact(
        "media-bom-spider-man-nwh-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Spider-Man: No Way Home (2021)?",
        "$260,138,569",
        "https://www.boxofficemojo.com/title/tt10872600/",
        "Spider-Man: No Way Home",
        "bom-title-tt10872600-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2021",
    ),
    _fact(
        "media-bom-force-awakens-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Star Wars: The Force Awakens (2015)?",
        "$247,966,675",
        "https://www.boxofficemojo.com/title/tt2488496/",
        "Star Wars: Episode VII - The Force Awakens",
        "bom-title-tt2488496-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2015",
    ),
    _fact(
        "media-bom-infinity-war-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Avengers: Infinity War (2018)?",
        "$257,698,183",
        "https://www.boxofficemojo.com/title/tt4154756/",
        "Avengers: Infinity War",
        "bom-title-tt4154756-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2018",
    ),
    _fact(
        "media-bom-lion-king-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for The Lion King (2019)?",
        "$191,770,759",
        "https://www.boxofficemojo.com/title/tt6105098/",
        "The Lion King",
        "bom-title-tt6105098-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2019",
    ),
    _fact(
        "media-bom-black-panther-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Black Panther (2018)?",
        "$202,003,951",
        "https://www.boxofficemojo.com/title/tt1825683/",
        "Black Panther",
        "bom-title-tt1825683-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2018",
    ),
    _fact(
        "media-bom-jurassic-world-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Jurassic World (2015)?",
        "$208,806,270",
        "https://www.boxofficemojo.com/title/tt0369610/",
        "Jurassic World",
        "bom-title-tt0369610-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2015",
    ),
    _fact(
        "media-bom-avengers-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for The Avengers (2012)?",
        "$207,438,708",
        "https://www.boxofficemojo.com/title/tt0848228/",
        "The Avengers",
        "bom-title-tt0848228-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2012",
    ),
    _fact(
        "media-bom-deadpool-wolverine-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Deadpool & Wolverine (2024)?",
        "$211,435,291",
        "https://www.boxofficemojo.com/title/tt6263850/",
        "Deadpool & Wolverine",
        "bom-title-tt6263850-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2024",
    ),
    _fact(
        "media-bom-inside-out-2-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Inside Out 2 (2024)?",
        "$154,201,673",
        "https://www.boxofficemojo.com/title/tt22022452/",
        "Inside Out 2",
        "bom-title-tt5952382-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2024",
    ),
    _fact(
        "media-bom-super-mario-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for The Super Mario Bros. Movie (2023)?",
        "$146,361,865",
        "https://www.boxofficemojo.com/title/tt6718170/",
        "The Super Mario Bros. Movie",
        "bom-title-tt6718170-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2023",
    ),
    _fact(
        "media-bom-finding-dory-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Finding Dory (2016)?",
        "$135,060,273",
        "https://www.boxofficemojo.com/title/tt2277860/",
        "Finding Dory",
        "bom-title-tt2277860-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2016",
    ),
    _fact(
        "media-bom-frozen-2-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Frozen II (2019)?",
        "$130,263,358",
        "https://www.boxofficemojo.com/title/tt4520988/",
        "Frozen II",
        "bom-title-tt4520988-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2019",
    ),
    _fact(
        "media-bom-beauty-beast-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Beauty & the Beast (2017)?",
        "$174,750,616",
        "https://www.boxofficemojo.com/title/tt2771200/",
        "Beauty and the Beast",
        "bom-title-tt2771200-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2017",
    ),
    _fact(
        "media-bom-dark-knight-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for The Dark Knight (2008)?",
        "$158,411,483",
        "https://www.boxofficemojo.com/title/tt0468569/",
        "The Dark Knight",
        "bom-title-tt0468569-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2008",
    ),
    _fact(
        "media-bom-hp-deathly-hallows-2-opening-weekend",
        "What domestic opening weekend gross does Box Office Mojo list for Harry Potter: Deathly Hallows Part 2 (2011)?",
        "$169,189,427",
        "https://www.boxofficemojo.com/title/tt1201607/",
        "Harry Potter and the Deathly Hallows: Part 2",
        "bom-title-tt1201607-domestic-opening",
        "box_office_mojo_title_record",
        "domestic_opening_weekend_gross",
        "period",
        "2011",
    ),
)


def _chart_facts() -> tuple[MediaFact, ...]:
    # The dated Billboard table reports these song and rank pairs in one page.
    chart_date = "2024-03-09"
    rows = (
        (1, "Texas Hold 'Em"),
        (2, "Carnival"),
        (3, "Lovin On Me"),
        (4, "Beautiful Things"),
        (5, "Lose Control"),
        (6, "Saturn"),
        (7, "I Remember Everything"),
        (8, "Greedy"),
        (9, "Snooze"),
        (10, "Cruel Summer"),
        (11, "Stick Season"),
        (12, "Agora Hills"),
        (13, "Redrum"),
        (14, "Fast Car"),
        (15, "Last Night"),
        (16, "Water"),
    )
    return tuple(
        _fact(
            f"media-billboard-hot100-{chart_date}-rank-{rank}",
            f"What position did {song} hold on the Billboard Hot 100 chart dated {chart_date}?",
            str(rank),
            f"https://ca.billboard.com/charts/hot-100/{chart_date}",
            f"Billboard Hot 100 — {chart_date}",
            f"billboard-hot-100-{chart_date}-row-{rank}",
            "billboard_hot_100_weekly_chart",
            "weekly_chart_position",
            "event",
            chart_date,
            song,
        )
        for rank, song in rows
    )


def _credit_facts() -> tuple[MediaFact, ...]:
    # The AFI Catalog's structured production-credit sections explicitly label
    # directors and producers. Each question requests one named role only.
    records = (
        ("american-dream", "American Dream (1992)", "59177", "Barbara Kopple", "Arthur Cohn"),
        (
            "man-who-wasnt-there",
            "The Man Who Wasn't There (2001)",
            "53923",
            "Joel Coen",
            "Ethan Coen",
        ),
        ("the-cowboys", "The Cowboys (1972)", "54695", "Mark Rydell", "Mark Rydell"),
        ("movie-movie", "Movie Movie (1978)", "56949", "Stanley Donen", "Stanley Donen"),
        ("lake-house", "The Lake House (2006)", "63909", "Alejandro Agresti", "Doug Davison"),
        ("say-anything", "Say Anything... (1989)", "58268", "Cameron Crowe", "Polly Platt"),
        ("monster-ball", "Monster's Ball (2001)", "53924", "Marc Forster", "Lee Daniels"),
        ("back-future", "Back to the Future (1985)", "55763", "Robert Zemeckis", "Neil Canton"),
    )
    facts: list[MediaFact] = []
    for slug, film, afi_id, director, producer in records:
        url = f"https://catalog.afi.com/Catalog/MovieDetails/{afi_id}"
        for role, answer in (("director", director), ("producer", producer)):
            facts.append(
                _fact(
                    f"media-afi-{slug}-{role}",
                    f"According to the AFI Catalog production credits for {film}, who is listed as the {role}?",
                    answer,
                    url,
                    film,
                    f"afi-film-{afi_id}-{role}",
                    "afi_catalog_production_credits",
                    f"film_{role}_credit",
                    "immutable",
                    "production credit is a fixed catalog fact",
                )
            )
    return tuple(facts)


FACTS: tuple[MediaFact, ...] = BOM_FACTS + _chart_facts() + _credit_facts()


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Capture public pages, verify each answer, and return strict query/gold rows."""
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")
    selected = FACTS[:count]
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_safe_path(output_dir / "raw").mkdir(parents=True, exist_ok=True)
    pages: dict[str, tuple[bytes, str, str]] = {}
    attempts: list[dict[str, Any]] = []
    with httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=5.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for fact in selected:
            if fact.url in pages:
                continue
            if len(attempts) >= MAX_PHYSICAL_REQUESTS:
                raise RuntimeError("media collector physical request limit reached")
            body, retrieved_at = _fetch(output_dir, fact.url, client, attempts)
            digest = hashlib.sha256(body).hexdigest()
            rel_path = f"raw/pages/{digest}.html"
            atomic_write_bytes(ensure_safe_path(output_dir / rel_path), body)
            pages[fact.url] = (body, retrieved_at, rel_path)

    cases: list[dict[str, Any]] = []
    for fact in selected:
        body, retrieved_at, rel_path = pages[fact.url]
        visible_text = _page_text(body)
        subject = fact.evidence_subject or fact.title
        if fact.source_family == "afi_catalog_production_credits":
            subject = subject.split(" (")[0]
        excerpt = _excerpt(
            body.decode("utf-8", errors="strict"),
            visible_text,
            fact.answer,
            subject,
            fact.question_type,
        )
        if fact.scope_kind == "period":
            temporal = {
                "kind": "period",
                "precision": "year",
                "periodStart": fact.scope_value,
                "periodEnd": fact.scope_value,
            }
        elif fact.scope_kind == "event":
            temporal = {"kind": "event", "precision": "day", "date": fact.scope_value}
        elif fact.scope_kind == "immutable":
            temporal = {
                "kind": "immutable",
                "precision": "immutable",
                "immutableReason": fact.scope_value,
            }
        else:
            temporal = {"kind": "version", "precision": "version", "version": fact.scope_value}
        digest = hashlib.sha256(body).hexdigest()
        gold: dict[str, Any] = {
            "answer": fact.answer,
            "value": fact.answer,
            "acceptedAnswers": [fact.answer],
        }
        if fact.question_type == "domestic_opening_weekend_gross":
            gold.update({"units": "USD", "currency": "USD"})
        elif fact.question_type == "weekly_chart_position":
            gold["units"] = "chart position"
        record = {
            "schemaVersion": "query-gold/v1",
            "id": fact.case_id,
            "categoryId": CATEGORY_ID,
            "query": fact.query,
            "temporal": temporal,
            "gold": gold,
            "evidence": [
                {
                    "url": fact.url,
                    "title": fact.title,
                    "retrievedAtUTC": retrieved_at,
                    "publishedAt": (
                        fact.title[-5:-1] if fact.scope_kind == "immutable" else fact.scope_value
                    ),
                    "sourceRecordId": fact.source_record_id,
                    "license": "unknown",
                    "rawSha256": digest,
                    "rawPath": rel_path,
                    "excerpt": excerpt,
                }
            ],
            "derivation": {
                "sourceFamily": fact.source_family,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": fact.question_type,
            },
        }
        cases.append(
            QueryGoldCase.model_validate(record).model_dump(mode="json", exclude_none=True)
        )
    _write_sources_note(output_dir, cases)
    return cases


def _write_sources_note(output_dir: Path, cases: list[dict[str, Any]]) -> None:
    source_counts = Counter(case["derivation"]["sourceFamily"] for case in cases)
    note = [
        "# Entertainment and media sources",
        "",
        "## Benchmark fit and construction method",
        "",
        "Questions cover dated domestic opening-weekend records, Billboard Hot 100 chart rows, and AFI Catalog production credits. Explicit collection captures public HTML pages and accepts a fact only when its answer is present in the retrieved page text.",
        "",
        "## Rejection, revision, and source limitations",
        "",
        "A source is rejected if it fails to load, exceeds the byte limit, changes host, or does not contain the seeded answer. Raw response bytes, hashes, retrieval times, and physical request attempts are retained locally. No blanket reuse license is asserted.",
        "",
        "## Concentration and manual review",
        "",
        "The seed set covers three source families. Source concentration is reported below. Direct-search ranking and human sample review have not been established by this collector and remain review items.",
        "",
        "## Public answer-bearing pages and representativeness",
        "",
        "| Source family | Cases |",
        "|---|---:|",
    ]
    note.extend(f"| {family} | {count} |" for family, count in sorted(source_counts.items()))
    note.extend(
        (
            "",
            "The sample emphasizes U.S. theatrical releases, the Billboard Hot 100, and films represented in the AFI Catalog. International box-office markets, other Billboard charts, and credits for titles outside the AFI Catalog are not represented.",
        )
    )
    atomic_write_bytes(
        ensure_safe_path(output_dir / "sources.md"), ("\n".join(note) + "\n").encode("utf-8")
    )
