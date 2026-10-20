"""Open-access PDF lookup: Europe PMC record -> PMC open data on AWS -> Unpaywall.

Europe PMC's `?pdf=render` and PMC's own `/pdf/` links sit behind bot challenges (HTTP 403 or a
proof-of-work page) for non-browser clients, so they are never returned. In order:

1. The record's own `pdf_url`.
2. The PMC Article Datasets copy on AWS (`<PMCID>.<v>/<PMCID>.<v>.pdf`, open, no challenge) for
   the PMCID that Europe PMC (or the record) names.
3. Unpaywall repository copies (institutional repositories and preprint servers download well).
4. Open PDF links from the Europe PMC `fullTextUrlList` on other hosts.
5. Unpaywall publisher copies (often blocked, but sometimes open).

Every lookup error returns None: a missing PDF never fails a run.
"""

import logging
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from hannovators_deep_researcher.models.literature import CandidateRecord

logger = logging.getLogger(__name__)

EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PMC_OPENDATA_URL = "https://pmc-oa-opendata.s3.amazonaws.com/"
UNPAYWALL_URL = "https://api.unpaywall.org/v2/"
UNPAYWALL_FALLBACK_EMAIL = "deep-researcher@hannovators.invalid"
"""Unpaywall wants a contact address; NCBI_EMAIL is used when it is set."""

_OPEN_AVAILABILITY = frozenset({"OA", "F"})
_PMC_PDF_KEY = re.compile(r"<Key>((PMC\d+)\.(\d+)/\2\.\3\.pdf)</Key>")
BLOCKED_HOSTS = ("europepmc.org", "pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov")
"""Hosts whose PDF links answer non-browser clients with a bot challenge."""


def is_blocked(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == blocked or host.endswith(f".{blocked}") for blocked in BLOCKED_HOSTS)


def europepmc_query(record: CandidateRecord) -> str | None:
    """The Europe PMC search query that finds this record: PMID, else PMCID, else DOI."""

    if record.pmid:
        return f"EXT_ID:{record.pmid} AND SRC:MED"
    if record.pmcid:
        return f"PMCID:{record.pmcid}"
    if record.doi:
        return f'DOI:"{record.doi}"'
    return None


def _first_result(payload: object) -> dict[str, Any] | None:
    result_list = payload.get("resultList") if isinstance(payload, dict) else None
    results = result_list.get("result") if isinstance(result_list, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        return None
    return results[0]


def open_pdf_links(result: dict[str, Any]) -> list[str]:
    """Open or free PDF links of a Europe PMC result, minus bot-challenged hosts."""

    url_list = result.get("fullTextUrlList")
    entries = url_list.get("fullTextUrl") if isinstance(url_list, dict) else None
    links: list[str] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if (
            isinstance(url, str)
            and entry.get("documentStyle") == "pdf"
            and entry.get("availabilityCode") in _OPEN_AVAILABILITY
            and not is_blocked(url)
        ):
            links.append(url)
    return links


def europepmc_ids(payload: object) -> tuple[str | None, str | None, list[str]]:
    """`(pmcid, doi, open PDF links)` from a Europe PMC `resultType=core` reply.

    Malformed replies give `(None, None, [])`.
    """

    result = _first_result(payload)
    if result is None:
        return None, None, []
    pmcid = result.get("pmcid")
    doi = result.get("doi")
    return (
        pmcid if isinstance(pmcid, str) and pmcid.startswith("PMC") else None,
        doi if isinstance(doi, str) and doi.strip() else None,
        open_pdf_links(result),
    )


def pmc_opendata_pdf_url(listing: str, pmcid: str) -> str | None:
    """The newest `<PMCID>.<v>/<PMCID>.<v>.pdf` key in a PMC open-data S3 listing, as a URL."""

    versions = [
        (int(match.group(3)), match.group(1))
        for match in _PMC_PDF_KEY.finditer(listing)
        if match.group(2) == pmcid
    ]
    return f"{PMC_OPENDATA_URL}{max(versions)[1]}" if versions else None


def unpaywall_pdf_urls(payload: object) -> tuple[list[str], list[str]]:
    """`(repository PDF URLs, publisher PDF URLs)` of an Unpaywall reply, best first."""

    locations = payload.get("oa_locations") if isinstance(payload, dict) else None
    repository: list[str] = []
    publisher: list[str] = []
    for location in locations if isinstance(locations, list) else []:
        if not isinstance(location, dict):
            continue
        url = location.get("url_for_pdf")
        if not isinstance(url, str) or not url.startswith("http") or is_blocked(url):
            continue
        (repository if location.get("host_type") == "repository" else publisher).append(url)
    return repository, publisher


class OpenAccessPdfFinder:
    """Finds a downloadable open-access PDF URL for a literature record."""

    def __init__(self, http: httpx.AsyncClient, *, email: str | None = None) -> None:
        self._http = http
        self._email = email or UNPAYWALL_FALLBACK_EMAIL

    async def pdf_url(self, record: CandidateRecord) -> str | None:
        if record.pdf_url and not is_blocked(record.pdf_url):
            return record.pdf_url
        pmcid, doi, links = await self._europepmc(record)
        pmcid = pmcid or record.pmcid
        if pmcid:
            opendata = await self._opendata_pdf(pmcid)
            if opendata:
                return opendata
        repository, publisher = await self._unpaywall(record.doi or doi)
        candidates = [*repository, *links, *publisher]
        return candidates[0] if candidates else None

    async def _get_json(self, url: str, params: dict[str, str]) -> object | None:
        try:
            response = await self._http.get(url, params=params)
        except httpx.HTTPError as error:
            logger.warning("Open-access lookup %s failed: %s", url, type(error).__name__)
            return None
        if response.status_code >= 400:
            logger.info("Open-access lookup %s returned HTTP %s", url, response.status_code)
            return None
        try:
            payload: object = response.json()
        except ValueError:
            return None
        return payload

    async def _europepmc(self, record: CandidateRecord) -> tuple[str | None, str | None, list[str]]:
        query = europepmc_query(record)
        if query is None:
            return None, None, []
        params = {"query": query, "resultType": "core", "format": "json", "pageSize": "1"}
        return europepmc_ids(await self._get_json(EUROPEPMC_SEARCH_URL, params))

    async def _opendata_pdf(self, pmcid: str) -> str | None:
        params = {"list-type": "2", "prefix": f"{pmcid}."}
        try:
            response = await self._http.get(PMC_OPENDATA_URL, params=params)
        except httpx.HTTPError as error:
            logger.warning("PMC open-data listing failed for %s: %s", pmcid, type(error).__name__)
            return None
        if response.status_code >= 400:
            return None
        return pmc_opendata_pdf_url(response.text, pmcid)

    async def _unpaywall(self, doi: str | None) -> tuple[list[str], list[str]]:
        if not doi:
            return [], []
        payload = await self._get_json(f"{UNPAYWALL_URL}{doi.strip()}", {"email": self._email})
        return unpaywall_pdf_urls(payload)
