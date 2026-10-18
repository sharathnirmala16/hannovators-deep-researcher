"""Collect NOAA GHCN-Daily precipitation cases into separate eval-v2 files.

This is a second, independent meteorology collector. It reads NOAA NCEI's
station CSVs and writes only a new question JSONL and answer JSONL beside the
existing eval-v2 exports; it never writes into the canonical query-gold tree.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

_NCEI_CSV = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{station}.csv"
_START_YEAR = 2015
_REQUEST_TIMEOUT = 25.0
_MAX_RESPONSE_BYTES = 20_000_000
_MAX_PHYSICAL_REQUESTS = 10
_MAX_RETRIES = 1
_RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}
_USER_AGENT = "provider-evals-historical-meteorology-noaa/1.0 (public NOAA NCEI data)"


@dataclass(frozen=True)
class Station:
    ghcn_id: str
    name: str


STATIONS = (
    Station("USW00094728", "New York City Central Park"),
    Station("USW00023174", "Los Angeles International Airport"),
    Station("USW00012921", "Houston Hobby Airport"),
    Station("USW00013874", "Atlanta Hartsfield-Jackson Airport"),
    Station("USW00014732", "Boston Logan Airport"),
)


def _request_csv(client: httpx.Client, station: Station) -> tuple[str, bytes, int]:
    url = _NCEI_CSV.format(station=station.ghcn_id)
    last_error = "request failed"
    for attempt in range(1, _MAX_RETRIES + 2):
        try:
            response = client.get(url)
            if response.status_code == 200:
                if len(response.content) > _MAX_RESPONSE_BYTES:
                    raise ValueError(f"NOAA response for {station.ghcn_id} exceeds the byte limit")
                response.content.decode("utf-8-sig", errors="strict")
                return url, response.content, attempt
            last_error = f"HTTP {response.status_code}"
            if response.status_code not in _RETRYABLE_STATUSES or attempt > _MAX_RETRIES:
                break
        except (httpx.HTTPError, OSError, UnicodeError) as error:
            last_error = type(error).__name__
            if attempt > _MAX_RETRIES:
                break
        if attempt <= _MAX_RETRIES:
            time.sleep(0.25 * attempt)
    raise RuntimeError(f"NOAA station data request failed for {station.ghcn_id} ({last_error})")


def _precipitation_rows(body: bytes, station: Station) -> list[tuple[str, int]]:
    text = body.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    required = {"STATION", "DATE", "NAME", "PRCP", "PRCP_ATTRIBUTES"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError(f"NOAA CSV for {station.ghcn_id} has an unexpected schema")

    rows: list[tuple[str, int]] = []
    for row in reader:
        if row.get("STATION") != station.ghcn_id:
            continue
        date = row.get("DATE", "").strip()
        raw = row.get("PRCP", "").strip()
        if len(date) != 10 or date[4] != "-" or date[7] != "-":
            continue
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            continue
        if parsed_date.year < _START_YEAR:
            continue
        # NOAA's PRCP attributes are M,Q,S; ignore trace amounts and quality-
        # flagged readings while retaining the source flag for normal records.
        attributes = row.get("PRCP_ATTRIBUTES", "").split(",")
        measurement_flag = attributes[0].strip() if attributes else ""
        quality_flag = attributes[1].strip() if len(attributes) > 1 else ""
        if quality_flag or measurement_flag == "T":
            continue
        if not raw.isdigit():
            continue
        tenths_mm = int(raw)
        if tenths_mm < 0:
            continue
        rows.append((date, tenths_mm))
    return rows


def _select_cases(client: httpx.Client) -> list[dict[str, Any]]:
    candidates: list[tuple[Station, str, int, str]] = []
    physical_requests = 0
    for station in STATIONS:
        if physical_requests >= _MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("NOAA request budget exceeded")
        url, body, attempts = _request_csv(client, station)
        physical_requests += attempts
        for date, tenths_mm in _precipitation_rows(body, station):
            candidates.append((station, date, tenths_mm, url))

    selected: list[tuple[Station, str, int, str]] = []
    for station in STATIONS:
        station_rows = sorted(
            (row for row in candidates if row[0] == station and row[2] > 0),
            key=lambda row: row[1],
        )
        if len(station_rows) < 10:
            raise RuntimeError(
                f"NOAA returned fewer than 10 usable precipitation records for {station.ghcn_id}"
            )
        # Spread the ten samples across the available record instead of taking
        # adjacent storm days from one event.
        last_index = len(station_rows) - 1
        chosen_indices = [round(index * last_index / 9) for index in range(10)]
        selected.extend(station_rows[index] for index in chosen_indices)

    cases: list[dict[str, Any]] = []
    for station, date, tenths_mm, url in selected:
        amount = tenths_mm / 10
        answer = f"{amount:.1f} mm"
        cases.append(
            {
                "id": f"weather-noaa-ghcn-{station.ghcn_id.lower()}-{date}-prcp",
                "prompt": (
                    f"According to NOAA's daily climate record, what precipitation amount "
                    f"did the {station.name} station (GHCN-Daily ID {station.ghcn_id}) "
                    f"record on {date}? Give the amount in millimeters."
                ),
                "answer": answer,
                "goldUrls": [url],
            }
        )
    return cases


def _write_new_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    with path.open("x", encoding="utf-8", newline="") as output:
        output.write(payload)
        output.flush()


def collect_and_write(repository_root: Path) -> tuple[Path, Path, int]:
    questions_path = (
        repository_root / "benchmarks/eval_v2/questions/historical_meteorology_noaa.jsonl"
    )
    answers_path = (
        repository_root / "benchmarks/eval_v2/answers/historical_meteorology_noaa_answers.jsonl"
    )
    if questions_path.exists() or answers_path.exists():
        raise FileExistsError(
            "NOAA meteorology output already exists; refusing to overwrite either file"
        )

    with httpx.Client(
        timeout=httpx.Timeout(_REQUEST_TIMEOUT, connect=10.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/csv"},
    ) as client:
        cases = _select_cases(client)

    if len(cases) != 50:
        raise ValueError(f"Expected 50 NOAA questions, collected {len(cases)}")
    questions = [{"id": row["id"], "prompt": row["prompt"]} for row in cases]
    answers = [
        {
            "id": row["id"],
            "prompt": row["prompt"],
            "answer": row["answer"],
            "goldUrls": row["goldUrls"],
        }
        for row in cases
    ]

    # Exclusive create protects the existing combined eval-v2 files and any
    # prior run of this independent dataset. Roll back only a file created here
    # if writing its matching pair fails.
    created_questions = False
    try:
        _write_new_jsonl(questions_path, questions)
        created_questions = True
        _write_new_jsonl(answers_path, answers)
    except OSError:
        if created_questions:
            questions_path.unlink(missing_ok=True)
        raise
    return questions_path, answers_path, len(cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    arguments = parser.parse_args(argv)
    try:
        questions, answers, count = collect_and_write(arguments.repository_root)
    except (OSError, RuntimeError, ValueError, httpx.HTTPError) as error:
        print(f"NOAA historical meteorology collection failed: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {count} NOAA meteorology questions to {questions}")
    print(f"Wrote {count} answers to {answers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
