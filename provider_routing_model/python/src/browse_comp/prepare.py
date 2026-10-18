"""Data transformation and preparation pipeline for BrowseComp."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from browse_comp.crypto import DEFAULT_CANARY, decrypt_field
from browse_comp.downloader import load_raw_dataset
from browse_comp.models import BenchmarkAnswer, BenchmarkCase


def process_dataset(
    df: pd.DataFrame,
    id_prefix: str = "browse-comp-",
    required_tools: list[Literal["search", "fetch"]] | None = None,
) -> tuple[list[BenchmarkCase], list[BenchmarkAnswer]]:
    """Transform raw BrowseComp dataframe into benchmark cases and ground-truth answers.

    Args:
        df: Raw pandas DataFrame with problem, answer, problem_topic, canary.
        id_prefix: Prefix for case IDs (e.g. 'browse-comp-').
        required_tools: Optional tool requirement override for benchmark cases.

    Returns:
        Tuple of (cases, answers) lists.
    """
    required_cols = {"problem", "answer", "problem_topic", "canary"}
    missing = required_cols - set(df.columns)
    if missing:
        msg = f"Dataset is missing required columns: {sorted(missing)}"
        raise ValueError(msg)

    canary = str(df["canary"].iloc[0]) if not df.empty else DEFAULT_CANARY

    processed_df = df.copy()
    processed_df["decrypted_problem"] = processed_df["problem"].map(
        lambda p: decrypt_field(str(p), canary).strip()
    )
    processed_df["decrypted_answer"] = processed_df["answer"].map(
        lambda a: decrypt_field(str(a), canary).strip()
    )
    processed_df["topic"] = processed_df["problem_topic"].map(lambda t: str(t).strip())

    total_rows = len(processed_df)
    pad_width = max(4, len(str(total_rows)))
    case_indices = np.arange(1, total_rows + 1)

    cases: list[BenchmarkCase] = []
    answers: list[BenchmarkAnswer] = []

    for idx, (_, row) in zip(case_indices, processed_df.iterrows(), strict=True):
        case_id = f"{id_prefix}{int(idx):0{pad_width}d}"
        prompt = str(row["decrypted_problem"])
        answer_text = str(row["decrypted_answer"])
        topic = str(row["topic"])

        case = BenchmarkCase(
            id=case_id,
            prompt=prompt,
            requiredTools=required_tools,
        )
        answer = BenchmarkAnswer(
            id=case_id,
            answer=answer_text,
            problem_topic=topic,
            prompt=prompt,
        )
        cases.append(case)
        answers.append(answer)

    return cases, answers


def write_jsonl(records: list[BenchmarkCase] | list[BenchmarkAnswer], output_path: Path) -> int:
    """Write records to a JSONL file, ensuring strict serialization without extra fields.

    Args:
        records: List of BenchmarkCase or BenchmarkAnswer models.
        output_path: Path to target .jsonl file.

    Returns:
        Number of lines written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            # Exclude None to avoid emitting requiredTools: null when omitted
            dumped = record.model_dump(exclude_none=True)
            f.write(json.dumps(dumped, ensure_ascii=False) + "\n")
    return len(records)


def prepare_benchmark_artifacts(
    source: str | Path | None = None,
    output_dir: Path | None = None,
    subset_size: int = 10,
    required_tools: list[Literal["search", "fetch"]] | None = None,
    id_prefix: str = "browse-comp-",
) -> dict[str, Path]:
    """Execute end-to-end data preparation, saving full and subset JSONL files.

    Args:
        source: Optional source path or URL for raw dataset.
        output_dir: Target directory for generated JSONL files.
        subset_size: Number of cases to include in the subset benchmark.
        required_tools: Optional tool requirement list for execution inputs.
        id_prefix: Identifier prefix for each case.

    Returns:
        Dictionary mapping artifact names to their file paths.
    """
    if output_dir is None:
        # Default to data/ directory at project root
        output_dir = Path(__file__).resolve().parents[3] / "data"

    raw_df = load_raw_dataset(source)
    cases, answers = process_dataset(raw_df, id_prefix=id_prefix, required_tools=required_tools)

    subset_cases = cases[:subset_size]
    subset_answers = answers[:subset_size]

    full_inputs_path = output_dir / "browse_comp.jsonl"
    full_answers_path = output_dir / "browse_comp_answers.jsonl"
    subset_inputs_path = output_dir / f"browse_comp_subset{subset_size}.jsonl"
    subset_answers_path = output_dir / f"browse_comp_subset{subset_size}_answers.jsonl"

    write_jsonl(cases, full_inputs_path)
    write_jsonl(answers, full_answers_path)
    write_jsonl(subset_cases, subset_inputs_path)
    write_jsonl(subset_answers, subset_answers_path)

    return {
        "full_inputs": full_inputs_path,
        "full_answers": full_answers_path,
        "subset_inputs": subset_inputs_path,
        "subset_answers": subset_answers_path,
    }
