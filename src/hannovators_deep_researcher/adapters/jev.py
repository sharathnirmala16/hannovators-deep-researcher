"""Jev System One `DecisionModel` over the Command Code Provider API (`/systemone`)."""

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import ValidationError

from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.infrastructure.resilience import RateLimited, parse_retry_after
from hannovators_deep_researcher.models.decisions import (
    MAX_CHOICE_OPTIONS,
    DecisionAnswer,
    DecisionQuestion,
)
from hannovators_deep_researcher.models.enums import DecisionQuestionType
from hannovators_deep_researcher.models.web import ProviderError, ProviderFailure

_NAME = "jev"
CHARS_PER_TOKEN = 4
MAX_RETRIES = 2
MAX_RETRY_DELAY = 30.0
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_STATUS_CODES = {
    400: "bad_request",
    401: "invalid_api_key",
    402: "payment_required",
    403: "provider_api_not_in_plan",
}


def _error(
    code: str, message: str, *, retryable: bool = False, status: int | None = None
) -> ProviderError:
    return ProviderError(
        provider=_NAME, code=code, message=message, retryable=retryable, status_code=status
    )


def _failure(
    code: str, message: str, *, retryable: bool = False, status: int | None = None
) -> ProviderFailure:
    return ProviderFailure(_error(code, message, retryable=retryable, status=status))


def truncate_state(state: str, max_tokens: int) -> str:
    """Cut a state to the token budget, estimated at 4 characters per token."""

    limit = max_tokens * CHARS_PER_TOKEN
    return state if len(state) <= limit else state[:limit]


def _check_questions(questions: Mapping[str, DecisionQuestion]) -> None:
    if not questions:
        raise _failure("bad_request", "at least one question is required")
    for key, question in questions.items():
        criteria = question.criteria
        if question.type == DecisionQuestionType.CHOICE and (
            not isinstance(criteria, dict) or len(criteria) > MAX_CHOICE_OPTIONS
        ):
            raise _failure("too_many_options", f"choice question {key!r} needs 1 to 20 options")


def _score_value(question: DecisionQuestion, raw: object) -> float | None:
    if isinstance(raw, str) and isinstance(question.criteria, list) and raw in question.criteria:
        return float(question.criteria.index(raw))
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return float(raw)
    return None


def _answer(key: str, question: DecisionQuestion, raw: object) -> DecisionAnswer:
    if not isinstance(raw, dict):
        raise _failure("invalid_response", f"answer {key!r} is not an object")
    choice = raw.get("choice")
    if question.type == DecisionQuestionType.CHOICE and (
        not isinstance(question.criteria, dict) or choice not in question.criteria
    ):
        raise _failure("invalid_response", f"answer {key!r} chose an unknown option")
    probabilities = raw.get("probabilities") or {}
    return DecisionAnswer(
        type=question.type,
        choice=choice if question.type == DecisionQuestionType.CHOICE else None,
        score=_score_value(question, raw.get("score"))
        if question.type == DecisionQuestionType.SCORE
        else None,
        noul=raw.get("noul") if question.type == DecisionQuestionType.NOUL else None,
        confidence=raw.get("confidence"),
        probabilities={str(name): float(value) for name, value in dict(probabilities).items()},
    )


class JevDecisionModel:
    """`DecisionModel` for Jev. A semaphore caps concurrent requests; 429 honors `Retry-After`."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        url: str,
        model: str,
        api_key: str,
        concurrency: int,
        max_state_tokens: int,
    ) -> None:
        self._http = http
        self._url = url
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._semaphore = asyncio.Semaphore(concurrency)
        self._max_state_tokens = max_state_tokens

    async def evaluate(
        self, state: str, questions: Mapping[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        _check_questions(questions)
        body = {
            "model": self._model,
            "state": truncate_state(state, self._max_state_tokens),
            "questions": {
                key: question.model_dump(mode="json", exclude_none=True)
                for key, question in questions.items()
            },
        }
        payload = await self._post(body)
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise _failure("invalid_response", "response has no answers object")
        missing = sorted(set(questions) - set(answers))
        if missing:
            raise _failure("invalid_response", f"missing answers: {', '.join(missing)}")
        try:
            return {
                key: _answer(key, question, answers[key]) for key, question in questions.items()
            }
        except (ValidationError, TypeError, ValueError) as exc:
            raise _failure("invalid_response", "malformed answer") from exc

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with self._semaphore:
                    response = await self._http.post(
                        self._url, json=body, headers=self._headers, timeout=_TIMEOUT
                    )
            except httpx.TimeoutException as exc:
                failure = _failure("timeout", "request timed out", retryable=True)
                if attempt == MAX_RETRIES:
                    raise failure from exc
                await asyncio.sleep(2**attempt)
                continue
            except httpx.TransportError as exc:
                raise _failure("transport_error", type(exc).__name__, retryable=True) from exc
            delay = self._retry_delay(response, attempt)
            if delay is None:
                break
            await asyncio.sleep(delay)
        return self._payload(response)

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float | None:
        status = response.status_code
        if attempt == MAX_RETRIES or (status != 429 and status < 500):
            return None
        retry_after = parse_retry_after(response.headers.get("retry-after"))
        return min(MAX_RETRY_DELAY, retry_after if retry_after is not None else 2.0**attempt)

    def _payload(self, response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status == 429:
            raise RateLimited(
                _error("rate_limited", "rate limit reached", retryable=True, status=429),
                retry_after=parse_retry_after(response.headers.get("retry-after")),
            )
        if status >= 400:
            raise _failure(
                _STATUS_CODES.get(status, "http_error"),
                f"HTTP {status}",
                retryable=status >= 500,
                status=status,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise _failure("invalid_response", "response is not JSON") from exc
        if not isinstance(payload, dict):
            raise _failure("invalid_response", "response is not a JSON object")
        return payload


def build_decision_model(settings: Settings, http: httpx.AsyncClient) -> JevDecisionModel:
    if settings.jev_api_key is None:
        raise _failure("not_configured", "JEV_API_KEY is not set")
    return JevDecisionModel(
        http,
        url=f"{settings.jev_base_url.rstrip('/')}/systemone",
        model=settings.jev_model,
        api_key=settings.jev_api_key.get_secret_value(),
        concurrency=settings.jev_concurrency,
        max_state_tokens=settings.jev_max_state_tokens,
    )
