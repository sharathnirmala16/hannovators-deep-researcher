"""PubMed E-utilities `LiteratureSearch`: esearch for counts and IDs, efetch XML for records,
elink for similar and referenced articles.

Every E-utilities request goes through one process-wide token bucket (NCBI allows 3 requests/s
without `NCBI_API_KEY` and 10 with it; the bucket stays below both) and retries HTTP 429, 5xx,
timeouts, and transport errors with backoff, honoring `Retry-After`. A 429 pauses the shared
bucket, so all concurrent queries back off together.
"""

import logging
import re
from collections.abc import Mapping, Sequence
from itertools import chain, zip_longest
from typing import Any
from xml.etree.ElementTree import Element, ParseError

import httpx
from defusedxml import ElementTree  # type: ignore[import-untyped]

from hannovators_deep_researcher.adapters.europepmc import OpenAccessPdfFinder
from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.infrastructure.rate_limit import TokenBucket, shared_bucket
from hannovators_deep_researcher.infrastructure.resilience import (
    RateLimited,
    ResilientRunner,
    parse_retry_after,
)
from hannovators_deep_researcher.models.enums import SourceLinkKind, SourceOrigin
from hannovators_deep_researcher.models.literature import CandidateRecord, SourceLinkRecord
from hannovators_deep_researcher.models.web import ProviderError, ProviderFailure

_NAME = "pubmed"
EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# Slightly under NCBI's 3 and 10 requests/s, so clock jitter never crosses the limit.
RATE_WITHOUT_KEY = 2.5
RATE_WITH_KEY = 8.0
BUCKET_NAME = "ncbi-eutils"
MAX_ATTEMPTS = 5
RETRY_BASE_SECONDS = 1.0
RETRY_MAX_SECONDS = 30.0
RATE_LIMIT_PAUSE_SECONDS = 1.5
RETRYABLE_STATUS = frozenset({500, 502, 503, 504})
EFETCH_BATCH = 200
SIMILAR_LINK = "pubmed_pubmed"
REFERENCES_LINK = "pubmed_pubmed_refs"
_TOOL = "hannovators-deep-researcher"
_YEAR = re.compile(r"\d{4}")

logger = logging.getLogger(__name__)


def _failure(
    code: str, message: str, *, retryable: bool = False, status: int | None = None
) -> ProviderFailure:
    return ProviderFailure(
        ProviderError(
            provider=_NAME, code=code, message=message, retryable=retryable, status_code=status
        )
    )


def _retryable(status: int, retry_after: float | None) -> RateLimited:
    return RateLimited(
        ProviderError(
            provider=_NAME,
            code="rate_limited" if status == 429 else "http_error",
            message=f"HTTP {status}",
            retryable=True,
            status_code=status,
        ),
        retry_after=retry_after,
    )


def _is_rate_limit_body(response: httpx.Response) -> bool:
    """NCBI sometimes answers HTTP 200 with `{"error": "API rate limit exceeded"}`."""

    return b"rate limit exceeded" in response.content[:300].lower()


def _link(source: str, target: str, kind: SourceLinkKind) -> SourceLinkRecord:
    return SourceLinkRecord(from_external_id=source, to_external_id=target, kind=kind)


def elink_ids(payload: object, linkname: str) -> dict[str, list[str]]:
    """Map each source PMID to its linked PMIDs (NCBI order) from an elink JSON reply.

    Malformed replies give an empty map.
    """

    linksets = payload.get("linksets") if isinstance(payload, dict) else None
    linked: dict[str, list[str]] = {}
    for linkset in linksets if isinstance(linksets, list) else []:
        ids = linkset.get("ids") if isinstance(linkset, dict) else None
        if not isinstance(ids, list) or not ids:
            continue
        for group in linkset.get("linksetdbs") or []:
            if isinstance(group, dict) and group.get("linkname") == linkname:
                links = group.get("links")
                linked[str(ids[0])] = [str(item) for item in links or []]
    return linked


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
        self._bucket: TokenBucket = shared_bucket(
            BUCKET_NAME, RATE_WITH_KEY if api_key else RATE_WITHOUT_KEY
        )
        # The circuit stays effectively closed: the bucket and retries handle throttling.
        self._runner = ResilientRunner(
            max_attempts=MAX_ATTEMPTS,
            base_delay=RETRY_BASE_SECONDS,
            max_delay=RETRY_MAX_SECONDS,
            circuit_failure_threshold=1_000,
        )
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
        """Similar articles (RELATED) and references (seed CITES reference) of PubMed IDs.

        Links alternate between the seeds, most similar first, so `limit` keeps a share of
        each seed. Non-numeric IDs are ignored.
        """

        pmids = list(dict.fromkeys(item for item in external_ids if item.isdigit()))
        if not pmids or limit <= 0:
            return []
        per_seed = max(1, limit // len(pmids))
        similar = await self._elink(pmids, SIMILAR_LINK)
        references = await self._elink(pmids, REFERENCES_LINK)
        rows: list[list[SourceLinkRecord]] = []
        for pmid in pmids:
            near = [item for item in similar.get(pmid, []) if item != pmid][:per_seed]
            refs = references.get(pmid, [])[: max(1, per_seed // 2)]
            rows.append(
                [_link(pmid, item, SourceLinkKind.RELATED) for item in near]
                + [_link(pmid, item, SourceLinkKind.CITES) for item in refs]
            )
        merged = chain.from_iterable(zip_longest(*rows))
        return [link for link in merged if link is not None][:limit]

    async def _elink(self, pmids: Sequence[str], linkname: str) -> dict[str, list[str]]:
        # One `id` parameter per PMID makes NCBI return one linkset per seed.
        params: dict[str, str | list[str]] = {
            "dbfrom": "pubmed",
            "db": "pubmed",
            "id": list(pmids),
            "linkname": linkname,
            "retmode": "json",
        }
        response = await self._get("elink.fcgi", params)
        try:
            return elink_ids(response.json(), linkname)
        except ValueError as exc:
            raise _failure("invalid_response", "malformed elink response") from exc

    async def open_access_pdf_url(self, record: CandidateRecord) -> str | None:
        """A downloadable open-access PDF URL (`adapters/europepmc.py`), or None."""

        finder = OpenAccessPdfFinder(self._http, email=self._common.get("email"))
        return await finder.pdf_url(record)

    async def _esearch(self, query: str, *, retmax: int) -> dict[str, Any]:
        # "Best match" order: the default (most recent first) fills a small budget with the
        # newest records instead of the landmark trials and reviews.
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": str(retmax),
            "retmode": "json",
            "sort": "relevance",
        }
        response = await self._get("esearch.fcgi", params)
        try:
            result = response.json()["esearchresult"]
        except (ValueError, KeyError, TypeError) as exc:
            raise _failure("invalid_response", "malformed esearch response") from exc
        if not isinstance(result, dict) or "ERROR" in result:
            raise _failure("invalid_response", "esearch returned an error")
        return result

    async def _get(self, endpoint: str, params: Mapping[str, str | list[str]]) -> httpx.Response:
        """One E-utilities GET through the shared bucket, retried on throttling and 5xx."""

        return await self._runner.run(_NAME, lambda: self._get_once(endpoint, params))

    async def _get_once(
        self, endpoint: str, params: Mapping[str, str | list[str]]
    ) -> httpx.Response:
        await self._bucket.acquire()
        try:
            response = await self._http.get(
                f"{EUTILS_URL}/{endpoint}", params={**params, **self._common}
            )
        except httpx.TimeoutException as exc:
            raise _failure("timeout", "request timed out", retryable=True) from exc
        except httpx.TransportError as exc:
            raise _failure("transport_error", type(exc).__name__, retryable=True) from exc
        status = response.status_code
        if status == 429 or (status < 400 and _is_rate_limit_body(response)):
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            pause = RATE_LIMIT_PAUSE_SECONDS if retry_after is None else retry_after
            self._bucket.pause(pause)
            logger.info("NCBI rate limit hit on %s; pausing %.1f s", endpoint, pause)
            raise _retryable(429, pause)
        if status in RETRYABLE_STATUS:
            raise _retryable(status, parse_retry_after(response.headers.get("retry-after")))
        if status >= 400:
            raise _failure("http_error", f"HTTP {status}", status=status)
        return response


def build_literature_search(settings: Settings, http: httpx.AsyncClient) -> PubMedSearch:
    api_key = settings.ncbi_api_key.get_secret_value() if settings.ncbi_api_key else None
    return PubMedSearch(http, api_key=api_key, email=settings.ncbi_email)
