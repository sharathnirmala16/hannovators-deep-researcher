"""Every error body is `{"detail": {"code": "<UPPER_SNAKE>", "message": "<text>"}}`."""

import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from hannovators_deep_researcher.models.contracts import ApiError, ApiErrorDetail
from hannovators_deep_researcher.services.pipeline.orchestrator import RunStateError
from hannovators_deep_researcher.services.workspace_deletion import WorkspaceBusyError
from hannovators_deep_researcher.services.workspace_state import (
    WorkspaceNotFoundError,
    WorkspaceStatusError,
)

logger = logging.getLogger(__name__)


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


def _response(
    status: int, code: str, message: str, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    body = ApiError(detail=ApiErrorDetail(code=code, message=message))
    return JSONResponse(body.model_dump(), status_code=status, headers=headers)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail
    if isinstance(detail, dict) and {"code", "message"} <= detail.keys():
        code, message = str(detail["code"]), str(detail["message"])
    else:
        code, message = HTTPStatus(exc.status_code).name, str(detail)
    return _response(exc.status_code, code, message, exc.headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    parts = [
        f"{'.'.join(str(item) for item in error.get('loc', ()))}: {error.get('msg', 'invalid')}"
        for error in exc.errors()
    ]
    return _response(422, "VALIDATION_ERROR", "; ".join(parts) or "invalid request")


async def _not_found(_: Request, exc: Exception) -> JSONResponse:
    return _response(404, "WORKSPACE_NOT_FOUND", str(exc))


async def _run_state(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RunStateError)
    code = "WORKSPACE_RUNNING" if exc.status == "RUNNING" else "WORKSPACE_NOT_RUNNABLE"
    return _response(409, code, str(exc))


async def _busy(_: Request, exc: Exception) -> JSONResponse:
    return _response(409, "WORKSPACE_RUNNING", str(exc))


async def _status_error(_: Request, exc: Exception) -> JSONResponse:
    return _response(409, "WORKSPACE_NOT_AWAITING_REVIEW", str(exc))


async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled API error", exc_info=exc)
    return _response(500, "INTERNAL_ERROR", f"{type(exc).__name__}: see the server log")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Exception, _unexpected)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(WorkspaceNotFoundError, _not_found)
    app.add_exception_handler(RunStateError, _run_state)
    app.add_exception_handler(WorkspaceStatusError, _status_error)
    app.add_exception_handler(WorkspaceBusyError, _busy)
