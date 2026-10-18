"""Shared `httpx.AsyncClient` factory with the project's timeout, pool, and header defaults."""

from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_LIMITS = httpx.Limits(max_connections=50, max_keepalive_connections=20)


def _user_agent() -> str:
    try:
        package_version = version("hannovators-deep-researcher")
    except PackageNotFoundError:
        package_version = "0"
    return f"hannovators-deep-researcher/{package_version}"


USER_AGENT = _user_agent()


def create_http_client(
    *,
    base_url: str = "",
    headers: Mapping[str, str] | None = None,
    timeout: httpx.Timeout | float | None = None,
    limits: httpx.Limits | None = None,
    follow_redirects: bool = True,
) -> httpx.AsyncClient:
    """Create an AsyncClient. The caller owns it: close it with `aclose()` or `async with`.

    Pass API keys through `headers`; this module never logs header values.
    """

    merged_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    return httpx.AsyncClient(
        base_url=base_url,
        headers=merged_headers,
        timeout=DEFAULT_TIMEOUT if timeout is None else timeout,
        limits=limits or DEFAULT_LIMITS,
        follow_redirects=follow_redirects,
    )
