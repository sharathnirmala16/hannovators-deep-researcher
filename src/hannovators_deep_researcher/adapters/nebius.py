"""Nebius Token Factory adapters: the Nemotron `ChatModel` and the Qwen3 `Embedder`.

Both use the OpenAI SDK against `NEBIUS_BASE_URL`; the SDK owns its HTTP client (it is typed
against `httpx2`), so the factories accept the shared `httpx` client only for a uniform
signature. Chat answers use `response_format` JSON schema from the Pydantic model;
`reasoning_content` is ignored, and one repair retry handles bad JSON.
"""

import base64
import math
import re
import struct
from collections.abc import Sequence
from itertools import batched
from typing import Any, cast

import httpx
import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.models.enums import ModelRole
from hannovators_deep_researcher.models.web import ProviderError, ProviderFailure

_NAME = "nebius"
EMBED_BATCH_SIZE = 64
_TEXT_TEMPERATURE = 1.0
_VISION_TEMPERATURE = 0.6
_TOP_P = 0.95
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_REPAIR_PROMPT = (
    "Your last reply was not valid JSON for the required schema. Error: {error}\n"
    "Reply again with only the corrected JSON object. No prose, no code fences."
)


def _failure(
    code: str, message: str, *, retryable: bool = False, status: int | None = None
) -> ProviderFailure:
    return ProviderFailure(
        ProviderError(
            provider=_NAME, code=code, message=message, retryable=retryable, status_code=status
        )
    )


def extract_json(text: str) -> str:
    """Strip code fences and prose around the outermost JSON object."""

    stripped = _FENCE.sub("", text.strip())
    start, end = stripped.find("{"), stripped.rfind("}")
    return stripped[start : end + 1] if 0 <= start < end else stripped


def parse_json_reply[T: BaseModel](schema: type[T], text: str) -> T:
    """Validate a model reply as `schema`. Raises `ValidationError` on bad or truncated JSON."""

    return schema.model_validate_json(extract_json(text))


def _map_api_error(exc: openai.OpenAIError) -> ProviderFailure:
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        return _failure(
            "http_error",
            f"HTTP {status}",
            retryable=status in {429, 500, 502, 503, 504},
            status=status,
        )
    if isinstance(exc, openai.APITimeoutError):
        return _failure("timeout", "request timed out", retryable=True)
    if isinstance(exc, openai.APIConnectionError):
        return _failure("transport_error", type(exc).__name__, retryable=True)
    return _failure("openai_error", type(exc).__name__)


def _user_content(user: str, images: Sequence[bytes]) -> str | list[dict[str, Any]]:
    if not images:
        return user
    parts: list[dict[str, Any]] = [{"type": "text", "text": user}]
    for image in images:
        encoded = base64.b64encode(image).decode()
        parts.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
        )
    return parts


class NebiusChatModel:
    """`ChatModel` for Nemotron on Nebius. Each role maps to a model ID through settings."""

    def __init__(self, client: AsyncOpenAI, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def complete_json[T: BaseModel](
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        schema: type[T],
        images: Sequence[bytes] = (),
    ) -> T:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": _user_content(user, images)},
        ]
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
        }
        temperature = _VISION_TEMPERATURE if images else _TEXT_TEMPERATURE
        model = self._settings.model_for(role)
        reply = await self._create(model, messages, response_format, temperature)
        try:
            return parse_json_reply(schema, reply)
        except ValidationError as exc:
            messages += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": _REPAIR_PROMPT.format(error=str(exc)[:800])},
            ]
        reply = await self._create(model, messages, response_format, temperature)
        try:
            return parse_json_reply(schema, reply)
        except ValidationError as exc:
            raise _failure("invalid_json", f"{schema.__name__} reply invalid after repair") from exc

    async def _create(
        self,
        model: str,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any],
        temperature: float,
    ) -> str:
        try:
            completion = await self._client.chat.completions.create(
                model=model,
                messages=cast(Any, messages),
                response_format=cast(Any, response_format),
                temperature=temperature,
                top_p=_TOP_P,
            )
        except openai.OpenAIError as exc:
            raise _map_api_error(exc) from exc
        if not completion.choices:
            raise _failure("invalid_response", "completion has no choices")
        return completion.choices[0].message.content or ""


def fit_vector(values: Sequence[float], dimensions: int) -> list[float]:
    """Keep the first `dimensions` values (Matryoshka) and L2-normalize again."""

    head = [float(value) for value in values[:dimensions]]
    norm = math.sqrt(sum(value * value for value in head))
    return [value / norm for value in head] if norm > 0 else head


def pack_vector(vector: Sequence[float]) -> bytes:
    """Pack a vector as a little-endian float32 BLOB."""

    return struct.pack(f"<{len(vector)}f", *vector)


def unpack_vector(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


class NebiusEmbedder:
    """`Embedder` for Qwen3-Embedding-8B. Queries get the `Instruct:` prefix; documents do not."""

    def __init__(self, client: AsyncOpenAI, *, model: str, dimensions: int) -> None:
        self._client = client
        self.model = model
        self.dimensions = dimensions

    async def embed(
        self, texts: Sequence[str], *, instruction: str | None = None
    ) -> list[list[float]]:
        inputs = [
            f"Instruct: {instruction}\nQuery: {text}" if instruction else text for text in texts
        ]
        vectors: list[list[float]] = []
        for batch in batched(inputs, EMBED_BATCH_SIZE):
            try:
                response = await self._client.embeddings.create(
                    model=self.model, input=list(batch), dimensions=self.dimensions
                )
            except openai.OpenAIError as exc:
                raise _map_api_error(exc) from exc
            if len(response.data) != len(batch):
                raise _failure("invalid_response", "embedding count does not match input count")
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(fit_vector(item.embedding, self.dimensions) for item in ordered)
        return vectors


def _client(settings: Settings) -> AsyncOpenAI:
    if settings.nebius_api_key is None:
        raise _failure("not_configured", "NEBIUS_API_KEY is not set")
    return AsyncOpenAI(
        api_key=settings.nebius_api_key.get_secret_value(),
        base_url=settings.nebius_base_url,
    )


def build_chat_model(settings: Settings, http: httpx.AsyncClient) -> NebiusChatModel:
    return NebiusChatModel(_client(settings), settings)


def build_embedder(settings: Settings, http: httpx.AsyncClient) -> NebiusEmbedder:
    return NebiusEmbedder(
        _client(settings),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )
