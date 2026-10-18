"""Embedding BLOBs: little-endian float32, L2-normalized, `embedding_dimensions` values."""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

FloatMatrix = npt.NDArray[np.float32]
_DTYPE = np.dtype("<f4")


def pack_vector(vector: Sequence[float]) -> bytes:
    """L2-normalize `vector` and pack it as a little-endian float32 BLOB."""

    array = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if norm > 0:
        array = array / norm
    return array.astype(_DTYPE).tobytes()


def blob_dimensions(blob: bytes | None) -> int:
    return 0 if not blob else len(blob) // _DTYPE.itemsize


def stack_vectors(blobs: Sequence[bytes | None], dimensions: int) -> tuple[FloatMatrix, list[int]]:
    """Stack the BLOBs that have exactly `dimensions` values.

    Returns the matrix and the input positions of its rows. BLOBs with another dimension
    (written by another embedding setting) or no BLOB at all are refused.
    """

    rows: list[npt.NDArray[np.float32]] = []
    positions: list[int] = []
    for position, blob in enumerate(blobs):
        if blob is None or blob_dimensions(blob) != dimensions or len(blob) % _DTYPE.itemsize:
            continue
        rows.append(np.frombuffer(blob, dtype=_DTYPE).astype(np.float32))
        positions.append(position)
    if not rows:
        return np.zeros((0, dimensions), dtype=np.float32), []
    return np.vstack(rows), positions


def query_vector(vector: Sequence[float], dimensions: int) -> npt.NDArray[np.float32] | None:
    """The normalized query vector, or None when its dimension does not match."""

    if len(vector) != dimensions:
        return None
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    return array / norm if norm > 0 else array
