"""PubMed E-utilities `LiteratureSearch`: esearch for counts and IDs, efetch XML for records."""

import asyncio
import re
import time
from collections.abc import Sequence
from typing import Any
from xml.etree.ElementTree import Element, ParseError

import httpx
from defusedxml import ElementTree  # type: ignore[import-untyped]

from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.models.enums import SourceOrigin
from hannovators_deep_researcher.models.literature import CandidateRecord, SourceLinkRecord
from hannovators_deep_researcher.models.web import ProviderError, ProviderFailure

_NAME = "pubmed"
EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RATE_WITHOUT_KEY = 3.0
RATE_WITH_KEY = 10.0
EFETCH_BATCH = 200
_TOOL = "hannovators-deep-researcher"
_YEAR = re.compile(r"\d{4}")


def _failure(
    code: str, message: str, *, retryable: bool = False, status: int | None = None
) -> ProviderFailure:
    return ProviderFailure(
        ProviderError(
            provider=_NAME, code=code, message=message, retryable=retryable, status_code=status
        )
    )


class _Throttle:
    """Space request starts at least `1 / rate` seconds apart."""

    def __init__(self, rate: float) -> None:
        self._interval = 1.0 / rate
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
            self._next = max(now, self._next) + self._interval


def _text(element: Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _abstract(article: Element) -> str | None:
    sections = []
    for part in article.findall("./Abstract/AbstractText"):
        text = _text(part)
        if not text:
            continue
        label = part.get("Label")
        sections.append(f"{label}: {text}" if label else text)
    return "\n".join(sections) or None


def _authors(article: Element) -> list[str]:
    names = []
    for author in article.findall("./AuthorList/Author"):
        collective = _text(author.find("CollectiveName"))
        last = _text(author.find("LastName"))
        initials = _text(author.find("Initials"))
        name = collective or " ".join(part for part in (last, initials) if part)
        if name:
            names.append(name)
    return names


def _year(article: Element) -> int | None:
    pub_date = article.find("./Journal/JournalIssue/PubDate")
    match = _YEAR.search(_text(pub_date))
    return int(match.group()) if match else None


def _record(node: Element) -> CandidateRecord | None:
    citation = node.find("MedlineCitation")
    article = citation.find("Article") if citation is not None else None
    pmid = _text(citation.find("PMID")) if citation is not None else ""
    if article is None or not pmid:
        return None
    ids = {
        item.get("IdType"): _text(item)
        for item in node.findall("./PubmedData/ArticleIdList/ArticleId")
    }
    return CandidateRecord(
        origin=SourceOrigin.PUBMED,
        external_id=pmid,
        title=_text(article.find("ArticleTitle")) or f"PMID {pmid}",
        abstract=_abstract(article),
        authors=_authors(article),
        year=_year(article),
        venue=_text(article.find("./Journal/Title")) or None,
        doi=ids.get("doi") or None,
        pmid=pmid,
        pmcid=ids.get("pmc") or None,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        publication_types=[
            _text(item) for item in article.findall("./PublicationTypeList/PublicationType")
        ],
    )


def parse_efetch_xml(xml: str | bytes) -> list[CandidateRecord]:
    """Turn an efetch `PubmedArticleSet` into records. Malformed XML raises `ProviderFailure`."""

    try:
        root = ElementTree.fromstring(xml)
    except ParseError as exc:
        raise _failure("invalid_response", "efetch returned malformed XML") from exc
    records = (_record(node) for node in root.iter("PubmedArticle"))
    return [record for record in records if record is not None]


class PubMedSearch:
    """`LiteratureSearch` over NCBI E-utilities with a client-side rate limit."""

    def __init__(
        self, http: httpx.AsyncClient, *, api_key: str | None = None, email: str | None = None
    ) -> None:
        self._http = http
        self._throttle = _Throttle(RATE_WITH_KEY if api_key else RATE_WITHOUT_KEY)
        self._common: dict[str, str] = {"tool": _TOOL}
        if api_key:
            self._common["api_key"] = api_key
        if email:
            self._common["email"] = email

    async def count(self, query: str) -> int:
        result = await self._esearch(query, retmax=0)
        return int(result.get("count", 0))

    async def search(self, query: str, *, limit: int) -> list[CandidateRecord]:
        result = await self._esearch(query, retmax=limit)
        return await self.fetch([str(pmid) for pmid in result.get("idlist", [])])

    async def fetch(self, pmids: Sequence[str]) -> list[CandidateRecord]:
        records: list[CandidateRecord] = []
        for start in range(0, len(pmids), EFETCH_BATCH):
            batch = ",".join(pmids[start : start + EFETCH_BATCH])
            response = await self._get(
                "efetch.fcgi", {"db": "pubmed", "id": batch, "retmode": "xml"}
            )
            records.extend(parse_efetch_xml(response.content))
        return records

    async def related(self, external_ids: Sequence[str], *, limit: int) -> list[SourceLinkRecord]:
        return []

    async def open_access_pdf_url(self, record: CandidateRecord) -> str | None:
        return None

    async def _esearch(self, query: str, *, retmax: int) -> dict[str, Any]:
        params = {"db": "pubmed", "term": query, "retmax": str(retmax), "retmode": "json"}
        response = await self._get("esearch.fcgi", params)
        try:
            result = response.json()["esearchresult"]
        except (ValueError, KeyError, TypeError) as exc:
            raise _failure("invalid_response", "malformed esearch response") from exc
        if not isinstance(result, dict) or "ERROR" in result:
            raise _failure("invalid_response", "esearch returned an error")
        return result

    async def _get(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        await self._throttle.wait()
        try:
            response = await self._http.get(
                f"{EUTILS_URL}/{endpoint}", params={**params, **self._common}
            )
        except httpx.TimeoutException as exc:
            raise _failure("timeout", "request timed out", retryable=True) from exc
        except httpx.TransportError as exc:
            raise _failure("transport_error", type(exc).__name__, retryable=True) from exc
        if response.status_code >= 400:
            status = response.status_code
            raise _failure(
                "http_error",
                f"HTTP {status}",
                retryable=status in {429, 500, 502, 503, 504},
                status=status,
            )
        return response


def build_literature_search(settings: Settings, http: httpx.AsyncClient) -> PubMedSearch:
    api_key = settings.ncbi_api_key.get_secret_value() if settings.ncbi_api_key else None
    return PubMedSearch(http, api_key=api_key, email=settings.ncbi_email)
