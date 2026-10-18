"""Map eval_v2 case IDs to their query-gold category without reading canonical records."""

from __future__ import annotations

from query_gold.validation import CATEGORY_IDS

_PREFIX_TO_CATEGORY: dict[str, str] = {
    "fin": "01_earnings_corporate_finance",
    "clinical": "02_biomedical_clinical_trials",
    "code_api": "03_code_api_documentation",
    "venture": "04_venture_capital_funding_ma",
    "legal": "05_government_courts_legal",
    "hw": "06_hardware_product_specifications",
    "math": "07_static_mathematics_stem",
    "sports": "08_sports_box_scores_game_stats",
    "re": "09_real_estate_land_registries",
    "acad": "10_academic_literature_citations",
    "cve": "11_cybersecurity_vulnerability_tracking",
    "muni": "12_municipal_code_zoning_local_law",
    "log": "13_logistics_freight_supply_chain",
    "aero": "14_aerospace_telemetry_records",
    "cloud": "15_cloud_infrastructure_service_pricing",
    "art": "16_art_collectibles_auction_transactions",
    "municipal": "17_local_graph_municipal_pois_directory_lookups",
    "media": "18_entertainment_box_office_media_registries",
    "imm": "19_immigration_visa_bulletins_consular_policies",
    "weather": "20_historical_meteorology_disaster_telemetry",
    "gaming": "21_gaming_software_release_patch_telemetry",
    "consumer": "22_consumer_ecommerce_msrp_recall_notices",
    "exec": "23_executive_directory_corporate_leadership",
    "standards": "24_standards_rfcs_technical_specifications",
}
if sorted(_PREFIX_TO_CATEGORY.values()) != sorted(CATEGORY_IDS):
    raise RuntimeError("case-ID prefix map must cover every query-gold category exactly once")


def category_for(case_id: str) -> str:
    """Return the category for an eval_v2 case ID; unknown prefixes are rejected."""
    prefix = "code_api" if case_id.startswith("code_api_") else case_id.split("-", 1)[0]
    try:
        return _PREFIX_TO_CATEGORY[prefix]
    except KeyError:
        raise ValueError(f"case ID has no known category prefix: {case_id[:64]}") from None
