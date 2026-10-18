# ruff: noqa: E501
"""Curate municipal restaurant inspection facts from New York City records.

Collection is explicit and bounded. The city data portal exposes the answer
records through its public HTML dataset page and its Socrata-backed records API;
the exact API response bytes are archived so that each grade/score can be
checked literally. The portal page remains the normal public discovery surface.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path, json_bytes
from query_gold.models import QueryGoldCase

CATEGORY_ID = "17_local_graph_municipal_pois_directory_lookups"
GENERATOR_VERSION = "municipal-directory-curator/1.0"
DATASET_ID = "43nn-pn8j"
API_ROOT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"
PORTAL_URL = f"https://data.cityofnewyork.us/Health/Restaurant-Inspection-Results/{DATASET_ID}"
MAX_PHYSICAL_REQUESTS = 4
MAX_RETRIES = 1
MAX_SOURCE_BYTES = 10_000_000
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "query-gold-municipal-directory/1.0 (official public sources)"


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_raw(output_dir: Path, name: str) -> Path:
    if "/" in name or ".." in name or name.startswith("."):
        raise ValueError("unsafe municipal source cache filename")
    return ensure_safe_path(output_dir / "raw" / name)


def _fetch(output_dir: Path, ledger: list[dict[str, Any]], url: str) -> tuple[bytes, str, str]:
    name = f"nyc-inspections-{hashlib.sha256(url.encode()).hexdigest()[:20]}.json"
    raw_path = _safe_raw(output_dir, name)
    meta_path = _safe_raw(output_dir, f"{name}.metadata.json")
    if raw_path.is_file() and meta_path.is_file():
        raw = raw_path.read_bytes()
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if metadata.get("url") != url or metadata.get("rawSha256") != _sha256(raw):
            raise ValueError("cached NYC source metadata does not match archived bytes")
        retrieved = metadata.get("retrievedAtUTC")
        if not isinstance(retrieved, str):
            raise ValueError("cached NYC source has no retrieval timestamp")
        return raw, retrieved, f"raw/{name}"

    for attempt in range(1, MAX_RETRIES + 2):
        if len(ledger) >= MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("municipal source request limit reached")
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
            response = httpx.get(
                url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            entry["status"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = _sha256(response.content)
            ledger.append(entry)
            atomic_write_jsonl(_safe_raw(output_dir, "network-attempts.jsonl"), ledger)
            if response.status_code == 200:
                if (
                    len(response.content) > MAX_SOURCE_BYTES
                    or response.url.host != "data.cityofnewyork.us"
                ):
                    raise ValueError("NYC response exceeded size or host constraints")
                response.content.decode("utf-8", errors="strict")
                atomic_write_bytes(raw_path, response.content)
                atomic_write_bytes(
                    meta_path,
                    json_bytes(
                        {
                            "url": url,
                            "rawSha256": _sha256(response.content),
                            "retrievedAtUTC": _now_utc(),
                        }
                    ),
                )
                return response.content, _now_utc(), f"raw/{name}"
            if attempt > MAX_RETRIES or response.status_code not in {
                408,
                425,
                429,
                500,
                502,
                503,
                504,
            }:
                raise RuntimeError(f"NYC inspection source returned HTTP {response.status_code}")
        except httpx.RequestError as error:
            entry["errorType"] = type(error).__name__
            ledger.append(entry)
            atomic_write_jsonl(_safe_raw(output_dir, "network-attempts.jsonl"), ledger)
            if attempt > MAX_RETRIES:
                raise RuntimeError("NYC inspection source failed after one retry") from None
    raise RuntimeError("NYC inspection source failed")


def _query_url(count: int) -> str:
    # Pick one latest non-null inspection row per establishment, then retain
    # only rows with an official letter grade and score.
    params = {
        "$select": (
            " camis,dba,boro,building,street,zipcode,inspection_date,score,grade,grade_date "
        ),
        "$where": "score IS NOT NULL AND grade IS NOT NULL AND inspection_date IS NOT NULL",
        "$order": "inspection_date DESC, camis ASC",
        "$limit": str(min(5000, max(500, count * 100))),
    }
    return f"{API_ROOT}?{urlencode(params)}"


def _record_query(row: dict[str, Any], question_type: str) -> tuple[str, str, str]:
    name = str(row["dba"]).strip()
    boro = str(row.get("boro", "")).strip()
    location = " ".join(
        str(row.get(key, "")).strip()
        for key in ("building", "street", "boro", "zipcode")
        if row.get(key)
    )
    street = " ".join(str(row.get("street", "")).split())
    day = str(row["inspection_date"])[:10]
    score = str(row["score"]).strip()
    grade = str(row["grade"]).strip()
    if question_type == "restaurant_inspection_grade":
        return (
            f"What letter grade did {name} at {location} receive in its New York City "
            f"restaurant inspection on {day}?",
            grade,
            "",
        )
    if question_type == "municipal_business_address":
        return (
            f"What street name does New York City's restaurant inspection record list "
            f"for {name} in {boro} on {day}?",
            street,
            "",
        )
    return (
        f"What inspection score did {name} at {location} receive in its New York City "
        f"restaurant inspection on {day}?",
        score,
        "",
    )


def _build_case(
    row: dict[str, Any],
    *,
    question_type: str,
    source_url: str,
    raw_digest: str,
    raw_path: str,
    retrieved: str,
    excerpt: str,
) -> dict[str, Any]:
    from query_gold.models import Derivation, Evidence, GoldAnswer, TemporalScope

    camis = str(row["camis"])
    day = str(row["inspection_date"])[:10]
    score = str(row["score"]).strip()
    query, answer, _units = _record_query(row, question_type)
    entry = QueryGoldCase(
        schemaVersion="query-gold/v1",
        id=f"municipal-nyc-inspection-{camis}-{day}",
        categoryId=CATEGORY_ID,  # type: ignore[arg-type]
        query=query,
        temporal=TemporalScope(kind="event", precision="day", date=day),
        gold=GoldAnswer(
            answer=answer,
            acceptedAnswers=[],
            value=int(score) if question_type == "restaurant_inspection_score" else None,
            units=None,
        ),
        evidence=[
            Evidence(
                url=source_url,
                title="NYC Restaurant Inspection Results",
                retrievedAtUTC=retrieved,
                effectiveDate=day,
                sourceRecordId=f"nyc-restaurant-camis-{camis}-{day}",
                rawSha256=raw_digest,
                rawPath=raw_path,
                excerpt=excerpt,
            )
        ],
        derivation=Derivation(
            sourceFamily="municipal_health_inspection_registry",
            generatorVersion=GENERATOR_VERSION,
            questionType=question_type,
        ),
    )
    return entry.model_dump(mode="json", exclude_none=True)


def _notes(cases: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> str:
    return "\n".join(
        (
            "# Local graph, municipal POIs & directory source notes",
            "",
            "## Benchmark fit and construction",
            "",
            "Cases ask for a named New York City food establishment's inspection score, letter grade, "
            "or street address "
            "on the exact inspection date. Records come from the official NYC Restaurant Inspection "
            "Results dataset (Socrata dataset 43nn-pn8j); response bytes and excerpts are archived.",
            "Only rows with a business name, CAMIS identifier, inspection date, numeric score, and "
            "letter grade are admitted. One record per establishment/date is retained.",
            "",
            "## Collection and review",
            "",
            f"Collected {len(cases)} cases in {len(attempts)} physical request attempt(s). Automated "
            "row and literal-excerpt checks run during collection. Human review of direct-search "
            "discoverability has not been performed.",
            "Evidence URLs point to the official NYC Open Data HTML dataset portal. Its metadata "
            "says the portal dataset and the Health Department restaurant grading site use the "
            "same source; the interactive table is the public answer-bearing surface. The exact "
            "excerpts archived here come from the dataset's JSON records API, not captured HTML. "
            "A static HTML fetch did not establish that every row field is rendered in page source; "
            "users may need to interact with the table or follow its data view.",
            "",
            "## Rejection criteria and limits",
            "",
            "Rows lacking a stable business identifier, exact inspection date, score, grade, or literal "
            "source representation are rejected. This dataset covers NYC restaurant inspections only; "
            "municipal licenses, registrations, corporate addresses, other cities, and other POIs are "
            "not represented. Historical scores may not describe present conditions.",
            "",
            "## License and snapshot policy",
            "",
            "The public data portal is cited; no additional license assertion is made. Raw API "
            "bytes are SHA-256 pinned with retrieval metadata. Refresh requires an explicit call.",
            "",
            "## Normal public answer-bearing source",
            "",
            f"NYC Restaurant Inspection Results: <{PORTAL_URL}>. The portal describes the "
            "municipal inspection dataset and links its interactive data view.",
            "",
            "## Evidence quality note",
            "",
            "The official HTML portal is the direct-search discovery page, but this collector stores "
            "API response bytes as the literal row excerpt and does not archive page HTML containing "
            "the answer. Under the contract's strict answer-bearing HTML/PDF rule, these records need "
            "a captured row-level portal/PDF excerpt before they can be called fully conformant.",
            "",
        )
    )


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Fetch official NYC inspection records and return up to 50 canonical cases."""
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 50:
        raise ValueError("count must be between 1 and 50")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_safe_path(output_dir, require_existing=True)
    ledger_path = _safe_raw(output_dir, "network-attempts.jsonl")
    ledger = []
    if ledger_path.is_file():
        ledger = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    url = _query_url(count)
    raw, retrieved, raw_path = _fetch(output_dir, ledger, url)
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError("NYC dataset response was not a JSON array")
    seen: set[tuple[str, str]] = set()
    cases: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict) or not all(
            row.get(key) for key in ("camis", "dba", "inspection_date", "score", "grade")
        ):
            continue
        if " and " in f" {str(row.get('dba', '')).casefold()} ":
            continue
        day = str(row["inspection_date"])[:10]
        key = (str(row["camis"]), day)
        if key in seen:
            continue
        seen.add(key)
        literal = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        if literal not in raw.decode("utf-8"):
            continue
        question_type = (
            "restaurant_inspection_score",
            "restaurant_inspection_grade",
            "municipal_business_street",
        )[len(cases) % 3]
        cases.append(
            _build_case(
                row,
                question_type=question_type,
                source_url=PORTAL_URL,
                raw_digest=_sha256(raw),
                raw_path=raw_path,
                retrieved=retrieved,
                excerpt=literal,
            )
        )
        if len(cases) == count:
            break
    if len(cases) != count:
        raise ValueError(
            f"NYC source yielded {len(cases)} valid unique inspection cases; needed {count}"
        )
    if count == 50 and (
        len({c["evidence"][0]["sourceRecordId"] for c in cases}) < 25
        or len({c["derivation"]["questionType"] for c in cases}) < 3
    ):
        raise ValueError("municipal cases do not meet source-record and question-type gates")
    atomic_write_jsonl(ensure_safe_path(output_dir / "cases.jsonl"), cases)
    atomic_write_bytes(
        ensure_safe_path(output_dir / "sources.md"), _notes(cases, ledger).encode("utf-8")
    )
    return cases
