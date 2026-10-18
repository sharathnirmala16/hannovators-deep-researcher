"""URL canonicalization for deduplicating web results and source external IDs."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "msclkid",
        "twclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "ref_url",
        "_hsenc",
        "_hsmi",
        "__hssc",
        "__hstc",
        "hscpsshared",
    }
)
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _is_tracking(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("utm_") or lowered in _TRACKING_PARAMS


def _netloc(scheme: str, netloc: str) -> str:
    parts = urlsplit(f"//{netloc}")
    try:
        port = parts.port
    except ValueError:
        return netloc.lower().removeprefix("www.")
    host = (parts.hostname or "").removeprefix("www.")
    if ":" in host:
        host = f"[{host}]"
    if port is not None and port != _DEFAULT_PORTS.get(scheme):
        host = f"{host}:{port}"
    return host


def canonicalize_url(url: str) -> str:
    """Return one canonical form per page, so the same hit from two queries dedupes.

    Lowercases the scheme and host, maps http to https, strips `www.`, the scheme's default
    port, user info, the fragment, a trailing path slash, and tracking parameters (`utm_*`,
    click IDs, referral tokens), and sorts the remaining query parameters.
    """

    raw = url.strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    netloc = _netloc(scheme, parts.netloc)
    if scheme == "http":
        scheme = "https"
    path = parts.path.rstrip("/") or "/"
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking(key)
    )
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))
