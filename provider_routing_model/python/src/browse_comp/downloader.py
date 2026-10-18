"""Dataset fetching and parquet loading utilities."""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pandas as pd

DEFAULT_PARQUET_URL = (
    "https://huggingface.co/api/datasets/smolagents/browse_comp/parquet/default/test/0.parquet"
)


def load_raw_dataset(source: str | Path | None = None) -> pd.DataFrame:
    """Load the raw parquet dataset from a local path, URL, or default HF endpoint.

    Args:
        source: Local file path or remote HTTP(S) URL. Defaults to the official HF parquet URL.

    Returns:
        pd.DataFrame containing raw columns ('problem', 'answer', 'problem_topic', 'canary').
    """
    target = str(source) if source is not None else DEFAULT_PARQUET_URL

    if target.startswith(("http://", "https://")):
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(target)
            response.raise_for_status()
            buffer = io.BytesIO(response.content)
            return pd.read_parquet(buffer)

    local_path = Path(target)
    if not local_path.is_file():
        msg = f"Parquet dataset file not found: {local_path}"
        raise FileNotFoundError(msg)
    return pd.read_parquet(local_path)
