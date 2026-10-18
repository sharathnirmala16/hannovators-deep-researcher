"""Fake PubMed and Europe PMC: canned records, canned links, and one bundled open-access PDF."""

from collections.abc import Sequence
from functools import cache
from typing import TYPE_CHECKING

import httpx

from hannovators_deep_researcher.adapters.fake.catalog import DATA_DIR, all_links, match_records
from hannovators_deep_researcher.models.enums import SourceOrigin
from hannovators_deep_researcher.models.literature import CandidateRecord, SourceLinkRecord

if TYPE_CHECKING:
    from hannovators_deep_researcher.models.ports import LiteratureSearch

FAKE_PDF_PATH = DATA_DIR / "fake_trial.pdf"
# `.invalid` never resolves (RFC 2606), so a fake URL can never reach a real host.
FAKE_OA_HOST = "fake-oa.invalid"
FAKE_OA_BASE_URL = f"https://{FAKE_OA_HOST}/pdf/"
_LITERATURE_ORIGINS = frozenset({SourceOrigin.PUBMED, SourceOrigin.EUROPEPMC})


class FakeLiteratureSearch:
    """Implements the `LiteratureSearch` port over the canned PUBMED and EUROPEPMC records.

    A query that names a PMID, PMCID, or DOI returns that record, as PubMed does.
    """

    async def count(self, query: str) -> int:
        return len(match_records(query, _LITERATURE_ORIGINS))

    async def search(self, query: str, *, limit: int) -> list[CandidateRecord]:
        return [item.record for item in match_records(query, _LITERATURE_ORIGINS)[:limit]]

    async def related(self, external_ids: Sequence[str], *, limit: int) -> list[SourceLinkRecord]:
        """Canned links that start or end at one of `external_ids` (cites and cited-by)."""

        wanted = set(external_ids)
        links = [
            link
            for link in all_links()
            if link.from_external_id in wanted or link.to_external_id in wanted
        ]
        return links[:limit]

    async def open_access_pdf_url(self, record: CandidateRecord) -> str | None:
        """The record's PDF URL, else a fake URL for any record with a PMCID."""

        if record.pdf_url:
            return record.pdf_url
        return fake_pdf_url(record.pmcid) if record.pmcid else None


def fake_pdf_url(key: str) -> str:
    return f"{FAKE_OA_BASE_URL}{key}.pdf"


@cache
def fake_pdf_bytes() -> bytes:
    """The bundled text-layer PDF that every fake open-access URL serves."""

    return FAKE_PDF_PATH.read_bytes()


def fake_http_transport() -> httpx.MockTransport:
    """An httpx transport that serves `fake_pdf_bytes()` for fake OA URLs and 404 otherwise."""

    def handle(request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.host == FAKE_OA_HOST and url.path.startswith("/pdf/") and url.path.endswith(".pdf"):
            return httpx.Response(
                200, content=fake_pdf_bytes(), headers={"Content-Type": "application/pdf"}
            )
        return httpx.Response(404, text=f"no fake resource at {url}")

    return httpx.MockTransport(handle)


if TYPE_CHECKING:
    _literature_search: LiteratureSearch = FakeLiteratureSearch()
