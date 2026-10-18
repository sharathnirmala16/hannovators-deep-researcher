# ruff: noqa: E501,RUF001
"""First-party merger and acquisition source catalog."""

from __future__ import annotations

from dataclasses import replace

from .venture_ma_facts import SourceSpec, _mix, _money, _ratio, _structured, _text

_M_AND_A_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        "adobe-figma-announcement-2022",
        "m_and_a",
        "official_merger_announcement",
        "Adobe to Acquire Figma",
        "https://news.adobe.com/news/news-details/2022/Adobe-to-Acquire-Figma/default.aspx",
        (
            _money(
                "What approximate transaction value did Adobe announce for its planned Figma acquisition on {date}?",
                "Approximately $20 billion",
                "$20 billion",
                20000000000,
                "USD announced transaction value",
                "Today, Adobe (Nasdaq:ADBE) announced it has entered into a definitive merger agreement to acquire Figma, a leading web-first collaborative design platform, for approximately $20 billion in cash and stock.",
                "announced_transaction_value",
                ("acquire Figma", "approximately"),
                support_terms=("cash and stock",),
            ),
            _mix(
                "How did Adobe say the consideration for its planned Figma acquisition would be divided, as announced on {date}?",
                "Approximately half cash and half stock",
                "Under the definitive agreement, Adobe has agreed to acquire Figma for approximately $20 billion, comprised of approximately half cash and half stock, subject to customary adjustments.",
                "cash_stock_consideration_mix",
                support_terms=("half cash", "half stock"),
                units="approximate fractions of announced consideration",
            ),
        ),
        "2022-09-15",
        ("September 15, 2022", "Sep 15, 2022", "September 15 2022"),
    ),
    SourceSpec(
        "microsoft-activision-announcement-2022",
        "m_and_a",
        "official_merger_announcement",
        "Microsoft to acquire Activision Blizzard to bring the joy and community of gaming to everyone, across every device",
        "https://news.microsoft.com/source/2022/01/18/microsoft-to-acquire-activision-blizzard-to-bring-the-joy-and-community-of-gaming-to-everyone-across-every-device/",
        (
            _money(
                "What announced transaction value did Microsoft give for the proposed Activision Blizzard acquisition on {date}?",
                "$68.7 billion, inclusive of Activision Blizzard's net cash",
                "$68.7 billion",
                68700000000,
                "USD announced transaction value, inclusive of target net cash",
                "Microsoft will acquire Activision Blizzard for $95.00 per share, in an all-cash transaction valued at $68.7 billion, inclusive of Activision Blizzard’s net cash.",
                "announced_transaction_value",
                ("transaction valued at",),
                support_terms=("inclusive of Activision Blizzard’s net cash",),
            ),
            _money(
                "What per-share cash price did Microsoft announce for Activision Blizzard on {date}?",
                "$95.00 per share in cash",
                "$95.00",
                95,
                "USD per Activision Blizzard share",
                "Microsoft will acquire Activision Blizzard for $95.00 per share, in an all-cash transaction valued at $68.7 billion, inclusive of Activision Blizzard’s net cash.",
                "per_share_cash_consideration",
                ("per share", "cash transaction"),
            ),
        ),
        "2022-01-18",
        ("Jan. 18, 2022", "January 18, 2022", "Jan 18 2022"),
    ),
    SourceSpec(
        "cisco-splunk-announcement-2023",
        "m_and_a",
        "official_merger_announcement",
        "Cisco to Acquire Splunk, to Help Make Organizations More Secure and Resilient in an AI-Powered World",
        "https://investor.cisco.com/news/news-details/2023/Cisco-to-Acquire-Splunk-to-Help-Make-Organizations-More-Secure-and-Resilient-in-an-AI-Powered-World/default.aspx",
        (
            _money(
                "What approximate equity value did Cisco announce for its planned Splunk acquisition on {date}?",
                "Approximately $28 billion in equity value",
                "$28 billion",
                28000000000,
                "USD equity value (approximate)",
                "Under the terms of the agreement, Cisco intends to acquire Splunk for $157 per share in cash, representing approximately $28 billion in equity value.",
                "announced_equity_value",
                ("equity value",),
                support_terms=("approximately",),
            ),
            _money(
                "What per-share cash consideration did Cisco announce for Splunk on {date}?",
                "$157 per share in cash",
                "$157",
                157,
                "USD per Splunk share",
                "Under the terms of the agreement, Cisco intends to acquire Splunk for $157 per share in cash, representing approximately $28 billion in equity value.",
                "per_share_cash_consideration",
                ("per share", "in cash"),
            ),
        ),
        "2023-09-21",
        ("Sept. 21, 2023", "September 21, 2023", "Sept 21 2023"),
    ),
    SourceSpec(
        "ibm-hashicorp-announcement-2024",
        "m_and_a",
        "official_merger_announcement",
        "IBM to Acquire HashiCorp, Inc. Creating a Comprehensive End-to-End Hybrid Cloud Platform",
        "https://newsroom.ibm.com/2024-04-24-IBM-to-Acquire-HashiCorp-Inc-Creating-a-Comprehensive-End-to-End-Hybrid-Cloud-Platform",
        (
            _money(
                "What enterprise value did IBM announce for its planned HashiCorp acquisition on {date}?",
                "$6.4 billion in enterprise value",
                "$6.4 billion",
                6400000000,
                "USD enterprise value, net of cash",
                "IBM (NYSE: IBM) and HashiCorp Inc. (NASDAQ: HCP), a leading multi-cloud infrastructure automation company, today announced they have entered into a definitive agreement under which IBM will acquire HashiCorp for $35 per share in cash, representing an enterprise value of $6.4 billion.",
                "announced_enterprise_value",
                ("enterprise value",),
            ),
            _money(
                "What per-share cash price did IBM announce for HashiCorp on {date}?",
                "$35 per share in cash",
                "$35",
                35,
                "USD per HashiCorp share",
                "IBM (NYSE: IBM) and HashiCorp Inc. (NASDAQ: HCP), a leading multi-cloud infrastructure automation company, today announced they have entered into a definitive agreement under which IBM will acquire HashiCorp for $35 per share in cash, representing an enterprise value of $6.4 billion.",
                "per_share_cash_consideration",
                ("per share", "in cash"),
            ),
        ),
        "2024-04-24",
        ("April 24, 2024", "Apr 24, 2024", "April 24 2024"),
    ),
    SourceSpec(
        "salesforce-slack-announcement-2020",
        "m_and_a",
        "official_merger_announcement",
        "Salesforce Signs Definitive Agreement to Acquire Slack",
        "https://investor.salesforce.com/news/news-details/2020/Salesforce-Signs-Definitive-Agreement-to-Acquire-Slack/default.aspx",
        (
            _money(
                "What approximate enterprise value did Salesforce state for its planned Slack acquisition on {date}?",
                "Approximately $27.7 billion in enterprise value",
                "$27.7 billion",
                27700000000,
                "USD enterprise value (approximate)",
                "Under the terms of the agreement, Slack shareholders will receive $26.79 in cash and 0.0776 shares of Salesforce common stock for each Slack share, representing an enterprise value of approximately $27.7 billion based on the closing price of Salesforce’s common stock on November 30, 2020.",
                "announced_enterprise_value",
                ("enterprise value",),
                support_terms=("approximately",),
            ),
            _structured(
                "What cash-and-stock consideration did Salesforce announce for each Slack share on {date}?",
                "$26.79 in cash plus 0.0776 shares of Salesforce common stock per Slack share",
                "Under the terms of the agreement, Slack shareholders will receive $26.79 in cash and 0.0776 shares of Salesforce common stock for each Slack share, representing an enterprise value of approximately $27.7 billion based on the closing price of Salesforce’s common stock on November 30, 2020.",
                "cash_stock_per_target_share",
                value={"cashUsdPerSlackShare": 26.79, "salesforceSharesPerSlackShare": 0.0776},
                units="USD cash and Salesforce common shares per Slack share",
                currency="USD",
                support_terms=(
                    "$26.79 in cash",
                    "0.0776 shares of Salesforce common stock",
                    "for each Slack share",
                ),
            ),
        ),
        "2020-12-01",
        ("Dec. 1, 2020", "December 1, 2020", "Dec 1 2020"),
    ),
    SourceSpec(
        "broadcom-vmware-announcement-2022",
        "m_and_a",
        "official_merger_announcement",
        "Broadcom to Acquire VMware for Approximately $61 Billion in Cash and Stock",
        "https://news.broadcom.com/apj/primary/broadcom-to-acquire-vmware-for-approximately-61-billion-in-cash-and-stock",
        (
            _money(
                "What approximate transaction value did Broadcom announce for its proposed VMware acquisition on {date}?",
                "Approximately $61 billion",
                "$61 billion",
                61000000000,
                "USD announced transaction value",
                "Broadcom Inc. to acquire VMware, Inc. for approximately $61 billion in cash and stock.",
                "announced_transaction_value",
                ("approximately",),
                support_terms=("cash and stock",),
            ),
            _mix(
                "What forms of consideration did Broadcom name for its proposed VMware acquisition announced on {date}?",
                "Cash and stock",
                "Broadcom Inc. to acquire VMware, Inc. for approximately $61 billion in cash and stock.",
                "cash_stock_consideration_mix",
                support_terms=("cash", "stock"),
                units="cash and stock consideration forms",
            ),
        ),
        "2022-05-26",
        ("May 26, 2022", "May 26 2022"),
    ),
    SourceSpec(
        "exxon-pioneer-announcement-2023",
        "m_and_a",
        "official_merger_announcement",
        "ExxonMobil announces merger with Pioneer Natural Resources in an all-stock transaction",
        "https://corporate.exxonmobil.com/news/news-releases/2023/1011_exxonmobil-announces-merger-with-pioneer-natural-resources-in-an-all-stock-transaction",
        (
            _money(
                "What value did ExxonMobil announce for its planned Pioneer transaction on {date}?",
                "$59.5 billion, an all-stock transaction value",
                "$59.5 billion",
                59500000000,
                "USD transaction value (all stock)",
                "The merger is an all-stock transaction valued at $59.5 billion, or $253 per share, based on ExxonMobil’s closing price on October 5, 2023.",
                "announced_transaction_value",
                ("all-stock transaction", "valued at"),
            ),
            _ratio(
                "What fixed share exchange ratio did ExxonMobil announce for Pioneer shareholders on {date}?",
                "2.3234 ExxonMobil shares for each Pioneer share",
                "2.3234",
                2.3234,
                "ExxonMobil shares per Pioneer share",
                "Under the terms of the agreement, Pioneer shareholders will receive 2.3234 shares of ExxonMobil for each Pioneer share at closing.",
                "share_exchange_ratio",
                support_terms=(
                    "Pioneer shareholders will receive",
                    "shares of ExxonMobil",
                    "for each Pioneer share",
                ),
            ),
        ),
        "2023-10-11",
        ("Oct. 11, 2023", "October 11, 2023", "Oct 11 2023"),
    ),
    SourceSpec(
        "chevron-hess-announcement-2023",
        "m_and_a",
        "official_merger_announcement",
        "Chevron Announces Agreement to Acquire Hess",
        "https://www.chevron.com/newsroom/2023/q4/chevron-announces-agreement-to-acquire-hess",
        (
            _money(
                "What transaction value did Chevron announce for its proposed Hess acquisition on {date}?",
                "$53 billion, an all-stock transaction value",
                "$53 billion",
                53000000000,
                "USD announced transaction value (all stock)",
                "Chevron Corporation (NYSE: CVX) announced today that it has entered into a definitive agreement with Hess Corporation (NYSE: HES) to acquire all of the outstanding shares of Hess in an all-stock transaction valued at $53 billion, or $171 per share based on Chevron’s closing price on October 20, 2023.",
                "announced_transaction_value",
                ("all-stock transaction", "valued at"),
            ),
            _ratio(
                "What fixed exchange ratio did Chevron announce for Hess shareholders on {date}?",
                "1.0250 Chevron shares for each Hess share",
                "1.0250",
                1.025,
                "Chevron shares per Hess share",
                "Under the terms of the agreement, Hess shareholders will receive 1.0250 shares of Chevron for each Hess share.",
                "share_exchange_ratio",
                support_terms=(
                    "Hess shareholders will receive",
                    "shares of Chevron",
                    "for each Hess share",
                ),
            ),
        ),
        "2023-10-23",
        ("October 23, 2023", "Oct. 23, 2023", "October 23 2023"),
    ),
    SourceSpec(
        "homedepot-srs-announcement-2024",
        "m_and_a",
        "official_merger_announcement",
        "The Home Depot Announces Agreement to Acquire SRS Distribution",
        "https://ir.homedepot.com/news-releases/2024/03-28-2024-100102814",
        (
            _money(
                "What total enterprise value did The Home Depot announce for its planned SRS acquisition on {date}?",
                "Approximately $18.25 billion, including net debt",
                "$18.25 billion",
                18250000000,
                "USD enterprise value, including net debt (approximate)",
                "Under the terms of the merger agreement, a subsidiary of The Home Depot will acquire SRS for a total enterprise value (including net debt) of approximately $18.25 billion.",
                "announced_enterprise_value",
                ("enterprise value",),
                support_terms=("including net debt", "approximately"),
            ),
            _text(
                "How did The Home Depot say it expected to fund the SRS transaction announced on {date}?",
                "Cash on hand and debt",
                "The transaction is expected to be funded through cash on hand and debt.",
                "acquisition_funding_method",
                support_terms=("cash on hand", "debt"),
            ),
        ),
        "2024-03-28",
        ("March 28, 2024", "Mar 28, 2024", "March 28 2024"),
    ),
    SourceSpec(
        "amazon-irobot-announcement-2022",
        "m_and_a",
        "official_merger_announcement",
        "Amazon and iRobot sign an agreement for Amazon to acquire iRobot",
        "https://www.aboutamazon.com/news/company-news/amazon-and-irobot-sign-an-agreement-for-amazon-to-acquire-irobot",
        (
            _money(
                "What approximate value did Amazon announce for its proposed iRobot acquisition on {date}, including iRobot's net debt?",
                "Approximately $1.7 billion, including iRobot's net debt",
                "$1.7 billion",
                1700000000,
                "USD announced transaction value, including target net debt (approximate)",
                "Amazon will acquire iRobot for $61 per share in an all-cash transaction valued at approximately $1.7 billion, including iRobot’s net debt.",
                "announced_transaction_value",
                ("transaction valued at",),
                support_terms=("approximately", "including iRobot’s net debt"),
            ),
            _money(
                "What per-share cash price did Amazon announce for iRobot on {date}?",
                "$61 per share in cash",
                "$61",
                61,
                "USD per iRobot share",
                "Amazon will acquire iRobot for $61 per share in an all-cash transaction valued at approximately $1.7 billion, including iRobot’s net debt.",
                "per_share_cash_consideration",
                ("per share", "all-cash transaction"),
            ),
        ),
        "2022-08-05",
        ("August 05, 2022", "August 5, 2022", "Aug. 5, 2022", "August 5 2022"),
    ),
    SourceSpec(
        "kroger-albertsons-announcement-2022",
        "m_and_a",
        "official_merger_announcement",
        "Kroger and Albertsons Companies Announce Definitive Merger Agreement",
        "https://ir.kroger.com/news/news-details/2022/Kroger-and-Albertsons-Companies-Announce-Definitive-Merger-Agreement/default.aspx",
        (
            _money(
                "What approximate enterprise value did Kroger and Albertsons announce for their proposed merger on {date}?",
                "Approximately $24.6 billion, including assumed net debt",
                "$24.6 billion",
                24600000000,
                "USD enterprise value, including assumed net debt (approximate)",
                "Kroger and Albertsons Companies Announce Definitive Merger Agreement October 14, 2022 Albertsons Companies Shareholders Expected to Receive Total Consideration Valued at $34.10 Per Share implying a total enterprise value of approximately $24.6 billion, including the assumption of approximately $4.7 billion of Albertsons Cos. net debt.",
                "announced_enterprise_value",
                ("enterprise value",),
                support_terms=("approximately", "net debt"),
            ),
            _money(
                "What total consideration per Albertsons share did the companies announce on {date}?",
                "$34.10 per share",
                "$34.10",
                34.1,
                "USD per Albertsons share",
                "Albertsons Companies Shareholders Expected to Receive Total Consideration Valued at $34.10 Per Share",
                "per_share_consideration",
                ("total consideration", "per share"),
            ),
        ),
        "2022-10-14",
        ("October 14, 2022", "Oct 14, 2022", "October 14 2022"),
    ),
    SourceSpec(
        "conocophillips-marathon-announcement-2024",
        "m_and_a",
        "official_merger_announcement",
        "ConocoPhillips to acquire Marathon Oil Corporation in all-stock transaction; provides shareholder distribution update",
        "https://www.conocophillips.com/news-media/story/conocophillips-to-acquire-marathon-oil-corporation-in-all-stock-transaction-provides-shareholder-distribution-update/",
        (
            _money(
                "What enterprise value did ConocoPhillips announce for its proposed Marathon Oil acquisition on {date}?",
                "$22.5 billion, inclusive of $5.4 billion of net debt",
                "$22.5 billion",
                22500000000,
                "USD enterprise value, inclusive of target net debt",
                "ConocoPhillips will acquire Marathon Oil in an all-stock transaction with an enterprise value of $22.5 billion, inclusive of $5.4 billion of net debt.",
                "announced_enterprise_value",
                ("enterprise value",),
                support_terms=("inclusive of $5.4 billion of net debt",),
            ),
            _ratio(
                "What fixed share exchange ratio did ConocoPhillips announce for Marathon Oil shareholders on {date}?",
                "0.2550 ConocoPhillips shares for each Marathon Oil share",
                "0.2550",
                0.255,
                "ConocoPhillips shares per Marathon Oil share",
                "Under the terms of the agreement, Marathon Oil shareholders will receive 0.2550 shares of ConocoPhillips common stock for each share of Marathon Oil common stock.",
                "share_exchange_ratio",
                support_terms=(
                    "Marathon Oil shareholders will receive",
                    "shares of ConocoPhillips",
                    "for each share of Marathon Oil",
                ),
            ),
        ),
        "2024-05-29",
        ("May 29, 2024", "May 29 2024"),
    ),
    SourceSpec(
        "adobe-figma-termination-2023",
        "m_and_a",
        "sec_filing_exhibit_press_release",
        "Adobe and Figma Mutually Agree to Terminate Merger Agreement",
        "https://www.sec.gov/Archives/edgar/data/796343/000079634323000254/adbedecember182023pressrel.htm",
        (
            _text(
                "What did Adobe and Figma announce on {date} about their previously announced merger agreement?",
                "a mutual agreement to terminate their previously announced merger agreement",
                "Today, Adobe (Nasdaq:ADBE) and Figma announced that they have entered into a mutual agreement to terminate their previously announced merger agreement, originally announced on September 15, 2022, under which Adobe would have acquired Figma for a mix of cash and stock consideration.",
                "announced_transaction_status",
                context_terms=("terminate",),
            ),
            _money(
                "What termination fee did Adobe state it would pay Figma after the agreement ended on {date}?",
                "$1 billion in cash",
                "$1,000,000,000",
                1000000000,
                "USD termination fee",
                "In accordance with the terms of the Termination Agreement, the Company will make a cash payment to Figma in the previously agreed amount of one billion dollars ($1,000,000,000) (the “Termination Fee”) within three business days following the date thereof.",
                "m_and_a_termination_fee",
                ("cash payment to Figma", "termination fee"),
            ),
        ),
        "2023-12-18",
        ("December 18, 2023", "Dec. 18, 2023", "December 18 2023"),
    ),
)
_M_AND_A_BACKUPS: tuple[SourceSpec, ...] = (
    SourceSpec(
        "exxon-denbury-announcement-2023",
        "m_and_a",
        "official_merger_announcement",
        "ExxonMobil announces acquisition of Denbury",
        "https://corporate.exxonmobil.com/news/news-releases/2023/0713_exxonmobil-announces-acquisition-of-denbury",
        (
            _money(
                "What value did ExxonMobil announce for its planned Denbury acquisition on {date}?",
                "$4.9 billion, an all-stock transaction value",
                "$4.9 billion",
                4900000000,
                "USD transaction value (all stock)",
                "The acquisition is an all-stock transaction valued at $4.9 billion, or $89.45 per share based on ExxonMobil’s closing price on July 12, 2023.",
                "announced_transaction_value",
                ("all-stock transaction", "valued at"),
            ),
            _ratio(
                "What share exchange ratio did ExxonMobil announce for Denbury shareholders on {date}?",
                "0.84 ExxonMobil shares for each Denbury share",
                "0.84",
                0.84,
                "ExxonMobil shares per Denbury share",
                "Under the terms of the agreement, Denbury shareholders will receive 0.84 shares of ExxonMobil for each Denbury share.",
                "share_exchange_ratio",
                support_terms=(
                    "Denbury shareholders will receive",
                    "shares of ExxonMobil",
                    "for each Denbury share",
                ),
            ),
        ),
        "2023-07-13",
        ("July 13, 2023", "July 13 2023"),
    ),
)


def _replace_fact_excerpts(
    source: SourceSpec,
    excerpts: dict[str, str],
) -> SourceSpec:
    return replace(
        source,
        facts=tuple(
            replace(fact, excerpt=excerpts.get(fact.question_type, fact.excerpt))
            for fact in source.facts
        ),
    )


_LITERAL_EXCERPT_REPAIRS: dict[str, dict[str, str]] = {
    "ibm-hashicorp-announcement-2024": {
        "announced_enterprise_value": r"""Under the terms of the agreement, IBM will acquire HashiCorp for <span class="xn-money">$35</span> per share in cash, or <span class="xn-money">$6.4 billion</span> enterprise value, net of cash.""",
        "per_share_cash_consideration": r"""Under the terms of the agreement, IBM will acquire HashiCorp for <span class="xn-money">$35</span> per share in cash, or <span class="xn-money">$6.4 billion</span> enterprise value, net of cash.""",
    },
    "salesforce-slack-announcement-2020": {
        "announced_enterprise_value": """Salesforce (NYSE: CRM), the global leader in CRM, and Slack Technologies, Inc. (NYSE: WORK), the most innovative enterprise communications platform, have entered into a definitive agreement under which Salesforce will acquire Slack. Under the terms of the agreement, Slack shareholders will receive $26.79 in cash and 0.0776 shares of Salesforce common stock for each Slack share, representing an enterprise value of approximately $27.7 billion based on the closing price of Salesforce&#x2019;s common stock on November 30, 2020.""",
        "cash_stock_per_target_share": """Salesforce (NYSE: CRM), the global leader in CRM, and Slack Technologies, Inc. (NYSE: WORK), the most innovative enterprise communications platform, have entered into a definitive agreement under which Salesforce will acquire Slack. Under the terms of the agreement, Slack shareholders will receive $26.79 in cash and 0.0776 shares of Salesforce common stock for each Slack share, representing an enterprise value of approximately $27.7 billion based on the closing price of Salesforce&#x2019;s common stock on November 30, 2020.""",
    },
    "homedepot-srs-announcement-2024": {
        "announced_enterprise_value": """Under the terms of the merger agreement, a subsidiary of The Home Depot will acquire SRS for a total enterprise value (including net debt) of approximately $18.25 billion. The closing of the acquisition is subject to customary closing conditions, including regulatory approvals, and is expected to be completed by the end of fiscal 2024. The transaction is expected to be funded through cash on hand and debt.""",
    },
    "kroger-albertsons-announcement-2022": {
        "announced_enterprise_value": """Under the terms of the merger agreement, which has been unanimously approved by the board of directors of each company, Kroger will acquire all of the outstanding shares of Albertsons Companies, Inc. (&quot;Albertsons Cos.&quot;) common and preferred stock (on an as converted basis) for an estimated total consideration of $34.10 per share, implying a total enterprise value of approximately $24.6 billion, including the assumption of approximately $4.7 billion of Albertsons Cos. net debt.""",
        "per_share_consideration": """<p>Under the terms of the merger agreement, which has been unanimously approved by the board of directors of each company, Kroger will acquire all of the outstanding shares of Albertsons Companies, Inc. (&quot;Albertsons Cos.&quot;) common and preferred stock (on an as converted basis) for an estimated total consideration of $34.10 per share, implying a total enterprise value of approximately $24.6 billion, including the assumption of approximately $4.7 billion of Albertsons Cos. net debt. Subject to the outcome of a store divestiture process, the cash component of the $34.10 per share consideration may be reduced by the per share value of a newly created standalone public company (&quot;SpinCo&quot;) that Albertsons Cos. is prepared to spin off at closing in conjunction with the regulatory clearance process described further in the Transaction Details below. As part of the transaction, Albertsons Cos. will pay a special cash dividend of up to $4 billion to its shareholders. The cash component of the $34.10 per share consideration will be reduced by the per share amount of the special cash dividend, which is expected to be approximately $6.85 per share. This cash dividend will be payable on November 7, 2022, to shareholders of record as of the close of business on October 24, 2022.</p>""",
    },
    "conocophillips-marathon-announcement-2024": {
        "share_exchange_ratio": """Under the terms of the agreement, Marathon Oil shareholders will receive 0.2550 shares of ConocoPhillips common stock for each share of Marathon Oil common stock, representing a 14.7% premium to the closing share price of Marathon Oil on May 28, 2024, and a 16.0% premium to the prior 10-day volume-weighted average price.""",
    },
}

_UNAVAILABLE_M_AND_A_SOURCE_IDS = {
    "broadcom-vmware-announcement-2022",
    "exxon-pioneer-announcement-2023",
    "chevron-hess-announcement-2023",
    "adobe-figma-termination-2023",
}
_M_AND_A_SOURCES = tuple(
    _replace_fact_excerpts(source, _LITERAL_EXCERPT_REPAIRS.get(source.source_record_id, {}))
    for source in _M_AND_A_SOURCES
    if source.source_record_id not in _UNAVAILABLE_M_AND_A_SOURCE_IDS
)


_M_AND_A_BACKUPS = (
    SourceSpec(
        "adobe-figma-termination-candidate-2023",
        "m_and_a",
        "official_merger_termination_announcement",
        "Adobe and Figma Mutually Agree to Terminate Merger Agreement",
        "https://news.adobe.com/news/news-details/2023/Adobe-and-Figma-Mutually-Agree-to-Terminate-Merger-Agreement/default.aspx",
        (
            _text(
                "What status did Adobe and Figma announce for their proposed merger on {date}?",
                "a mutual agreement to terminate their previously announced merger agreement",
                r"""<p><strong>SAN JOSE, Calif. &#x26; SAN FRANCISCO</strong>--(BUSINESS WIRE)-- Today, Adobe (Nasdaq:ADBE) and Figma announced that they have entered into a mutual agreement to terminate their previously announced merger agreement, originally announced on September 15, 2022, under which Adobe would have acquired Figma for a mix of cash and stock consideration.</p>""",
                "announced_transaction_status",
                context_terms=("mutual agreement", "terminate"),
                support_terms=(
                    "previously announced merger agreement",
                    "would have acquired Figma",
                ),
            ),
            _text(
                "What reason did Adobe and Figma give for terminating their proposed merger on {date}?",
                "there is no clear path to receive necessary regulatory approvals from the European Commission and the UK Competition and Markets Authority",
                r"""<p>Although both companies continue to believe in the merits and procompetitive benefits of the combination, Adobe and Figma mutually agreed to terminate the transaction based on a joint assessment that there is no clear path to receive necessary regulatory approvals from the European Commission and the UK Competition and Markets Authority.</p>""",
                "termination_reason",
                context_terms=("joint assessment", "regulatory approvals"),
                support_terms=("European Commission", "UK Competition and Markets Authority"),
            ),
        ),
        "2023-12-18",
    ),
    SourceSpec(
        "nvidia-arm-announcement-2020",
        "m_and_a",
        "official_merger_announcement",
        "NVIDIA to Acquire Arm for $40 Billion, Creating World’s Premier Computing Company for the Age of AI",
        "https://nvidianews.nvidia.com/news/nvidia-to-acquire-arm-for-40-billion-creating-worlds-premier-computing-company-for-the-age-of-ai",
        (
            _money(
                "What announced transaction value did NVIDIA state for its planned Arm acquisition on {date}?",
                "$40 billion, an announced transaction value",
                "$40 billion",
                40_000_000_000,
                "USD announced transaction value for a proposed acquisition",
                r"""<p>NVIDIA and SoftBank Group Corp. (SBG) today announced a definitive agreement under which NVIDIA will acquire Arm Limited from SBG and the SoftBank Vision Fund (together, &ldquo;SoftBank&rdquo;) in a transaction valued at $40 billion. The transaction is expected to be immediately accretive to NVIDIA&rsquo;s non-GAAP gross margin and non-GAAP earnings per share.</p>""",
                "announced_transaction_value",
                ("transaction valued at",),
                support_terms=("definitive agreement", "will acquire Arm", "transaction valued at"),
            ),
            _money(
                "What maximum earn-out did NVIDIA say SoftBank could receive under the proposed Arm acquisition announced on {date}?",
                "Up to $5 billion in cash or common stock, contingent on Arm performance targets",
                "$5 billion",
                5_000_000_000,
                "USD maximum contingent earn-out (cash or common stock)",
                "Additionally, SoftBank may receive up to $5 billion in cash or common stock under an earn-out construct, subject to satisfaction of specific financial performance targets by Arm.",
                "m_and_a_contingent_earnout",
                ("earn-out construct",),
                support_terms=(
                    "may receive up to",
                    "cash or common stock",
                    "specific financial performance targets by Arm",
                ),
            ),
        ),
        "2020-09-13",
        ("September 13, 2020",),
    ),
    SourceSpec(
        "facebook-whatsapp-announcement-2014",
        "m_and_a",
        "official_merger_announcement",
        "Facebook to Acquire WhatsApp",
        "https://about.fb.com/news/2014/02/facebook-to-acquire-whatsapp/",
        (
            _money(
                "How much cash consideration did Facebook announce for WhatsApp on {date}?",
                "$4 billion in cash",
                "$4 billion",
                4_000_000_000,
                "USD cash consideration for WhatsApp shareholders",
                "Facebook today announced that it has reached a definitive agreement to acquire WhatsApp, a rapidly growing cross-platform mobile messaging company, for a total of approximately $16 billion, including $4 billion in cash and approximately $12 billion worth of Facebook shares. The agreement also provides for an additional $3 billion in restricted stock units to be granted to WhatsApp’s founders and employees that will vest over four years subsequent to closing.",
                "acquisition_cash_consideration",
                ("in cash",),
                support_terms=(
                    "definitive agreement to acquire WhatsApp",
                    "total of approximately $16 billion",
                ),
            ),
            _money(
                "What value did Facebook assign to the additional restricted stock units for WhatsApp’s founders and employees on {date}?",
                "$3 billion in restricted stock units",
                "$3 billion",
                3_000_000_000,
                "USD value of additional restricted stock unit awards",
                "Facebook today announced that it has reached a definitive agreement to acquire WhatsApp, a rapidly growing cross-platform mobile messaging company, for a total of approximately $16 billion, including $4 billion in cash and approximately $12 billion worth of Facebook shares. The agreement also provides for an additional $3 billion in restricted stock units to be granted to WhatsApp’s founders and employees that will vest over four years subsequent to closing.",
                "acquisition_employee_rsu_value",
                ("restricted stock units",),
                support_terms=(
                    "additional $3 billion in restricted stock units",
                    "will vest over four years subsequent to closing",
                ),
            ),
        ),
        "2014-02-19",
        ("February 19, 2014",),
    ),
    SourceSpec(
        "amd-xilinx-announcement-2020-corrected",
        "m_and_a",
        "official_merger_announcement",
        "AMD to Acquire Xilinx, Creating the Industry’s High Performance Computing Leader",
        "https://ir.amd.com/news-events/press-releases/detail/977/amd-to-acquire-xilinx-creating-the-industrys-high-performance-computing-leader",
        (
            _money(
                "What announced transaction value did AMD state for its planned Xilinx acquisition on {date}?",
                "$35 billion in an all-stock transaction",
                "$35 billion",
                35_000_000_000,
                "USD announced transaction value (all stock)",
                r"""<p>SILICON VALLEY, Calif., Oct.  27, 2020  (GLOBE NEWSWIRE) -- AMD (NASDAQ: AMD) and Xilinx (NASDAQ: XLNX) today announced they have entered into a definitive agreement for AMD to acquire Xilinx in an all-stock transaction valued at $35 billion. The combination will create the industry�s leading high performance computing company, significantly expanding the breadth of AMD�s product portfolio and customer set across diverse growth markets where Xilinx is an established leader. The transaction is expected to be immediately accretive to AMD margins, EPS and free cash flow generation and deliver industry-leading growth.</p>""",
                "announced_transaction_value",
                ("all-stock transaction", "valued at"),
                support_terms=("definitive agreement", "all-stock transaction valued at"),
            ),
            _ratio(
                "What fixed exchange ratio did AMD announce for Xilinx stockholders on {date}?",
                "1.7234 AMD shares for each Xilinx share",
                "1.7234",
                1.7234,
                "AMD shares per Xilinx share",
                r"""<p><strong>Additional Transaction Details</strong><br>Under the terms of the agreement, Xilinx stockholders will receive a fixed exchange ratio of 1.7234 shares of AMD common stock for each share of Xilinx common stock they hold at the closing of the transaction. Based on the exchange ratio, this represents approximately $143 per share of Xilinx common stock<sup>2</sup>. Post-closing, current AMD stockholders will own approximately 74 percent of the combined company on a fully diluted basis, while Xilinx stockholders will own approximately 26 percent. The transaction is intended to qualify as a tax-free reorganization for U.S. federal income tax purposes.</p>""",
                "share_exchange_ratio",
                support_terms=(
                    "fixed exchange ratio",
                    "shares of AMD common stock",
                    "for each share of Xilinx common stock",
                ),
            ),
        ),
        "2020-10-27",
    ),
    SourceSpec(
        "nvidia-mellanox-announcement-2019",
        "m_and_a",
        "official_merger_announcement",
        "NVIDIA to Acquire Mellanox for $6.9 Billion",
        "https://nvidianews.nvidia.com/news/nvidia-to-acquire-mellanox-for-6-9-billion",
        (
            _money(
                "What approximate enterprise value did NVIDIA announce for its proposed Mellanox acquisition on {date}?",
                "Approximately $6.9 billion in enterprise value",
                "$6.9 billion",
                6_900_000_000,
                "USD announced enterprise value (approximate)",
                "NVIDIA and Mellanox today announced that the companies have reached a definitive agreement under which NVIDIA will acquire Mellanox. Pursuant to the agreement, NVIDIA will acquire all of the issued and outstanding common shares of Mellanox for $125 per share in cash, representing a total enterprise value of approximately $6.9 billion.",
                "announced_enterprise_value",
                ("enterprise value", "approximately"),
                support_terms=("total enterprise value of approximately",),
            ),
            _money(
                "What per-share cash price did NVIDIA announce for Mellanox on {date}?",
                "$125 per Mellanox share in cash",
                "$125",
                125,
                "USD per Mellanox share",
                "NVIDIA and Mellanox today announced that the companies have reached a definitive agreement under which NVIDIA will acquire Mellanox. Pursuant to the agreement, NVIDIA will acquire all of the issued and outstanding common shares of Mellanox for $125 per share in cash, representing a total enterprise value of approximately $6.9 billion.",
                "per_share_cash_consideration",
                ("per share", "cash"),
                support_terms=("for $125 per share in cash",),
            ),
        ),
        "2019-03-11",
        ("March 11, 2019",),
    ),
)

# AMD's HTML response stores normal U+2019 apostrophes, while the initial
# hand-transcribed quote used U+FFFD. Repair the excerpt against the bytes.
_M_AND_A_BACKUPS = tuple(
    replace(
        source,
        facts=tuple(
            replace(fact, excerpt=fact.excerpt.replace("\ufffd", "\u2019")) for fact in source.facts
        ),
    )
    if source.source_record_id == "amd-xilinx-announcement-2020-corrected"
    else source
    for source in _M_AND_A_BACKUPS
)
