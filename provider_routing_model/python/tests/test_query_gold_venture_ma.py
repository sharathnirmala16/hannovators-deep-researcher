"""Focused offline checks for source-field validation and direct announcement queries."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib import error, request

from query_gold.categories import venture_ma
from query_gold.categories.venture_ma_dates import extract_tagged_publication_date
from query_gold.categories.venture_ma_deals import (
    _M_AND_A_BACKUPS as ma_backups,
)
from query_gold.categories.venture_ma_deals import (
    _M_AND_A_SOURCES as ma_sources,
)
from query_gold.categories.venture_ma_facts import (
    _FUNDING_BACKUPS as funding_backups,
)
from query_gold.categories.venture_ma_facts import (
    _FUNDING_SOURCES as funding_sources,
)
from query_gold.categories.venture_ma_facts import (
    SourceSpec,
    _money,
    _text,
)
from query_gold.categories.venture_ma_money import _parse_money_token


class VentureMaCurationTests(unittest.TestCase):
    def test_money_parser_normalizes_scale_and_currency(self) -> None:
        self.assertEqual(
            _parse_money_token("$1.25 billion"),
            (Decimal("1250000000.00"), "USD"),
        )
        self.assertEqual(
            _parse_money_token("$800m"),
            (Decimal("800000000"), "USD"),
        )

    def test_publication_date_extractor_uses_published_not_modified_date(self) -> None:
        self.assertEqual(
            extract_tagged_publication_date(
                '<meta property="article:modified_time" content="2026-10-16">'
                '<time datetime="2024-06-10">June 10</time>'
            ),
            "2024-06-10",
        )
        self.assertIsNone(
            extract_tagged_publication_date(
                '<meta property="article:modified_time" content="2026-10-16">'
            )
        )

    def test_curated_facts_are_literal_field_mappings_and_direct_queries(self) -> None:
        sources = (
            *funding_sources,
            *funding_backups,
            *ma_sources,
            *ma_backups,
        )
        self.assertGreaterEqual(len(sources), 25)
        for source in sources:
            date_value = source.published_at or "2026-09-16"
            for fact in source.facts:
                with self.subTest(source=source.source_record_id, question_type=fact.question_type):
                    venture_ma._validate_fact_spec(fact, fact.excerpt)
                    query = fact.question.format(date=date_value)
                    venture_ma._validate_query_shape(query, fact, date_value)
                    self.assertIn(date_value, query)
                    self.assertNotIn(fact.answer.casefold(), query.casefold())

    def test_wrong_numeric_field_is_rejected_even_when_amount_occurs_in_excerpt(self) -> None:
        excerpt = (
            "The issuer raised $10 million in its financing round. "
            "Its post-money valuation was $100 million."
        )
        correct = _money(
            "How much did the issuer raise in 2024?",
            "$10 million",
            "$10 million",
            10_000_000,
            "USD funding round size",
            excerpt,
            "funding_round_size",
            ("raised", "financing round"),
        )
        venture_ma._validate_fact_spec(correct, excerpt)

        wrong_field = _money(
            "How much did the issuer raise in 2024?",
            "$100 million",
            "$100 million",
            100_000_000,
            "USD funding round size",
            excerpt,
            "funding_round_size",
            ("raised", "financing round"),
        )
        with self.assertRaisesRegex(ValueError, "different source field"):
            venture_ma._validate_fact_spec(wrong_field, excerpt)

    def test_source_date_mismatch_is_rejected(self) -> None:
        source = SourceSpec(
            source_record_id="date-fixture",
            kind="funding",
            source_family="official_funding_announcement",
            title="Date fixture announcement",
            url="https://issuer.example/announcement",
            facts=(
                _text(
                    "Which investor led the round announced on {date}?",
                    "Example Capital",
                    "The round was led by Example Capital.",
                    "funding_lead_investor",
                    context_terms=("led",),
                ),
            ),
            published_at="2024-06-10",
            date_tokens=("June 10, 2024",),
        )
        wrong_date = (
            b'<meta property="article:published_time" content="2024-06-09">'
            b"The round was led by Example Capital."
        )
        with self.assertRaisesRegex(ValueError, "does not support the curated publication date"):
            venture_ma._validate_source_facts(source, wrong_date)

    def test_wrong_currency_or_units_are_rejected(self) -> None:
        excerpt = "The company raised $10 million in the financing round."
        wrong_currency = _money(
            "How much did the company raise in 2024?",
            "$10 million",
            "$10 million",
            10_000_000,
            "EUR funding round size",
            excerpt,
            "funding_round_size",
            ("raised", "financing round"),
            currency="EUR",
        )
        with self.assertRaisesRegex(ValueError, "currency disagree"):
            venture_ma._validate_fact_spec(wrong_currency, excerpt)

        wrong_units = _money(
            "How much did the company raise in 2024?",
            "$10 million",
            "$10 million",
            10_000_000,
            "shares per target share",
            excerpt,
            "funding_round_size",
            ("raised", "financing round"),
        )
        with self.assertRaisesRegex(ValueError, "units must explicitly name"):
            venture_ma._validate_fact_spec(wrong_units, excerpt)

    def test_context_dependent_compound_and_derived_queries_are_rejected(self) -> None:
        fact = funding_sources[0].facts[0]
        red_flags = (
            "How much did this company raise in 2023-05-23?",
            "How much did Anthropic raise in 2023-05-23 and what was its valuation?",
            "What is the difference between the announced and completed amount on 2023-05-23?",
        )
        for query in red_flags:
            with self.subTest(query=query), self.assertRaises(ValueError):
                venture_ma._validate_query_shape(query, fact, "2023-05-23")

    def test_redirects_fail_closed_and_each_physical_attempt_is_logged(self) -> None:
        source = funding_sources[0]

        class RedirectingOpener:
            def open(self, request: object, timeout: int) -> object:
                del timeout
                raise error.HTTPError(
                    source.url,
                    302,
                    "Found",
                    Message(),
                    None,
                )

        seen_handlers: list[object] = []

        def build_opener(*handlers: object) -> RedirectingOpener:
            seen_handlers.extend(handlers)
            return RedirectingOpener()

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            state = venture_ma._load_request_ledger(output)
            with (
                patch.object(
                    request,
                    "build_opener",
                    side_effect=build_opener,
                ) as mocked_build_opener,
                self.assertRaisesRegex(RuntimeError, "HTTP 302"),
            ):
                venture_ma._download_source(source, state, output)

            ledger = json.loads((output / "raw" / "collection-attempts.json").read_text())
            attempts = ledger["physicalAttempts"]
            self.assertEqual(len(attempts), 2)
            self.assertEqual([row["outcome"] for row in attempts], ["HTTP 302", "HTTP 302"])
            self.assertEqual(mocked_build_opener.call_count, 2)
            self.assertEqual(len(seen_handlers), 2)
            self.assertTrue(
                all(
                    isinstance(handler, venture_ma._RejectRedirectHandler)
                    for handler in seen_handlers
                )
            )

    def test_offline_collection_uses_cached_primary_pages_and_persists_exact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            chosen = (funding_sources[0], ma_sources[0])
            for source in chosen:
                assert source.published_at is not None
                raw_dir = output / "raw"
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = raw_dir / f"{source.source_record_id}.html"
                contents = (
                    f'<meta property="article:published_time" content="{source.published_at}">\n'
                    + "\n".join(fact.excerpt for fact in source.facts)
                ).encode("utf-8")
                raw_path.write_bytes(contents)
                (raw_dir / f"{source.source_record_id}.meta.json").write_text(
                    json.dumps(
                        {
                            "sourceRecordId": source.source_record_id,
                            "url": source.url,
                            "retrievedAtUTC": "2026-10-17T00:00:00Z",
                            "httpStatus": 200,
                            "physicalAttempts": 1,
                            "rawSha256": hashlib.sha256(contents).hexdigest(),
                        }
                    ),
                    encoding="utf-8",
                )

            with patch.object(
                request,
                "urlopen",
                side_effect=AssertionError("offline cache should avoid network calls"),
            ):
                records = venture_ma.collect(output, count=2)

            self.assertEqual(len(records), 2)
            self.assertEqual(len({row["evidence"][0]["sourceRecordId"] for row in records}), 2)
            persisted = [
                json.loads(line) for line in (output / "cases.jsonl").read_text().splitlines()
            ]
            self.assertEqual(records, persisted)
            for row in persisted:
                evidence = row["evidence"][0]
                source_bytes = (output / evidence["rawPath"]).read_bytes()
                self.assertEqual(hashlib.sha256(source_bytes).hexdigest(), evidence["rawSha256"])
                self.assertIn(evidence["excerpt"].encode("utf-8"), source_bytes)
                self.assertIn(row["temporal"]["date"], row["query"])
            self.assertTrue((output / "sources.md").is_file())
            self.assertIn("not as an upstream benchmark", (output / "sources.md").read_text())


if __name__ == "__main__":
    unittest.main()
