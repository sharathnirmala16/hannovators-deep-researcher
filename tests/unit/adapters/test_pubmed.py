"""PubMed efetch parsing edge cases."""

import pytest

from hannovators_deep_researcher.adapters.pubmed import parse_efetch_xml
from hannovators_deep_researcher.models.web import ProviderFailure

pytestmark = pytest.mark.unit

XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation><PMID>111</PMID><Article>
      <Journal><Title>Trials</Title><JournalIssue><PubDate>
        <MedlineDate>2019 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>
      <ArticleTitle>A <i>randomized</i> trial</ArticleTitle>
      <Abstract>
        <AbstractText Label="BACKGROUND">Why.</AbstractText>
        <AbstractText Label="RESULTS">2/70 vs 8/53.</AbstractText>
      </Abstract>
      <AuthorList><Author><LastName>Doe</LastName><Initials>J</Initials></Author></AuthorList>
    </Article></MedlineCitation>
    <PubmedData><ArticleIdList>
      <ArticleId IdType="doi">10.1/x</ArticleId></ArticleIdList></PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation><PMID>222</PMID>
      <Article><ArticleTitle>No abstract</ArticleTitle></Article></MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


def test_structured_sections_join_in_order_and_missing_abstract_is_none() -> None:
    first, second = parse_efetch_xml(XML)

    assert first.abstract == "BACKGROUND: Why.\nRESULTS: 2/70 vs 8/53."
    assert (first.title, first.year, first.doi, first.authors) == (
        "A randomized trial",
        2019,
        "10.1/x",
        ["Doe J"],
    )
    assert second.abstract is None


def test_malformed_xml_raises_typed_error() -> None:
    with pytest.raises(ProviderFailure, match="malformed XML"):
        parse_efetch_xml("<PubmedArticleSet><PubmedArticle>")
