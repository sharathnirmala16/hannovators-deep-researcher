"""Version-pinned API and CLI facts for the code/documentation category.

The collector uses a small curated set of official release files. Answers for
signatures, declared defaults, and options are extracted from the cached bytes;
release-note answers are admitted only when their supporting wording occurs in
the cited paragraph. It never executes package code or calls a model.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from query_gold.categories.code_api_helpers import (
    append_attempt_event,
    click_command_default,
    count_started_attempts,
    long_option,
    manifest_entry,
    open_without_redirects,
    release_section_excerpt,
    section_option_excerpt,
    timestamp_utc,
)
from query_gold.categories.code_api_paths import guard_absolute_path, safe_file
from query_gold.io import atomic_write_bytes, json_bytes, read_json
from query_gold.models import SCHEMA_VERSION, QueryGoldCase

CATEGORY_ID = "03_code_api_documentation"
GENERATOR_VERSION = "query-gold/v1"
MAX_PHYSICAL_REQUESTS = 150
REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 1
MAX_SOURCE_BYTES = 2_000_000
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MISSING = object()


@dataclass(frozen=True)
class Project:
    repo: str
    key: str
    tag: str
    revision: str
    display_name: str
    license_file: str


PROJECTS: dict[str, Project] = {
    "python/cpython": Project(
        repo="python/cpython",
        key="cpython",
        tag="v3.12.10",
        revision="0cc81280367df838c4b199f8f0378837165071c2",
        display_name="CPython",
        license_file="LICENSE",
    ),
    "pandas-dev/pandas": Project(
        repo="pandas-dev/pandas",
        key="pandas",
        tag="v2.2.3",
        revision="0691c5cf90477d3503834d983f69350f250a6ff7",
        display_name="pandas",
        license_file="LICENSE",
    ),
    "pallets/click": Project(
        repo="pallets/click",
        key="click",
        tag="8.1.7",
        revision="874ca2bc1c30d93a4ac6e36a15ed685eafe89097",
        display_name="Click",
        license_file="LICENSE.rst",
    ),
}


SOURCE_PATHS: dict[str, tuple[str, str]] = {
    "py_os": ("python/cpython", "Doc/library/os.rst"),
    "py_re": ("python/cpython", "Doc/library/re.rst"),
    "py_json": ("python/cpython", "Doc/library/json.rst"),
    "py_pathlib": ("python/cpython", "Doc/library/pathlib.rst"),
    "py_csv": ("python/cpython", "Doc/library/csv.rst"),
    "py_subprocess": ("python/cpython", "Doc/library/subprocess.rst"),
    "py_shutil": ("python/cpython", "Doc/library/shutil.rst"),
    "py_tempfile": ("python/cpython", "Doc/library/tempfile.rst"),
    "py_datetime": ("python/cpython", "Doc/library/datetime.rst"),
    "py_itertools": ("python/cpython", "Doc/library/itertools.rst"),
    "py_collections": ("python/cpython", "Doc/library/collections.rst"),
    "py_contextlib": ("python/cpython", "Doc/library/contextlib.rst"),
    "py_changes": ("python/cpython", "Doc/whatsnew/3.12.rst"),
    "pd_frame": ("pandas-dev/pandas", "pandas/core/frame.py"),
    "pd_series": ("pandas-dev/pandas", "pandas/core/series.py"),
    "pd_groupby": ("pandas-dev/pandas", "pandas/core/groupby/generic.py"),
    "pd_concat": ("pandas-dev/pandas", "pandas/core/reshape/concat.py"),
    "pd_readers": ("pandas-dev/pandas", "pandas/io/parsers/readers.py"),
    "pd_json": ("pandas-dev/pandas", "pandas/io/json/_json.py"),
    "pd_changes": ("pandas-dev/pandas", "doc/source/whatsnew/v2.2.0.rst"),
    "click_options": ("pallets/click", "docs/options.rst"),
    "click_commands": ("pallets/click", "docs/commands.rst"),
    "click_parameters": ("pallets/click", "docs/parameters.rst"),
    "click_core": ("pallets/click", "src/click/core.py"),
    "click_changes": ("pallets/click", "CHANGES.rst"),
}


@dataclass(frozen=True)
class FactSpec:
    """A question and extraction location; derived answers are not stored here."""

    id: str
    source: str
    question_type: str
    query: str
    extractor: str
    target: str
    parameter: str | None = None
    answer: str | None = None
    support: tuple[str, ...] = ()
    units: str | None = None
    version: str | None = None
    section: str | None = None


# Keep one independently valid JSON object per seed so separators cannot break the data.
_FACT_SPEC_JSON_ROWS: tuple[str, ...] = (
    '{"id":"code_api_py_os_makedirs_signature","source":"py_os","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `os.makedirs`?","extractor":"rst_signature","target":"makedirs"}',  # noqa: E501
    '{"id":"code_api_py_os_listdir_path_default","source":"py_os","question_type":"parameter_default","query":"What default expression does CPython 3.12.10 document for `os.listdir`\'s `path`?","extractor":"rst_default","target":"listdir","parameter":"path"}',  # noqa: E501
    '{"id":"code_api_py_re_sub_signature","source":"py_re","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `re.sub`?","extractor":"rst_signature","target":"sub"}',  # noqa: E501
    '{"id":"code_api_py_re_findall_flags_default","source":"py_re","question_type":"parameter_default","query":"What default expression does CPython 3.12.10 document for `re.findall.flags`?","extractor":"rst_default","target":"findall","parameter":"flags"}',  # noqa: E501
    '{"id":"code_api_py_json_loads_signature","source":"py_json","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `json.loads`?","extractor":"rst_signature","target":"loads"}',  # noqa: E501
    '{"id":"code_api_py_json_decoder_strict_default","source":"py_json","question_type":"parameter_default","query":"What default does CPython 3.12.10 declare for `json.JSONDecoder.strict`?","extractor":"rst_default","target":"JSONDecoder","parameter":"strict"}',  # noqa: E501
    '{"id":"code_api_py_pathlib_glob_signature","source":"py_pathlib","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `pathlib.Path.glob`?","extractor":"rst_signature","target":"Path.glob"}',  # noqa: E501
    '{"id":"code_api_py_pathlib_resolve_strict_default","source":"py_pathlib","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `pathlib.Path.resolve.strict`?","extractor":"rst_default","target":"Path.resolve","parameter":"strict"}',  # noqa: E501
    '{"id":"code_api_py_csv_reader_signature","source":"py_csv","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `csv.reader`?","extractor":"rst_signature","target":"reader"}',  # noqa: E501
    '{"id":"code_api_py_csv_writer_dialect_default","source":"py_csv","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `csv.writer.dialect`?","extractor":"rst_default","target":"writer","parameter":"dialect"}',  # noqa: E501
    '{"id":"code_api_py_subprocess_getstatusoutput_signature","source":"py_subprocess","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `subprocess.getstatusoutput`?","extractor":"rst_signature","target":"getstatusoutput"}',  # noqa: E501
    '{"id":"code_api_py_subprocess_wait_timeout_default","source":"py_subprocess","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `subprocess.Popen.wait.timeout`?","extractor":"rst_default","target":"Popen.wait","parameter":"timeout"}',  # noqa: E501
    '{"id":"code_api_py_shutil_copyfile_signature","source":"py_shutil","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `shutil.copyfile`?","extractor":"rst_signature","target":"copyfile"}',  # noqa: E501
    '{"id":"code_api_py_shutil_which_path_default","source":"py_shutil","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `shutil.which.path`?","extractor":"rst_default","target":"which","parameter":"path"}',  # noqa: E501
    '{"id":"code_api_py_tempfile_mkstemp_signature","source":"py_tempfile","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `tempfile.mkstemp`?","extractor":"rst_signature","target":"mkstemp"}',  # noqa: E501
    '{"id":"code_api_py_tempfile_temporarydirectory_delete_default","source":"py_tempfile","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `tempfile.TemporaryDirectory.delete`?","extractor":"rst_default","target":"TemporaryDirectory","parameter":"delete"}',  # noqa: E501
    '{"id":"code_api_py_datetime_now_signature","source":"py_datetime","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `datetime.datetime.now`?","extractor":"rst_signature","target":"datetime.now"}',  # noqa: E501
    '{"id":"code_api_py_datetime_isoformat_timespec_default","source":"py_datetime","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `datetime.isoformat.timespec`?","extractor":"rst_default","target":"datetime.isoformat","parameter":"timespec"}',  # noqa: E501
    '{"id":"code_api_py_itertools_product_signature","source":"py_itertools","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `itertools.product`?","extractor":"rst_signature","target":"product"}',  # noqa: E501
    '{"id":"code_api_py_itertools_tee_n_default","source":"py_itertools","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `itertools.tee.n`?","extractor":"rst_default","target":"tee","parameter":"n"}',  # noqa: E501
    '{"id":"code_api_py_collections_namedtuple_signature","source":"py_collections","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `collections.namedtuple`?","extractor":"rst_signature","target":"namedtuple"}',  # noqa: E501
    '{"id":"code_api_py_collections_defaultdict_factory_default","source":"py_collections","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `collections.defaultdict.default_factory`?","extractor":"rst_default","target":"defaultdict","parameter":"default_factory"}',  # noqa: E501
    '{"id":"code_api_py_contextlib_suppress_signature","source":"py_contextlib","question_type":"api_signature","query":"What signature does CPython 3.12.10 document for `contextlib.suppress`?","extractor":"rst_signature","target":"suppress"}',  # noqa: E501
    '{"id":"code_api_py_contextlib_nullcontext_result_default","source":"py_contextlib","question_type":"parameter_default","query":"What default does CPython 3.12.10 document for `contextlib.nullcontext.enter_result`?","extractor":"rst_default","target":"nullcontext","parameter":"enter_result"}',  # noqa: E501
    '{"id":"code_api_py_boolean_optional_action_deprecation","source":"py_changes","question_type":"deprecation","query":"Which three parameter names does CPython 3.12.10 mark deprecated for `argparse.BooleanOptionalAction`?","extractor":"paragraph_literal","target":"BooleanOptionalAction","answer":"type, choices, and metavar","support":["BooleanOptionalAction","type","choices","metavar","deprecated","3.14"]}',  # noqa: E501
    '{"id":"code_api_py_shutil_onerror_deprecation","source":"py_changes","question_type":"deprecation","query":"Which error callback parameter does CPython 3.12.10 mark deprecated for `shutil.rmtree`?","extractor":"paragraph_literal","target":":func:`shutil.rmtree` now accepts a new argument *onexc*","answer":"onerror","support":["shutil.rmtree","onexc","onerror","deprecated"]}',  # noqa: E501
    '{"id":"code_api_pd_frame_groupby_dropna_default","source":"pd_frame","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `DataFrame.groupby.dropna`?","extractor":"python_default","target":"DataFrame.groupby","parameter":"dropna"}',  # noqa: E501
    '{"id":"code_api_pd_frame_merge_how_default","source":"pd_frame","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `DataFrame.merge.how`?","extractor":"python_default","target":"DataFrame.merge","parameter":"how"}',  # noqa: E501
    '{"id":"code_api_pd_series_sort_na_position_default","source":"pd_series","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `Series.sort_values.na_position`?","extractor":"python_default","target":"Series.sort_values","parameter":"na_position"}',  # noqa: E501
    '{"id":"code_api_pd_series_dropna_how_default","source":"pd_series","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `Series.dropna.how`?","extractor":"python_default","target":"Series.dropna","parameter":"how"}',  # noqa: E501
    '{"id":"code_api_pd_groupby_value_counts_normalize_default","source":"pd_groupby","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `SeriesGroupBy.value_counts.normalize`?","extractor":"python_default","target":"SeriesGroupBy.value_counts","parameter":"normalize"}',  # noqa: E501
    '{"id":"code_api_pd_groupby_fillna_inplace_default","source":"pd_groupby","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `DataFrameGroupBy.fillna.inplace`?","extractor":"python_default","target":"DataFrameGroupBy.fillna","parameter":"inplace"}',  # noqa: E501
    '{"id":"code_api_pd_concat_axis_default","source":"pd_concat","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `concat.axis`?","extractor":"python_default","target":"concat","parameter":"axis"}',  # noqa: E501
    '{"id":"code_api_pd_concat_join_default","source":"pd_concat","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `concat.join`?","extractor":"python_default","target":"concat","parameter":"join"}',  # noqa: E501
    '{"id":"code_api_pd_read_csv_quotechar_default","source":"pd_readers","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `read_csv.quotechar`?","extractor":"python_default","target":"read_csv","parameter":"quotechar"}',  # noqa: E501
    '{"id":"code_api_pd_read_csv_bad_lines_default","source":"pd_readers","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `read_csv.on_bad_lines`?","extractor":"python_default","target":"read_csv","parameter":"on_bad_lines"}',  # noqa: E501
    '{"id":"code_api_pd_to_json_date_format_default","source":"pd_json","question_type":"parameter_default","query":"What default expression does pandas 2.2.3\'s internal `pandas.io.json._json.to_json` helper declare for `date_format`?","extractor":"python_default","target":"to_json","parameter":"date_format"}',  # noqa: E501
    '{"id":"code_api_pd_read_json_lines_default","source":"pd_json","question_type":"parameter_default","query":"What default does pandas 2.2.3 declare for `read_json.lines`?","extractor":"python_default","target":"read_json","parameter":"lines"}',  # noqa: E501
    '{"id":"code_api_pd_types_deprecation","source":"pd_changes","question_type":"deprecation","query":"What replacement expression do pandas 2.2.0 notes give for `pandas.api.types.is_interval`?","extractor":"line_literal","target":"pandas.api.types.is_interval","answer":"isinstance(obj, pd.Interval)","support":["pandas.api.types.is_interval","isinstance(obj, pd.Interval)","Deprecated"],"version":"2.2.0"}',  # noqa: E501
    '{"id":"code_api_pd_groupby_fillna_deprecation_replacements","source":"pd_changes","question_type":"deprecation","query":"Which forward-fill method replaces deprecated `DataFrameGroupBy.fillna` in pandas 2.2.0?","extractor":"line_literal","target":".DataFrameGroupBy.ffill","answer":"DataFrameGroupBy.ffill","support":["DataFrameGroupBy.fillna","DataFrameGroupBy.ffill","forward and backward","Deprecated"],"version":"2.2.0"}',  # noqa: E501
    '{"id":"code_api_click_count_flag","source":"click_options","question_type":"cli_option","query":"In Click 8.1.7\'s `Counting` example, which long flag is declared with `count=True`?","extractor":"click_section_option","target":"@click.option(\'-v\', \'--verbose\', count=True)","section":"Counting"}',  # noqa: E501
    '{"id":"code_api_click_repeated_value_flag","source":"click_options","question_type":"cli_option","query":"In Click 8.1.7\'s `Multiple Options` example, which long flag is declared with `multiple=True`?","extractor":"click_section_option","target":"@click.option(\'--message\', \'-m\', multiple=True)","section":"Multiple Options"}',  # noqa: E501
    '{"id":"code_api_click_file_input_long_flag","source":"click_commands","question_type":"cli_option","query":"In Click 8.1.7\'s `Multi Command Pipelines` example using `click.File(\'r\')`, which long flag is paired with `-i`?","extractor":"click_section_option","target":"@click.option(\'-i\', \'--input\', type=click.File(\'r\'))","section":"Multi Command Pipelines"}',  # noqa: E501
    '{"id":"code_api_click_runserver_port_default","source":"click_commands","question_type":"parameter_default","query":"What default does the Click 8.1.7 `runserver` example declare for its `--port` option?","extractor":"click_command_default","target":"runserver","parameter":"--port","units":"TCP port"}',  # noqa: E501
    '{"id":"code_api_click_environment_value_source","source":"click_parameters","question_type":"cli_semantics","query":"Which parameter values can Click 8.1.7 pull from environment variables, unlike argument values?","extractor":"line_literal","target":"option values can be pulled from environment variables","answer":"option values","support":["option values can be pulled from environment variables","arguments can not"]}',  # noqa: E501
    '{"id":"code_api_click_parameter_option_arity","source":"click_parameters","question_type":"cli_semantics","query":"How many arguments may a Click 8.1.7 option accept by default?","extractor":"paragraph_literal","target":"defaults to 1","answer":"1","support":["fixed number","defaults to 1","multiple times"],"units":"arguments per option occurrence"}',  # noqa: E501
    '{"id":"code_api_click_context_default_map_default","source":"click_core","question_type":"parameter_default","query":"What default does Click 8.1.7 declare for `click.core.Context.default_map`?","extractor":"python_default","target":"Context.__init__","parameter":"default_map"}',  # noqa: E501
    '{"id":"code_api_click_command_deprecated_default","source":"click_core","question_type":"parameter_default","query":"What default does Click 8.1.7 declare for `click.core.Command.deprecated`?","extractor":"python_default","target":"Command.__init__","parameter":"deprecated"}',  # noqa: E501
    '{"id":"code_api_click_bash_detection_change","source":"click_changes","question_type":"release_change","query":"Which error-handling behavior does Click 8.1.7\'s changelog specify for Bash version detection issues?","extractor":"release_section_literal","target":"Bash version detection issues a warning","answer":"a warning instead of an error","support":["Bash version detection","warning","error"],"version":"8.1.7"}',  # noqa: E501
    '{"id":"code_api_click_fish_completion_change","source":"click_changes","question_type":"release_change","query":"Which shell does the Click changelog\'s `Version 8.1.7` completion-script fix name?","extractor":"release_section_literal","target":"Fix issue with completion script for Fish shell.","answer":"Fish","support":["completion script","Fish shell"],"version":"8.1.7"}',  # noqa: E501
)

FACT_SPECS: tuple[FactSpec, ...] = tuple(
    FactSpec(**{**row, "support": tuple(row.get("support", ()))})
    for row in (json.loads(row_json) for row_json in _FACT_SPEC_JSON_ROWS)
)


def _source_id(alias: str) -> str:
    try:
        repo, source_path = SOURCE_PATHS[alias]
    except KeyError as error:
        raise ValueError(f"unknown source alias: {alias}") from error
    return f"{repo}:{source_path}"


def _source_components(source_id: str) -> tuple[Project, str, str, str]:
    try:
        repo, source_path = source_id.split(":", maxsplit=1)
        project = PROJECTS[repo]
    except (ValueError, KeyError) as error:
        raise ValueError("sourceRecordId is not in the pinned source allowlist") from error
    raw_path = f"raw/{project.key}/{source_path}"
    url = f"https://github.com/{repo}/blob/{project.revision}/{source_path}"
    return project, source_path, raw_path, url


def _fetch_pinned_source(
    source_id: str,
    *,
    request_count: list[int],
    manifest: dict[str, Any],
    manifest_path: Path,
    root: Path,
) -> dict[str, Any]:
    project, source_path, raw_path, _ = _source_components(source_id)
    _, _, _, url = _source_components(source_id)
    raw_url = f"https://raw.githubusercontent.com/{project.repo}/{project.revision}/{source_path}"
    destination = safe_file(root, raw_path, must_exist=False)
    ledger_path = safe_file(root, "raw/request_attempts.jsonl", must_exist=False)
    last_error = "source request failed"
    source_attempts = 0

    if manifest.get("historicalRedirectHopsUnknown") is True:
        raise RuntimeError("historical redirect hops are unknown; network fetching is disabled")
    for attempt in range(MAX_RETRIES + 1):
        if request_count[0] >= MAX_PHYSICAL_REQUESTS:
            manifest.setdefault("failures", []).append(
                {
                    "sourceRecordId": source_id,
                    "url": url,
                    "upstreamRevision": project.revision,
                    "physicalAttempts": source_attempts,
                    "reason": (
                        "150-request category budget reached; source rejected without fallback"
                    ),
                }
            )
            atomic_write_bytes(manifest_path, json_bytes(manifest, pretty=True))
            raise RuntimeError("category source request limit of 150 physical requests reached")
        source_attempts += 1
        request_count[0] += 1
        attempt_id = f"request-{request_count[0]}"
        started_at = timestamp_utc()
        append_attempt_event(
            ledger_path,
            {
                "attemptId": attempt_id,
                "event": "started",
                "rawURL": raw_url,
                "sourceRecordId": source_id,
                "startedAtUTC": started_at,
            },
        )
        manifest["physicalRequestsBudgetConsumed"] = request_count[0]
        manifest["physicalRequestsThisCollection"] = (
            manifest.get("physicalRequestsThisCollection", 0) + 1
        )
        atomic_write_bytes(manifest_path, json_bytes(manifest, pretty=True))
        request = Request(raw_url, headers={"User-Agent": "query-gold-curator/1.0"})
        try:
            with open_without_redirects(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response_status = getattr(response, "status", None)
                status_code = response_status if isinstance(response_status, int) else None
                payload = response.read(MAX_SOURCE_BYTES + 1)
            if len(payload) > MAX_SOURCE_BYTES:
                raise ValueError("pinned source exceeds the 2 MB per-file cache limit")
            payload.decode("utf-8", errors="strict")
        except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, ValueError) as error:
            status_code = error.code if isinstance(error, HTTPError) else None
            outcome = (
                "http_error"
                if isinstance(error, HTTPError)
                else "invalid_response"
                if isinstance(error, (UnicodeDecodeError, ValueError))
                else "transport_error"
            )
            append_attempt_event(
                ledger_path,
                {
                    "attemptId": attempt_id,
                    "event": "finished",
                    "error": f"HTTP {status_code}"
                    if status_code is not None
                    else type(error).__name__,
                    "finishedAtUTC": timestamp_utc(),
                    "outcome": outcome,
                    "rawURL": raw_url,
                    "sourceRecordId": source_id,
                    "statusCode": status_code,
                },
            )
            last_error = f"HTTP {status_code}" if status_code is not None else type(error).__name__
            if attempt == MAX_RETRIES:
                break
            continue

        append_attempt_event(
            ledger_path,
            {
                "attemptId": attempt_id,
                "event": "finished",
                "finishedAtUTC": timestamp_utc(),
                "outcome": "success",
                "rawURL": raw_url,
                "sourceRecordId": source_id,
                "statusCode": status_code,
            },
        )
        atomic_write_bytes(destination, payload)
        entry = manifest_entry(
            source_id=source_id,
            repo=project.repo,
            tag=project.tag,
            revision=project.revision,
            source_path=source_path,
            raw_path=raw_path,
            url=url,
            retrieved_at=timestamp_utc(),
            payload=payload,
        )
        source_rows = manifest.setdefault("sources", [])
        previous = [
            index
            for index, row in enumerate(source_rows)
            if isinstance(row, dict) and row.get("sourceRecordId") == source_id
        ]
        if len(previous) > 1:
            raise ValueError(f"duplicate source manifest rows for {source_id}")
        if previous:
            source_rows[previous[0]] = entry
        else:
            source_rows.append(entry)
        manifest["requestLimit"] = MAX_PHYSICAL_REQUESTS
        manifest["requestTimeoutSeconds"] = REQUEST_TIMEOUT_SECONDS
        manifest["maxRetriesPerSource"] = MAX_RETRIES
        atomic_write_bytes(manifest_path, json_bytes(manifest, pretty=True))
        return entry

    failure = {
        "sourceRecordId": source_id,
        "url": url,
        "upstreamRevision": project.revision,
        "physicalAttempts": source_attempts,
        "reason": last_error,
    }
    manifest.setdefault("failures", []).append(failure)
    atomic_write_bytes(manifest_path, json_bytes(manifest, pretty=True))
    raise RuntimeError(f"pinned source fetch rejected for {source_id}: {last_error}")


def _read_source_manifest(
    root: Path,
) -> tuple[Path, dict[str, Any], dict[str, dict[str, Any]]]:
    manifest_path = safe_file(root, "raw/snapshot_manifest.json", must_exist=False)
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), list):
            raise ValueError("source snapshot manifest has an invalid shape")
    else:
        manifest = {
            "schemaVersion": "query-gold-source-snapshots/v1",
            "sources": [],
            "failures": [],
        }
        atomic_write_bytes(manifest_path, json_bytes(manifest, pretty=True))

    by_id: dict[str, dict[str, Any]] = {}
    for entry in manifest["sources"]:
        if isinstance(entry, dict) and isinstance(entry.get("sourceRecordId"), str):
            if entry["sourceRecordId"] in by_id:
                raise ValueError("source snapshot manifest contains duplicate sourceRecordIds")
            by_id[entry["sourceRecordId"]] = entry
    return manifest_path, manifest, by_id


def _verify_snapshot_file(
    source_id: str,
    entry: dict[str, Any],
    project: Project,
    source_path: str,
    raw_path: str,
    url: str,
    source_file: Path,
) -> bytes:
    expected = {
        "repo": project.repo,
        "tag": project.tag,
        "upstreamRevision": project.revision,
        "path": source_path,
        "url": url,
        "rawUrl": f"https://raw.githubusercontent.com/{project.repo}/{project.revision}/{source_path}",
        "rawPath": raw_path,
    }
    if any(entry.get(field) != value for field, value in expected.items()):
        raise ValueError(f"snapshot manifest does not match pinned source {source_id}")
    digest = entry.get("sha256")
    retrieved_at = entry.get("retrievedAt")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError(f"snapshot manifest has an invalid SHA-256 for {source_id}")
    if not isinstance(retrieved_at, str) or not retrieved_at.endswith("Z"):
        raise ValueError(f"snapshot manifest has no UTC retrieval timestamp for {source_id}")
    payload = source_file.read_bytes()
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError(f"pinned source cache SHA-256 mismatch for {source_id}")
    payload.decode("utf-8", errors="strict")
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError(f"pinned source exceeds the 2 MB per-file cache limit: {source_id}")
    return payload


def _load_source_bytes(
    root: Path,
    *,
    source_ids: list[str] | None = None,
    request_count: list[int] | None = None,
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    """Load verified snapshots, fetching only missing pinned files on opt-in collect."""
    root = guard_absolute_path(root)
    root.mkdir(parents=True, exist_ok=True)
    guard_absolute_path(root)
    manifest_path, manifest, by_id = _read_source_manifest(root)
    prior_request_count = manifest.get(
        "physicalRequestsBudgetConsumed", manifest.get("physicalRequestsTotal", 0)
    )
    if not isinstance(prior_request_count, int) or isinstance(prior_request_count, bool):
        raise ValueError("source manifest physical request count is invalid")
    ledger_path = safe_file(root, "raw/request_attempts.jsonl", must_exist=False)
    ledger_attempts = count_started_attempts(ledger_path)
    legacy_starts = manifest.get("legacyRequestStartsBeforeDurableLedger")
    if legacy_starts is None:
        legacy_starts = max(0, prior_request_count - ledger_attempts)
        manifest["legacyRequestStartsBeforeDurableLedger"] = legacy_starts
        manifest["historicalRedirectHopsUnknown"] = legacy_starts > 0
        if legacy_starts:
            manifest["physicalRequestsBudgetConsumedIsProvenUpperBound"] = False
            manifest["historicalRequestAccountingNote"] = (
                "The inherited ledger counted urlopen request starts; automatic redirect "
                "hops were not separately logged, so the prior physical wire-hop total "
                "is unknown. Further network fetches are disabled for this snapshot."
            )
        accounting = manifest.setdefault("requestAccounting", {})
        if isinstance(accounting, dict):
            accounting["legacyRequestStartsBeforeDurableLedger"] = legacy_starts
            accounting["historicalRedirectHopsSeparatelyCounted"] = False
            accounting["historicalPhysicalWireRequestTotal"] = "unknown" if legacy_starts else 0
    prior_request_count = max(prior_request_count, legacy_starts + ledger_attempts)
    if not 0 <= prior_request_count <= MAX_PHYSICAL_REQUESTS:
        raise ValueError("source manifest has exceeded the 150-request category budget")
    manifest["redirectPolicy"] = "fail_closed"
    counter = request_count if request_count is not None else [prior_request_count]
    if request_count is None:
        manifest["physicalRequestsBudgetConsumed"] = counter[0]
        atomic_write_bytes(manifest_path, json_bytes(manifest, pretty=True))
    if source_ids is None:
        raise ValueError("source IDs must be explicit to keep collection bounded")
    byte_cache: dict[str, bytes] = {}
    verified_entries: dict[str, dict[str, Any]] = {}
    for source_id in source_ids:
        project, source_path, raw_path, url = _source_components(source_id)
        entry = by_id.get(source_id)
        source_file = safe_file(root, raw_path, must_exist=False)
        if entry is None and source_file.is_file():
            raise ValueError(f"untracked cache/source manifest mismatch for {source_id}")
        if entry is None or not source_file.is_file():
            entry = _fetch_pinned_source(
                source_id,
                request_count=counter,
                manifest=manifest,
                manifest_path=manifest_path,
                root=root,
            )
            by_id[source_id] = entry
        payload = _verify_snapshot_file(
            source_id, entry, project, source_path, raw_path, url, source_file
        )
        byte_cache[source_id] = payload
        verified_entries[source_id] = entry
    return byte_cache, verified_entries


def _verified_license(project: Project, license_bytes: bytes) -> str:
    text = license_bytes.decode("utf-8", errors="strict")
    if project.repo == "python/cpython":
        if "Python Software Foundation License Version 2." not in text:
            return "unknown"
        return "Python Software Foundation License Version 2"
    if project.repo == "pandas-dev/pandas":
        if "BSD 3-Clause License" not in text:
            return "unknown"
        return "BSD 3-Clause License"
    if project.repo == "pallets/click":
        if "Copyright 2014 Pallets" not in text or not all(
            marker in text
            for marker in ("1.  Redistributions", "2.  Redistributions", "3.  Neither")
        ):
            return "unknown"
        return "BSD 3-Clause License (Pallets terms)"
    return "unknown"


def _directive_signature(source: str, target: str) -> tuple[str, str]:
    """Return a displayed RST API signature and its exact directive excerpt."""
    lines = source.splitlines(keepends=True)
    directive = re.compile(r"^\.\.\s+(?:function|method|classmethod|staticmethod|class)::\s+")
    for index, line in enumerate(lines):
        if not directive.match(line):
            continue
        display = line.split("::", maxsplit=1)[1].strip()
        name = display.split("(", maxsplit=1)[0].strip()
        if name != target:
            continue
        excerpt_lines = [line]
        if line.rstrip("\r\n").endswith("\\"):
            cursor = index + 1
            while cursor < len(lines):
                continuation = lines[cursor]
                excerpt_lines.append(continuation)
                display += " " + continuation.strip().rstrip("\\").strip()
                cursor += 1
                if not continuation.rstrip("\r\n").endswith("\\"):
                    break
        return display, "".join(excerpt_lines)
    raise ValueError(f"RST API directive not found for {target}")


def _split_signature_parameters(signature: str) -> list[str]:
    opening = signature.find("(")
    closing = signature.rfind(")")
    if opening < 0 or closing <= opening:
        raise ValueError("API signature has no balanced parameter list")
    return [piece.strip() for piece in signature[opening + 1 : closing].split(",")]


def _default_from_signature(signature: str, parameter: str) -> str:
    for piece in _split_signature_parameters(signature):
        candidate = piece.strip()
        if candidate.startswith(parameter) and len(candidate) > len(parameter):
            suffix = candidate[len(parameter) :].lstrip()
            if suffix.startswith("="):
                expression = suffix[1:].strip()
                if expression:
                    return expression
    raise ValueError(f"parameter default not found for {parameter}")


def _find_python_function(source: str, target: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    if "." in target:
        class_name, function_name = target.rsplit(".", maxsplit=1)
    else:
        class_name, function_name = None, target
    tree = ast.parse(source)
    candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    if class_name is None:
        candidates = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ]
    else:
        classes = [
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if len(classes) != 1:
            raise ValueError(f"Python source class not found uniquely: {class_name}")
        candidates = [
            node
            for node in classes[0].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ]
    if not candidates:
        raise ValueError(f"Python source function not found: {target}")
    return candidates[-1]


def _python_default_node(node: ast.FunctionDef | ast.AsyncFunctionDef, parameter: str) -> ast.expr:
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for argument, default in zip(positional, defaults, strict=True):
        if argument.arg == parameter and default is not None:
            return default
    for argument, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        if argument.arg == parameter and default is not None:
            return default
    raise ValueError(f"Python source default not found for {node.name}.{parameter}")


def _python_header(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    lines = source.splitlines(keepends=True)
    if not node.body:
        raise ValueError(f"Python function has no body: {node.name}")
    excerpt = "".join(lines[node.lineno - 1 : node.body[0].lineno - 1])
    if not excerpt.strip() or not excerpt.lstrip().startswith(("def ", "async def ")):
        raise ValueError(f"Python function header could not be isolated: {node.name}")
    return excerpt


def _python_default(source: str, target: str, parameter: str) -> tuple[str, str, Any]:
    node = _find_python_function(source, target)
    expression_node = _python_default_node(node, parameter)
    expression = ast.get_source_segment(source, expression_node)
    if expression is None:
        raise ValueError(f"Python source expression is unavailable for {target}.{parameter}")
    if expression == "...":
        raise ValueError(
            f"Python source contains only a typing placeholder for {target}.{parameter}"
        )
    return expression, _python_header(source, node), _literal_value(expression)


def _literal_value(expression: str) -> Any:
    try:
        value = ast.literal_eval(expression)
    except (ValueError, SyntaxError):
        return _MISSING
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite default values are not supported")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return _MISSING


def _line_excerpt(source: str, needle: str) -> str:
    matches = [line for line in source.splitlines(keepends=True) if needle in line]
    if not matches or any(line != matches[0] for line in matches[1:]):
        raise ValueError(f"expected exactly one source line containing selector {needle!r}")
    return matches[0]


def _paragraph_excerpt(source: str, needle: str) -> str:
    lines = source.splitlines(keepends=True)
    matching = [index for index, line in enumerate(lines) if needle in line]
    if len(matching) != 1:
        raise ValueError(f"expected exactly one source paragraph containing selector {needle!r}")
    start = matching[0]
    end = start + 1
    while start > 0 and lines[start - 1].strip():
        start -= 1
    while end < len(lines) and lines[end].strip():
        end += 1
    return "".join(lines[start:end])


def _click_default(excerpt: str, parameter: str) -> tuple[str, Any]:
    match = re.search(rf"\b{re.escape(parameter)}\s*=\s*([^,)]+)", excerpt)
    if match is None:
        raise ValueError(f"Click option default not found for {parameter}")
    expression = match.group(1).strip()
    return expression, _literal_value(expression)


def _validate_spec(spec: FactSpec) -> None:
    if not _CASE_ID.fullmatch(spec.id):
        raise ValueError(f"invalid stable case id: {spec.id}")
    if spec.source not in SOURCE_PATHS:
        raise ValueError(f"unknown category source alias: {spec.source}")
    if not spec.query.strip() or len(spec.query) > 8000:
        raise ValueError(f"invalid query text for {spec.id}")
    if spec.extractor not in {
        "rst_signature",
        "rst_default",
        "python_default",
        "click_long_option",
        "click_section_option",
        "click_command_default",
        "click_default",
        "line_literal",
        "paragraph_literal",
        "release_section_literal",
    }:
        raise ValueError(f"unknown fact extractor for {spec.id}")
    if (
        spec.extractor
        in {
            "rst_default",
            "python_default",
            "click_default",
            "click_command_default",
        }
        and not spec.parameter
    ):
        raise ValueError(f"parameter-default fact lacks an exact field name: {spec.id}")
    literal_extractors = {"line_literal", "paragraph_literal", "release_section_literal"}
    if spec.extractor in literal_extractors and (spec.answer is None or not spec.support):
        raise ValueError(f"literal fact lacks an answer or source support markers: {spec.id}")
    if spec.extractor not in literal_extractors and (spec.answer is not None or spec.support):
        raise ValueError(f"extracted fact must not carry a hand-authored answer: {spec.id}")
    allowed_units = {
        "code_api_click_parameter_option_arity": "arguments per option occurrence",
        "code_api_click_runserver_port_default": "TCP port",
    }
    expected_units = allowed_units.get(spec.id)
    if spec.units is not None and expected_units is None:
        raise ValueError(f"units are not defined for this API fact: {spec.id}")
    if expected_units is not None and spec.units is None:
        raise ValueError(f"source fact requires explicit units: {spec.id}")
    if spec.units is not None and spec.units != expected_units:
        raise ValueError(f"units are invalid for this source fact: {spec.id}")
    if spec.extractor == "click_section_option":
        if not spec.section:
            raise ValueError(f"Click option fact lacks an exact section: {spec.id}")
    elif spec.section is not None:
        raise ValueError(f"unexpected section on non-section fact: {spec.id}")
    expected_type = {
        "rst_signature": "api_signature",
        "rst_default": "parameter_default",
        "python_default": "parameter_default",
        "click_default": "parameter_default",
        "click_command_default": "parameter_default",
        "click_long_option": "cli_option",
        "click_section_option": "cli_option",
        "release_section_literal": "release_change",
    }.get(spec.extractor)
    if expected_type is not None and spec.question_type != expected_type:
        raise ValueError(f"fact extractor has an incompatible question type: {spec.id}")


def _extract_fact(spec: FactSpec, source: str) -> tuple[str, str, Any]:
    _validate_spec(spec)
    if spec.extractor == "rst_signature":
        answer, excerpt = _directive_signature(source, spec.target)
        return answer, excerpt, answer
    if spec.extractor == "rst_default":
        signature, excerpt = _directive_signature(source, spec.target)
        answer = _default_from_signature(signature, spec.parameter or "")
        return answer, excerpt, _literal_value(answer)
    if spec.extractor == "python_default":
        return _python_default(source, spec.target, spec.parameter or "")
    if spec.extractor == "click_long_option":
        excerpt = _line_excerpt(source, spec.target)
        answer = long_option(excerpt)
        return answer, excerpt, answer
    if spec.extractor == "click_section_option":
        excerpt = section_option_excerpt(source, spec.section or "", spec.target)
        answer = long_option(excerpt)
        return answer, excerpt, answer
    if spec.extractor == "click_default":
        excerpt = _line_excerpt(source, spec.target)
        answer, value = _click_default(excerpt, spec.parameter or "")
        return answer, excerpt, value
    if spec.extractor == "click_command_default":
        return click_command_default(source, spec.target, spec.parameter or "", _click_default)

    if spec.extractor == "release_section_literal":
        project = PROJECTS[SOURCE_PATHS[spec.source][0]]
        version = spec.version or project.tag.removeprefix("v")
        excerpt = release_section_excerpt(source, version, spec.target)
    elif spec.extractor == "paragraph_literal":
        excerpt = _paragraph_excerpt(source, spec.target)
    else:
        excerpt = _line_excerpt(source, spec.target)
    missing_support = [marker for marker in spec.support if marker not in excerpt]
    if missing_support:
        raise ValueError(f"literal answer lacks cached-source support for {spec.id}")
    return spec.answer or "", excerpt, spec.answer or ""


def _source_family(spec: FactSpec) -> str:
    if spec.source.startswith("py_"):
        return (
            "official_cpython_release_notes"
            if spec.source == "py_changes"
            else "official_cpython_reference"
        )
    if spec.source.startswith("pd_"):
        return (
            "official_pandas_release_notes"
            if spec.source == "pd_changes"
            else "official_pandas_source"
        )
    if spec.source == "click_changes":
        return "official_click_changelog"
    if spec.source == "click_core":
        return "official_click_source"
    return "official_click_documentation"


def _make_case(
    spec: FactSpec,
    *,
    source_bytes: bytes,
    source_entry: dict[str, Any],
    source_license: str,
) -> dict[str, Any]:
    source_id = _source_id(spec.source)
    project, _, raw_path, url = _source_components(source_id)
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != source_entry.get("sha256"):
        raise ValueError(f"source bytes no longer match the snapshot manifest: {source_id}")
    source = source_bytes.decode("utf-8", errors="strict")
    answer, excerpt, value = _extract_fact(spec, source)
    if not answer.strip() or not excerpt.strip() or len(excerpt) > 8000 or excerpt not in source:
        raise ValueError(f"source extraction produced an empty or oversized fact: {spec.id}")
    version = spec.version or project.tag.removeprefix("v")
    if version not in spec.query:
        raise ValueError(f"query does not state its exact source version: {spec.id}")
    gold: dict[str, Any] = {"answer": answer, "acceptedAnswers": [answer]}
    if value is not _MISSING:
        gold["value"] = value
    if spec.units is not None:
        gold["units"] = spec.units
    record = {
        "schemaVersion": SCHEMA_VERSION,
        "id": spec.id,
        "categoryId": CATEGORY_ID,
        "query": spec.query,
        "temporal": {"kind": "version", "precision": "version", "version": version},
        "gold": gold,
        "evidence": [
            {
                "url": url,
                "title": (
                    f"{project.display_name} {project.tag.removeprefix('v')} pinned source: "
                    f"{source_entry['path']}"
                ),
                "retrievedAtUTC": source_entry["retrievedAt"],
                "sourceRecordId": source_id,
                "upstreamRevision": project.revision,
                "license": source_license,
                "rawSha256": digest,
                "rawPath": raw_path,
                "excerpt": excerpt,
            }
        ],
        "derivation": {
            "sourceFamily": _source_family(spec),
            "generatorVersion": GENERATOR_VERSION,
            "questionType": spec.question_type,
        },
    }
    if f"/blob/{project.revision}/" not in url:
        raise ValueError(f"case has no pinned, answer-bearing public source page: {spec.id}")
    validated = QueryGoldCase.model_validate(record)
    canonical = validated.model_dump(mode="json", exclude_none=True)
    _assert_query_direct(canonical["query"], version, spec.id)
    return canonical


_CONTEXT_REFERENCE = re.compile(
    r"\b(?:above|below|former|latter|previous|following|latest|current|"
    r"this page|that page|these results)\b",
    re.IGNORECASE,
)
_DERIVED_OR_CROSS_SOURCE = re.compile(
    r"\b(?:calculate|compute|derive|difference between|sum of|combined total|across documents)\b",
    re.IGNORECASE,
)
_SECOND_QUESTION = re.compile(
    r"\b(?:and|also)\s+(?:what|which|when|where|why|how)\b", re.IGNORECASE
)
_COMPOUND_LIST = re.compile(r"\b(?:which two|what are the two|both .+ and .+)\b", re.IGNORECASE)


def _assert_query_direct(query: str, version: str, case_id: str) -> None:
    """Reject vague, unscoped, derived, or multi-question search prompts."""
    if query.count("?") != 1 or version.casefold() not in query.casefold():
        raise ValueError(f"query must be one standalone, version-scoped question: {case_id}")
    if _CONTEXT_REFERENCE.search(query):
        raise ValueError(f"query depends on hidden conversational context: {case_id}")
    if _DERIVED_OR_CROSS_SOURCE.search(query):
        raise ValueError(f"query requires derived or cross-source reasoning: {case_id}")
    if _SECOND_QUESTION.search(query):
        raise ValueError(f"query contains more than one requested fact: {case_id}")
    if _COMPOUND_LIST.search(query):
        raise ValueError(f"query requests multiple facts instead of one direct answer: {case_id}")


def _validate_collection(records: list[dict[str, Any]]) -> None:
    if len(records) != 50:
        raise ValueError(f"code API category requires exactly 50 curated cases, got {len(records)}")
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("code API category contains duplicate case IDs")
    queries = [" ".join(record["query"].casefold().split()) for record in records]
    if len(set(queries)) != len(queries):
        raise ValueError("code API category contains duplicate normalized queries")
    source_ids = {record["evidence"][0]["sourceRecordId"] for record in records}
    question_types = {record["derivation"]["questionType"] for record in records}
    if len(source_ids) < 25:
        raise ValueError("code API category must cite at least 25 distinct source records")
    if len(question_types) < 3:
        raise ValueError("code API category must include at least three question types")
    for record in records:
        version = record["temporal"]["version"]
        _assert_query_direct(record["query"], version, record["id"])
        answer = record["gold"]["answer"].casefold()
        query = " ".join(record["query"].casefold().split())
        if len(answer) >= 5 and answer in query:
            raise ValueError(f"canonical answer appears verbatim in the query: {record['id']}")


def _write_case_specs(root: Path, specs: tuple[FactSpec, ...]) -> None:
    rows = []
    for spec in specs:
        row = asdict(spec)
        row["sourceRecordId"] = _source_id(spec.source)
        row.pop("source")
        row.pop("answer", None)
        row.pop("support", None)
        rows.append(row)
    path = safe_file(root, "raw/case_specs.json", must_exist=False)
    atomic_write_bytes(
        path,
        json_bytes({"schemaVersion": "query-gold-code-api-specs/v1", "specs": rows}, pretty=True),
    )


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Return the version-pinned category records and cache canonical JSONL.

    Missing upstream files are fetched only during this explicit collection call.
    Each request has a timeout, at most one retry is made, and physical requests
    are capped at 150. Existing cached source bytes are checksum-verified first.
    """
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 50:
        raise ValueError("count must be an integer between 1 and 50")
    root = guard_absolute_path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    guard_absolute_path(root)
    selected_specs = FACT_SPECS[:count]
    required_ids = {_source_id(spec.source) for spec in selected_specs}
    required_ids.update(
        f"{repo}:{PROJECTS[repo].license_file}"
        for repo in {SOURCE_PATHS[spec.source][0] for spec in selected_specs}
    )
    source_bytes, source_entries = _load_source_bytes(root, source_ids=sorted(required_ids))

    used_repos = {SOURCE_PATHS[spec.source][0] for spec in selected_specs}
    licenses: dict[str, str] = {}
    for repo in used_repos:
        project = PROJECTS[repo]
        license_id = f"{repo}:{project.license_file}"
        licenses[repo] = _verified_license(project, source_bytes[license_id])

    records = [
        _make_case(
            spec,
            source_bytes=source_bytes[_source_id(spec.source)],
            source_entry=source_entries[_source_id(spec.source)],
            source_license=licenses[SOURCE_PATHS[spec.source][0]],
        )
        for spec in selected_specs
    ]
    if count == 50:
        _validate_collection(records)
    cases_path = safe_file(root, "cases.jsonl", must_exist=False)
    serialized = b"".join(json_bytes(record) for record in records)
    atomic_write_bytes(cases_path, serialized)
    _write_case_specs(root, selected_specs)
    return records


def _default_output_dir() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return (
        repository_root
        / "results"
        / "query-gold-curation"
        / "first-five-v1"
        / "categories"
        / CATEGORY_ID
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect pinned code API documentation query/gold cases."
    )
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--count", type=int, default=50)
    arguments = parser.parse_args()
    records = collect(arguments.output_dir, arguments.count)
    print(f"Wrote {len(records)} code API cases to {arguments.output_dir / 'cases.jsonl'}")


if __name__ == "__main__":
    main()
