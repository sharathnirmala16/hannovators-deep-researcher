# ruff: noqa: E501,RUF001
"""Typed funding fact catalog and deterministic seed constructors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class FactSpec:
    """A deterministic field mapping with a literal source quote."""

    question: str
    answer: str
    excerpt: str
    question_type: str
    metric: Literal["money", "ratio", "text", "mix", "structured"]
    value: Any | None = None
    units: str | None = None
    currency: str | None = None
    numeric_token: str | None = None
    answer_token: str | None = None
    context_terms: tuple[str, ...] = ()
    support_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """One dated primary announcement, with up to two deliberately distinct facts."""

    source_record_id: str
    kind: Literal["funding", "m_and_a"]
    source_family: str
    title: str
    url: str
    facts: tuple[FactSpec, ...]
    published_at: str | None = None
    date_tokens: tuple[str, ...] = ()
    license_name: str = "unknown"
    upstream_revision: str | None = None


def _money(
    question: str,
    answer: str,
    token: str,
    value: int | float,
    units: str,
    excerpt: str,
    question_type: str,
    context_terms: tuple[str, ...],
    *,
    currency: str = "USD",
    support_terms: tuple[str, ...] = (),
) -> FactSpec:
    return FactSpec(
        question=question,
        answer=answer,
        excerpt=excerpt,
        question_type=question_type,
        metric="money",
        value=value,
        units=units,
        currency=currency,
        numeric_token=token,
        context_terms=context_terms,
        support_terms=support_terms,
    )


def _ratio(
    question: str,
    answer: str,
    token: str,
    value: float,
    units: str,
    excerpt: str,
    question_type: str,
    *,
    support_terms: tuple[str, ...],
) -> FactSpec:
    return FactSpec(
        question=question,
        answer=answer,
        excerpt=excerpt,
        question_type=question_type,
        metric="ratio",
        value=value,
        units=units,
        numeric_token=token,
        support_terms=support_terms,
    )


def _text(
    question: str,
    answer: str,
    excerpt: str,
    question_type: str,
    *,
    context_terms: tuple[str, ...] = (),
    support_terms: tuple[str, ...] = (),
) -> FactSpec:
    return FactSpec(
        question=question,
        answer=answer,
        excerpt=excerpt,
        question_type=question_type,
        metric="text",
        answer_token=answer,
        context_terms=context_terms,
        support_terms=support_terms,
    )


def _mix(
    question: str,
    answer: str,
    excerpt: str,
    question_type: str,
    *,
    support_terms: tuple[str, ...],
    value: Any | None = None,
    units: str | None = None,
) -> FactSpec:
    return FactSpec(
        question=question,
        answer=answer,
        excerpt=excerpt,
        question_type=question_type,
        metric="mix",
        value=value,
        units=units,
        support_terms=support_terms,
    )


def _structured(
    question: str,
    answer: str,
    excerpt: str,
    question_type: str,
    *,
    value: Any,
    units: str,
    currency: str | None,
    support_terms: tuple[str, ...],
) -> FactSpec:
    return FactSpec(
        question=question,
        answer=answer,
        excerpt=excerpt,
        question_type=question_type,
        metric="structured",
        value=value,
        units=units,
        currency=currency,
        support_terms=support_terms,
    )


_FUNDING_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        "anthropic-series-c-2023",
        "funding",
        "official_funding_announcement",
        "Anthropic raises $450 million in Series C",
        "https://www.anthropic.com/news/anthropic-series-c",
        (
            _money(
                "In Anthropic's Series C announcement dated {date}, how much funding did the company say it raised?",
                "$450 million",
                "$450 million",
                450000000,
                "USD funding round size",
                "We are pleased to announce that we have raised $450 million in Series C funding led by Spark Capital with participation from Google, Salesforce Ventures, Sound Ventures, Zoom Ventures, and others.",
                "funding_round_size",
                ("raised", "series c funding"),
            ),
            _text(
                "Which investor led Anthropic's Series C round announced on {date}?",
                "Spark Capital",
                "We are pleased to announce that we have raised $450 million in Series C funding led by Spark Capital with participation from Google, Salesforce Ventures, Sound Ventures, Zoom Ventures, and others.",
                "funding_lead_investor",
                context_terms=("led",),
            ),
        ),
        "2023-05-23",
        ("May 23, 2023", "May 23 2023"),
    ),
    SourceSpec(
        "cohere-funding-2025",
        "funding",
        "official_funding_announcement",
        "Cohere raises $500M at $6.8B valuation to accelerate enterprise efficiency with agentic AI",
        "https://cohere.com/blog/august-2025-funding-round",
        (
            _money(
                "What size of financing did Cohere announce on {date}?",
                "$500 million",
                "$500 million",
                500000000,
                "USD funding round size",
                "Today, we’re excited to announce Cohere’s latest $500 million raise at a $6.8 billion valuation in an oversubscribed round led by Radical Ventures and Inovia Capital, with additional participation from existing investors including AMD Ventures, NVIDIA, PSP Investments, and Salesforce Ventures, as well as new investors, including Healthcare of Ontario Pension Plan (“HOOPP”), among others.",
                "funding_round_size",
                ("raise",),
            ),
            _money(
                "What company valuation did Cohere state for the funding round announced on {date}?",
                "$6.8 billion",
                "$6.8 billion",
                6800000000,
                "USD post-money valuation",
                "Today, we’re excited to announce Cohere’s latest $500 million raise at a $6.8 billion valuation in an oversubscribed round led by Radical Ventures and Inovia Capital, with additional participation from existing investors including AMD Ventures, NVIDIA, PSP Investments, and Salesforce Ventures, as well as new investors, including Healthcare of Ontario Pension Plan (“HOOPP”), among others.",
                "post_money_valuation",
                ("valuation",),
            ),
        ),
        "2025-08-14",
        ("Aug 14, 2025", "August 14, 2025", "Aug 14 2025"),
    ),
    SourceSpec(
        "canva-funding-2021",
        "funding",
        "official_funding_announcement",
        "Canva Announces USD 40 Billion Valuation Fueled by the Global Demand for Visual Communication",
        "https://www.canva.com/newsroom/news/canva-announces-usd-40-billion-valuation-fueled-global-demand-visual-communication/",
        (
            _money(
                "How much funding did Canva announce on {date}?",
                "$200 million",
                "$200 million",
                200000000,
                "USD funding round size",
                "Canva, the global visual communications platform, today announced a USD $40 billion valuation after a USD $200 million funding round led by T. Rowe Price",
                "funding_round_size",
                ("funding round",),
            ),
            _money(
                "What valuation did Canva announce alongside its funding round on {date}?",
                "$40 billion",
                "$40 billion",
                40000000000,
                "USD company valuation",
                "Canva, the global visual communications platform, today announced a USD $40 billion valuation after a USD $200 million funding round led by T. Rowe Price",
                "funding_valuation",
                ("valuation",),
            ),
        ),
        "2021-09-15",
        ("September 15, 2021", "15 September 2021"),
    ),
    SourceSpec(
        "scale-series-f-2024",
        "funding",
        "official_funding_announcement",
        "Scale’s Series F: Expanding the Data Foundry for AI",
        "https://scale.com/blog/scale-ai-series-f",
        (
            _money(
                "How large was Scale's Series F financing transaction announced on {date}?",
                "$1 billion",
                "$1B",
                1000000000,
                "USD funding transaction size",
                "Today, we’re announcing that Scale has closed a $1B financing transaction at a $13.8B valuation.",
                "funding_round_size",
                ("closed", "financing transaction"),
            ),
            _money(
                "What valuation did Scale state alongside its Series F financing announcement on {date}?",
                "$13.8 billion",
                "$13.8B",
                13800000000,
                "USD company valuation",
                "Today, we’re announcing that Scale has closed a $1B financing transaction at a $13.8B valuation.",
                "post_money_valuation",
                ("valuation",),
            ),
        ),
        "2024-05-21",
        ("May 21, 2024", "May 21 2024"),
    ),
    SourceSpec(
        "glean-series-e-2024",
        "funding",
        "official_funding_announcement",
        "Glean raises over $260M series E and launches next-generation prompting to accelerate its vision of Work AI for all",
        "https://www.glean.com/blog/glean-series-e-prompting-launch",
        (
            _money(
                "How much Series E funding did Glean announce on {date}?",
                "Over $260 million",
                "$260M",
                260000000,
                "USD funding round lower bound",
                "Glean raises over $260M series E funding at a $4.6B valuation",
                "funding_round_size",
                ("series e", "funding"),
                support_terms=("over",),
            ),
            _money(
                "What valuation did Glean give for its Series E announced on {date}?",
                "$4.6 billion",
                "$4.6B",
                4600000000,
                "USD company valuation",
                "Glean raises over $260M series E funding at a $4.6B valuation",
                "post_money_valuation",
                ("valuation",),
            ),
        ),
        "2024-09-10",
        ("Sep 10, 2024", "September 10, 2024", "Sep 10 2024"),
    ),
    SourceSpec(
        "coreweave-series-c-2024",
        "funding",
        "official_funding_announcement",
        "CoreWeave Secures $1.1 Billion in Series C Funding to Drive the Next Generation of Cloud Computing for the Future of AI",
        "https://investors.coreweave.com/news/news-details/2024/CoreWeave-Secures-1-1-Billion-in-Series-C-Funding-to-Drive-the-Next-Generation-of-Cloud-Computing-for-the-Future-of-AI/default.aspx",
        (
            _money(
                "How much Series C funding did CoreWeave announce on {date}?",
                "$1.1 billion",
                "$1.1 billion",
                1100000000,
                "USD funding round size",
                "CoreWeave Secures $1.1 Billion in Series C Funding to Drive the Next Generation of Cloud Computing for the Future of AI",
                "funding_round_size",
                ("series c", "funding"),
            ),
            _text(
                "Which investor led CoreWeave's Series C round announced on {date}?",
                "Coatue",
                "led by Coatue, with participation from Magnetar who led the last primary round",
                "funding_lead_investor",
                context_terms=("led",),
            ),
        ),
        "2024-05-01",
        ("May 1, 2024", "May 01, 2024", "May 1 2024"),
    ),
    SourceSpec(
        "wayve-series-c-2024",
        "funding",
        "official_funding_announcement",
        "Wayve Raises Over $1 Billion Led by SoftBank to Develop Embodied AI Products for Automated Driving",
        "https://wayve.ai/press/series-c",
        (
            _money(
                "How much Series C funding did Wayve announce on {date}?",
                "$1.05 billion",
                "$1.05 billion",
                1050000000,
                "USD funding round size",
                "Wayve announces a $1.05 billion Series C investment round led by SoftBank Group (“SoftBank”), with contributions from new investor NVIDIA and existing investor Microsoft, to accelerate its mission to reimagine autonomous mobility through embodied intelligence.",
                "funding_round_size",
                ("series c", "investment round"),
            ),
            _text(
                "Which firm led Wayve's Series C announced on {date}?",
                "SoftBank Group",
                "Wayve announces a $1.05 billion Series C investment round led by SoftBank Group (“SoftBank”), with contributions from new investor NVIDIA and existing investor Microsoft, to accelerate its mission to reimagine autonomous mobility through embodied intelligence.",
                "funding_lead_investor",
                context_terms=("led by",),
            ),
        ),
        "2024-05-06",
        ("May 6, 2024", "May 06, 2024", "May 6 2024"),
    ),
    SourceSpec(
        "xai-series-b-2024",
        "funding",
        "official_funding_announcement",
        "Series B funding round",
        "https://x.ai/news/series-b",
        (
            _money(
                "What size was xAI's Series B funding round announced on {date}?",
                "$6 billion",
                "$6 billion",
                6000000000,
                "USD funding round size",
                "Our Series B funding round of $6 billion",
                "funding_round_size",
                ("series b funding round",),
            ),
            _text(
                "Which two investors were named first among xAI's key Series B participants announced on {date}?",
                "Valor Equity Partners, Vy Capital",
                "Our Series B funding round of $6 billion with participation from key investors including Valor Equity Partners, Vy Capital",
                "funding_named_participants",
                context_terms=("participation",),
            ),
        ),
        "2024-05-26",
        ("May 26, 2024", "May 26 2024"),
    ),
    SourceSpec(
        "ramp-series-d2-2024",
        "funding",
        "official_funding_announcement",
        "Ramp announces Series D-2 capital raise",
        "https://ramp.com/blog/ramp-april-2024-funding",
        (
            _money(
                "What amount did Ramp announce for its Series D-2 raise on {date}?",
                "$150 million",
                "$150 million",
                150000000,
                "USD funding round size",
                "Ramp is completing a $150 million Series D-2 funding round, raising the company’s valuation to $7.65 billion.",
                "funding_round_size",
                ("series d-2", "funding round"),
            ),
            _money(
                "What valuation did Ramp report for its Series D-2 funding round announced on {date}?",
                "$7.65 billion",
                "$7.65 billion",
                7650000000,
                "USD company valuation",
                "Ramp is completing a $150 million Series D-2 funding round, raising the company’s valuation to $7.65 billion.",
                "post_money_valuation",
                ("valuation",),
            ),
        ),
        "2024-04-16",
        ("Apr 16, 2024", "April 16, 2024", "Apr 16 2024"),
    ),
    SourceSpec(
        "figure-series-c-2025",
        "funding",
        "official_funding_announcement",
        "Figure Exceeds $1B in Series C Funding at $39B Post-Money Valuation",
        "https://www.figure.ai/news/series-c",
        (
            _money(
                "What committed capital amount did Figure say it had exceeded in its Series C announcement dated {date}?",
                "More than $1 billion in committed capital",
                "$1 billion",
                1000000000,
                "USD committed Series C capital lower bound",
                "Today we’re announcing that we have exceeded more than $1 billion in committed capital through our Series C financing round, at a post-money valuation of $39 billion.",
                "funding_committed_capital",
                ("committed capital", "series c financing"),
                support_terms=("more than",),
            ),
            _money(
                "What post-money valuation did Figure state in its Series C announcement dated {date}?",
                "$39 billion",
                "$39 billion",
                39000000000,
                "USD post-money valuation",
                "Today we’re announcing that we have exceeded more than $1 billion in committed capital through our Series C financing round, at a post-money valuation of $39 billion.",
                "post_money_valuation",
                ("post-money valuation",),
            ),
        ),
    ),
    SourceSpec(
        "databricks-series-j-2024",
        "funding",
        "official_funding_announcement",
        "Databricks is Raising $10B Series J Investment at $62B Valuation",
        "https://www.databricks.com/company/newsroom/press-releases/databricks-raising-10b-series-j-investment-62b-valuation",
        (
            _money(
                "What total expected financing amount did Databricks say it was raising for its Series J in the announcement dated {date}?",
                "An expected $10 billion, with $8.6 billion completed to date",
                "$10 billion",
                10000000000,
                "USD expected total financing (not fully completed at announcement)",
                "The company is raising $10 billion of expected non-dilutive financing and has completed $8.6 billion to date. This funding values Databricks at $62 billion and is led by Thrive Capital.",
                "funding_expected_total",
                ("raising", "financing"),
                support_terms=("expected", "completed $8.6 billion to date"),
            ),
            _money(
                "What valuation did Databricks state for the Series J financing announced on {date}?",
                "$62 billion",
                "$62 billion",
                62000000000,
                "USD company valuation",
                "The company is raising $10 billion of expected non-dilutive financing and has completed $8.6 billion to date. This funding values Databricks at $62 billion and is led by Thrive Capital.",
                "funding_valuation",
                ("values Databricks at",),
            ),
        ),
        "2024-12-17",
        ("December 17, 2024", "Dec 17, 2024", "December 17 2024"),
    ),
    SourceSpec(
        "klarna-funding-2022",
        "funding",
        "official_funding_announcement",
        "Klarna closes major financing round during worst stock downturn in 50 years",
        "https://www.klarna.com/international/regulatory-news/klarna-closes-major-financing-round-during-worst-stock-downturn-in-50-years/",
        (
            _money(
                "How much new financing did Klarna announce it had closed on {date}?",
                "$800 million",
                "$800m",
                800000000,
                "USD financing round size",
                "Stockholm, Sweden, July 11 2022: Klarna, the global leader in the generational shift away from credit cards, announced the closing of a new $800m financing at a $6.7bn post-money valuation.",
                "funding_round_size",
                ("closing", "financing"),
            ),
            _money(
                "What post-money valuation did Klarna state for the financing announced on {date}?",
                "$6.7 billion",
                "$6.7bn",
                6700000000,
                "USD post-money valuation",
                "Stockholm, Sweden, July 11 2022: Klarna, the global leader in the generational shift away from credit cards, announced the closing of a new $800m financing at a $6.7bn post-money valuation.",
                "post_money_valuation",
                ("post-money valuation",),
            ),
        ),
        "2022-07-11",
        ("July 11, 2022", "July 11 2022"),
    ),
)
_FUNDING_BACKUPS: tuple[SourceSpec, ...] = ()
