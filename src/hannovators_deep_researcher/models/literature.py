"""Literature search records returned by PubMed and Europe PMC adapters."""

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.enums import SourceLinkKind, SourceOrigin


class CandidateRecord(ContractModel):
    """A candidate source. `external_id` is the PMID, DOI, or canonical URL."""

    origin: SourceOrigin
    external_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    publication_types: list[str] = Field(default_factory=list)


class SourceLinkRecord(ContractModel):
    from_external_id: str
    to_external_id: str
    kind: SourceLinkKind
