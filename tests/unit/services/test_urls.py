"""Edge cases for URL canonicalization."""

import pytest

from hannovators_deep_researcher.services.urls import canonicalize_url

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "https://example.com/a?utm_source=x&id=2&fbclid=y&a=1&ref=feed",
            "https://example.com/a?a=1&id=2",
        ),
        ("https://WWW.Example.com/a", "https://example.com/a"),
        ("http://example.com:80/a", "https://example.com/a"),
        ("https://example.com:443/a", "https://example.com/a"),
        ("https://example.com:8443/a", "https://example.com:8443/a"),
        ("https://example.com/a/#section", "https://example.com/a"),
    ],
)
def test_canonicalize_url(raw: str, expected: str) -> None:
    assert canonicalize_url(raw) == expected
