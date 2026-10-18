"""Curate river-gauge annual peak telemetry from the official USGS Water Data API.

This first source slice covers annual peak discharge and gage height at one
long-running public gauge. Each value is taken from a pinned USGS OGC API
feature; the collector stores the exact response bytes and uses the exact
feature JSON as its answer-bearing excerpt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from query_gold.io import atomic_write_bytes, ensure_safe_path, json_bytes, read_json

CATEGORY_ID = "20_historical_meteorology_disaster_telemetry"
SCHEMA_VERSION = "query-gold/v1"
GENERATOR_VERSION = "historical-meteorology-usgs-peaks/1"
SOURCE_FAMILY = "usgs_annual_peak_streamflow"
UPSTREAM_REVISION = "usgs-water-data-ogcapi-v1"
API_URL = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/peaks/items"
SITE_ID = "USGS-01094400"
SITE_LABEL = "North Nashua River at Fitchburg, Massachusetts"
PARAMETERS = {
    "00060": ("annual peak streamflow discharge", "ft^3/s", "flow"),
    "00065": ("annual peak gage height", "ft", "height"),
}
PUBLIC_STATION_URL = "https://waterdata.usgs.gov/monitoring-location/USGS-01094400/"
MAX_PHYSICAL_REQUESTS = 8
MAX_RETRIES = 1
MAX_SOURCE_BYTES = 8_000_000
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "query-gold-historical-meteorology/1.0 (public USGS data)"
_YEAR = re.compile(r"^\d{4}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _paths(output_dir: Path) -> tuple[Path, Path, Path]:
    root = ensure_safe_path(Path(output_dir))
    raw = ensure_safe_path(root / "raw")
    ensure_safe_path(raw / "peaks")
    return root, raw, ensure_safe_path(raw / "network-attempts.jsonl")


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("invalid USGS request ledger row")
        rows.append(row)
    return rows


def _write_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    atomic_write_bytes(path, content.encode("utf-8"))


def _fetch_parameter(
    output_dir: Path,
    parameter_code: str,
    client: httpx.Client | None,
    ledger: list[dict[str, Any]],
) -> tuple[bytes, str, str]:
    _, raw_dir, ledger_path = _paths(output_dir)
    raw_path = ensure_safe_path(raw_dir / "peaks" / f"{parameter_code}.json")
    meta_path = ensure_safe_path(raw_dir / "peaks" / f"{parameter_code}.metadata.json")
    query_url = f"{API_URL}?" + urlencode(
        {
            "f": "json",
            "monitoring_location_id": SITE_ID,
            "parameter_code": parameter_code,
            "limit": "50000",
        }
    )
    if raw_path.is_file() or meta_path.is_file():
        if not raw_path.is_file() or not meta_path.is_file():
            raise ValueError(f"incomplete pinned USGS source cache for parameter {parameter_code}")
        body = raw_path.read_bytes()
        metadata = read_json(meta_path)
        if (
            not isinstance(metadata, dict)
            or metadata.get("url") != query_url
            or metadata.get("rawSha256") != _sha256(body)
            or not isinstance(metadata.get("retrievedAtUTC"), str)
        ):
            raise ValueError(f"pinned USGS source metadata mismatch for parameter {parameter_code}")
        return body, metadata["retrievedAtUTC"], query_url

    for attempt in range(1, MAX_RETRIES + 2):
        if len(ledger) >= MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("USGS public source request limit reached")
        started = _now_utc()
        entry: dict[str, Any] = {
            "url": query_url,
            "attempt": attempt,
            "startedAtUTC": started,
            "status": None,
            "responseBytes": None,
            "responseSha256": None,
            "errorType": None,
        }
        try:
            if client is None:
                raise RuntimeError("USGS HTTP client was not initialized")
            response = client.get(query_url)
            entry["status"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = _sha256(response.content)
            ledger.append(entry)
            _write_ledger(ledger_path, ledger)
            if response.status_code == 200:
                if len(response.content) > MAX_SOURCE_BYTES:
                    raise ValueError("USGS peak response exceeds the source size limit")
                body = response.content
                body.decode("utf-8", errors="strict")
                atomic_write_bytes(raw_path, body)
                metadata = {
                    "url": query_url,
                    "retrievedAtUTC": started,
                    "rawSha256": _sha256(body),
                    "sourceFamily": SOURCE_FAMILY,
                    "upstreamRevision": UPSTREAM_REVISION,
                }
                atomic_write_bytes(meta_path, json_bytes(metadata))
                return body, started, query_url
            if response.status_code not in _RETRYABLE_STATUS or attempt > MAX_RETRIES:
                raise RuntimeError(f"USGS peak endpoint returned HTTP {response.status_code}")
        except (httpx.HTTPError, OSError) as error:
            if not ledger or ledger[-1].get("startedAtUTC") != started:
                entry["errorType"] = type(error).__name__
                ledger.append(entry)
                _write_ledger(ledger_path, ledger)
            if attempt > MAX_RETRIES:
                raise RuntimeError(f"USGS peak request failed ({type(error).__name__})") from error
        if attempt <= MAX_RETRIES:
            time.sleep(min(2 ** (attempt - 1), 2))
    raise RuntimeError("USGS peak source retrieval did not complete")


def _features(body: bytes, parameter_code: str) -> dict[str, dict[str, Any]]:
    payload: object = json.loads(body.decode("utf-8", errors="strict"))
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise ValueError(f"USGS response for {parameter_code} is not a GeoJSON feature collection")
    by_year: dict[str, dict[str, Any]] = {}
    for feature in payload["features"]:
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            continue
        properties = feature["properties"]
        year = properties.get("water_year")
        value = properties.get("value")
        date = properties.get("time")
        if not isinstance(year, (str, int)) or not _YEAR.fullmatch(str(year)):
            continue
        if not isinstance(date, str) or not _DATE.fullmatch(date):
            continue
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric < 0 or not numeric < float("inf"):
            continue
        if str(properties.get("parameter_code")) != parameter_code:
            continue
        if str(properties.get("monitoring_location_id")) != SITE_ID:
            continue
        qualifiers = properties.get("qualifier")
        if isinstance(qualifiers, list) and "NOTMAXGH" in qualifiers:
            continue
        if str(year) in by_year:
            raise ValueError(
                f"duplicate USGS annual peak row for water year {year}/{parameter_code}"
            )
        by_year[str(year)] = feature
    return by_year


def _format_value(raw: Any) -> str:
    value = str(raw).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError("USGS peak value is not a non-negative decimal")
    return value


def _literal_properties_excerpt(body: bytes, feature: dict[str, Any]) -> str:
    """Return the exact properties object as it appeared in the cached JSON."""
    properties = feature.get("properties")
    if not isinstance(properties, dict) or not isinstance(properties.get("time_series_id"), str):
        raise ValueError("USGS feature lacks a stable time-series identifier")
    text = body.decode("utf-8", errors="strict")
    key = '"time_series_id"'
    key_index = text.find(key)
    while key_index >= 0:
        start = text.rfind("{", 0, key_index + 1)
        if start < 0:
            break
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    excerpt = text[start : index + 1]
                    if json.loads(excerpt) == properties:
                        return excerpt
                    break
        key_index = text.find(key, key_index + len(key))
    raise ValueError("could not locate exact USGS properties bytes in the pinned response")


def _literal_public_excerpt(
    body: bytes, feature: dict[str, Any], *, answer_date: bool = False
) -> str:
    """Return an exact station-page substring containing this peak value or date."""
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("USGS peak feature lacks properties")
    text = body.decode("utf-8", errors="strict")
    value = json.dumps(str(properties["value"]), ensure_ascii=False)
    date = json.dumps(properties["time"], ensure_ascii=False)
    answer_token = date if answer_date else value
    position = text.find(answer_token)
    if position < 0:
        raise ValueError("public USGS station page does not contain the peak answer literal")
    start = max(0, position - 100)
    end = min(len(text), position + len(answer_token) + 100)
    return text[start:end]


def _fetch_public_station_page(
    output_dir: Path,
    client: httpx.Client | None,
    ledger: list[dict[str, Any]],
) -> tuple[bytes, str]:
    _, raw_dir, ledger_path = _paths(output_dir)
    raw_path = ensure_safe_path(raw_dir / "public_station.html")
    meta_path = ensure_safe_path(raw_dir / "public_station.html.metadata.json")
    if raw_path.is_file() or meta_path.is_file():
        if not raw_path.is_file() or not meta_path.is_file():
            raise ValueError("incomplete pinned public USGS station-page cache")
        body = raw_path.read_bytes()
        metadata = read_json(meta_path)
        if (
            not isinstance(metadata, dict)
            or metadata.get("url") != PUBLIC_STATION_URL
            or metadata.get("rawSha256") != _sha256(body)
            or not isinstance(metadata.get("retrievedAtUTC"), str)
        ):
            raise ValueError("pinned USGS public-page metadata mismatch")
        return body, metadata["retrievedAtUTC"]
    if client is None:
        raise RuntimeError("USGS HTTP client was not initialized")
    for attempt in range(1, MAX_RETRIES + 2):
        if len(ledger) >= MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("USGS public source request limit reached")
        started = _now_utc()
        entry: dict[str, Any] = {
            "url": PUBLIC_STATION_URL,
            "attempt": attempt,
            "startedAtUTC": started,
            "status": None,
            "responseBytes": None,
            "responseSha256": None,
            "errorType": None,
        }
        try:
            response = client.get(PUBLIC_STATION_URL)
            entry["status"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = _sha256(response.content)
            ledger.append(entry)
            _write_ledger(ledger_path, ledger)
            if response.status_code == 200:
                body = response.content
                if len(body) > MAX_SOURCE_BYTES:
                    raise ValueError("USGS public station page exceeds the source size limit")
                body.decode("utf-8", errors="strict")
                atomic_write_bytes(raw_path, body)
                atomic_write_bytes(
                    meta_path,
                    json_bytes(
                        {
                            "url": PUBLIC_STATION_URL,
                            "retrievedAtUTC": started,
                            "rawSha256": _sha256(body),
                            "sourceFamily": "usgs_public_monitoring_location_page",
                            "upstreamRevision": UPSTREAM_REVISION,
                        }
                    ),
                )
                return body, started
            if response.status_code not in _RETRYABLE_STATUS or attempt > MAX_RETRIES:
                raise RuntimeError(f"USGS public station page returned HTTP {response.status_code}")
        except (httpx.HTTPError, OSError) as error:
            if not ledger or ledger[-1].get("startedAtUTC") != started:
                entry["errorType"] = type(error).__name__
                ledger.append(entry)
                _write_ledger(ledger_path, ledger)
            if attempt > MAX_RETRIES:
                raise RuntimeError(
                    f"USGS public station page request failed ({type(error).__name__})"
                ) from error
        if attempt <= MAX_RETRIES:
            time.sleep(1)
    raise RuntimeError("USGS public station page retrieval did not complete")


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Collect up to 50 cases from USGS annual peak flow and gage-height records."""
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 50:
        raise ValueError("count must be an integer between 0 and 50")
    if count == 0:
        return []
    root, raw_dir, ledger_path = _paths(Path(output_dir))
    root.mkdir(parents=True, exist_ok=True)
    (raw_dir / "peaks").mkdir(parents=True, exist_ok=True)
    ledger = _read_ledger(ledger_path)
    client: httpx.Client | None = None
    source_records: dict[str, tuple[bytes, str, str]] = {}
    try:
        for parameter_code in PARAMETERS:
            filename = ensure_safe_path(raw_dir / "peaks" / f"{parameter_code}.json")
            if not filename.is_file():
                if client is None:
                    client = httpx.Client(
                        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=8.0),
                        follow_redirects=False,
                        trust_env=False,
                        headers={
                            "User-Agent": USER_AGENT,
                            "Accept": "application/geo+json, application/json",
                        },
                    )
                source_records[parameter_code] = _fetch_parameter(
                    root, parameter_code, client, ledger
                )
            else:
                # _fetch_parameter checks the immutable response and metadata without network I/O.
                source_records[parameter_code] = _fetch_parameter(
                    root,
                    parameter_code,
                    client,
                    ledger,
                )
        parsed = {code: _features(source_records[code][0], code) for code in PARAMETERS}
        if client is None and not ensure_safe_path(raw_dir / "public_station.html").is_file():
            client = httpx.Client(
                timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=8.0),
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            )
        public_page, public_page_retrieved_at = _fetch_public_station_page(root, client, ledger)
        common_years = sorted(
            set.intersection(*(set(rows) for rows in parsed.values())), reverse=True
        )
        if len(common_years) < (count + 1) // 2:
            raise ValueError(
                f"USGS station has only {len(common_years)} complete shared water years; "
                f"{(count + 1) // 2} are required"
            )

        cases: list[dict[str, Any]] = []
        selected_years = common_years[: (count + 1) // 2]
        for year_index, year in enumerate(selected_years):
            for code, (measure, units, suffix) in PARAMETERS.items():
                feature = parsed[code][year]
                props = feature["properties"]
                value = _format_value(props["value"])
                event_date = props["time"]
                raw_body, retrieved_at, url = source_records[code]
                excerpt = _literal_properties_excerpt(raw_body, feature)
                answer = f"{value} {units}"
                case = {
                    "schemaVersion": SCHEMA_VERSION,
                    "id": f"weather-usgs-01094400-wy{year}-{suffix}",
                    "categoryId": CATEGORY_ID,
                    "query": (
                        f"For USGS river gauge {SITE_ID} at {SITE_LABEL}, what {measure} "
                        f"does the official annual peaks record show for water year {year}?"
                    ),
                    "temporal": {
                        "kind": "version",
                        "precision": "version",
                        "version": f"water year {year}",
                    },
                    "gold": {
                        "answer": answer,
                        "value": {"value": value, "waterYear": int(year), "date": event_date},
                        "acceptedAnswers": [value, answer],
                        "units": None,
                    },
                    "evidence": [
                        {
                            "url": url,
                            "title": (
                                f"USGS annual peak record for {SITE_ID}, parameter {code}, "
                                f"water year {year}"
                            ),
                            "retrievedAtUTC": retrieved_at,
                            "sourceRecordId": f"{SITE_ID}/{year}/{code}",
                            "upstreamRevision": UPSTREAM_REVISION,
                            "license": "USGS public water data; reuse terms not asserted",
                            "rawSha256": _sha256(raw_body),
                            "rawPath": f"raw/peaks/{code}.json",
                            "excerpt": excerpt,
                        },
                        {
                            "url": PUBLIC_STATION_URL,
                            "title": (
                                f"USGS Water Data for the Nation: {SITE_LABEL}, water year {year}"
                            ),
                            "retrievedAtUTC": public_page_retrieved_at,
                            "sourceRecordId": f"{SITE_ID}/{year}/{code}",
                            "upstreamRevision": UPSTREAM_REVISION,
                            "license": "USGS public water data; reuse terms not asserted",
                            "rawSha256": _sha256(public_page),
                            "rawPath": "raw/public_station.html",
                            "excerpt": _literal_public_excerpt(public_page, feature),
                        },
                    ],
                    "derivation": {
                        "sourceFamily": SOURCE_FAMILY,
                        "generatorVersion": GENERATOR_VERSION,
                        "questionType": f"annual_peak_{suffix}",
                    },
                }
                cases.append(case)
                if len(cases) >= count:
                    return cases[:count]
                # A third direct question type asks for the observed calendar
                # date of the annual peak flow. It reuses the same literal row,
                # but its answer is a date rather than a measurement value.
                if code == "00060" and year_index < 16 and len(cases) < count:
                    date_case = {
                        "schemaVersion": SCHEMA_VERSION,
                        "id": f"weather-usgs-01094400-wy{year}-flow-date",
                        "categoryId": CATEGORY_ID,
                        "query": (
                            f"For USGS river gauge {SITE_ID} at {SITE_LABEL}, on what calendar "
                            "date "
                            f"was the annual peak streamflow recorded for water year {year}?"
                        ),
                        "temporal": {
                            "kind": "version",
                            "precision": "version",
                            "version": f"water year {year}",
                        },
                        "gold": {
                            "answer": event_date,
                            "value": event_date,
                            "acceptedAnswers": [event_date],
                        },
                        "evidence": [
                            {
                                "url": url,
                                "title": f"USGS annual peak record for {SITE_ID}, parameter 00060",
                                "retrievedAtUTC": retrieved_at,
                                "sourceRecordId": f"{SITE_ID}/{year}/00060",
                                "upstreamRevision": UPSTREAM_REVISION,
                                "license": "USGS public water data; reuse terms not asserted",
                                "rawSha256": _sha256(raw_body),
                                "rawPath": "raw/peaks/00060.json",
                                "excerpt": excerpt,
                            },
                            {
                                "url": PUBLIC_STATION_URL,
                                "title": (
                                    f"USGS Water Data for the Nation: {SITE_LABEL}, "
                                    f"water year {year}"
                                ),
                                "retrievedAtUTC": public_page_retrieved_at,
                                "sourceRecordId": f"{SITE_ID}/{year}/00060",
                                "upstreamRevision": UPSTREAM_REVISION,
                                "license": "USGS public water data; reuse terms not asserted",
                                "rawSha256": _sha256(public_page),
                                "rawPath": "raw/public_station.html",
                                "excerpt": _literal_public_excerpt(
                                    public_page, feature, answer_date=True
                                ),
                            },
                        ],
                        "derivation": {
                            "sourceFamily": SOURCE_FAMILY,
                            "generatorVersion": GENERATOR_VERSION,
                            "questionType": "annual_peak_flow_date",
                        },
                    }
                    cases.append(date_case)
                    if len(cases) >= count:
                        return cases[:count]
        return cases[:count]
    finally:
        if client is not None:
            client.close()


def _write_cases(output_dir: Path, cases: list[dict[str, Any]]) -> Path:
    root, _, _ = _paths(output_dir)
    target = ensure_safe_path(root / "cases.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(case, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for case in cases
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=target.parent,
        prefix=".cases.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(text)
        temp_path = Path(temporary.name)
    ensure_safe_path(temp_path)
    ensure_safe_path(target)
    temp_path.replace(target)
    return target


def _default_output_dir() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return (
        repository_root
        / "results"
        / "query-gold-curation"
        / "eval-v2-v1"
        / "categories"
        / CATEGORY_ID
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--count", type=int, default=50)
    arguments = parser.parse_args(argv)
    try:
        cases = collect(arguments.output_dir, arguments.count)
        target = _write_cases(arguments.output_dir, cases)
    except (OSError, RuntimeError, ValueError, httpx.HTTPError) as error:
        print(f"historical meteorology collection failed: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {len(cases)} historical meteorology cases to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
