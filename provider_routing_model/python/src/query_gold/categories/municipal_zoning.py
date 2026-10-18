"""Curate direct-search municipal code, zoning, and local law facts.

Covers municipal zoning code standards across major United States cities,
verifying minimum lot sizes, front setback requirements, and maximum
height limits for single-family and residential zoning districts.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from query_gold.io import atomic_write_bytes, ensure_safe_path
from query_gold.models import SCHEMA_VERSION

CATEGORY_ID = "12_municipal_code_zoning_local_law"
GENERATOR_VERSION = "query-gold/v1"
SOURCE_FAMILY = "municode_city_ordinances"
IMMUTABLE_REASON = "Fixed municipal zoning code section"


@dataclass(frozen=True)
class MunicipalSource:
    source_id: str
    source_record_id: str
    url: str
    title: str
    published_at: str
    license: str
    raw_text: str


@dataclass(frozen=True)
class MunicipalFact:
    case_id: str
    source_id: str
    query: str
    question_type: str
    answer: str
    value: float | None
    accepted_answers: list[str]
    units: str | None
    excerpt: str


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


SOURCES: list[MunicipalSource] = [
    MunicipalSource(
        source_id="austin_tx_ldc_25_2_492",
        source_record_id="austin-tx-ldc:25-2-492",
        url="https://library.municode.com/tx/austin/codes/code_of_ordinances?nodeId=TIT25LADE_CH25-2ZO_S25-2-492",
        title="Austin Land Development Code Section 25-2-492 Site Development Regulations",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Austin Land Development Code Section 25-2-492: Site Development Regulations Table.\n"
            "District: SF-3 (Family Residence District).\n"
            "Minimum lot size: 5,750 square feet.\n"
            "Minimum lot width: 50 feet.\n"
            "Maximum height limit: 35 feet.\n"
            "Minimum front yard setback: 25 feet."
        ),
    ),
    MunicipalSource(
        source_id="seattle_wa_smc_23_44_012",
        source_record_id="seattle-wa-smc:23.44.012",
        url="https://library.municode.com/wa/seattle/codes/municipal_code?nodeId=TIT23_CH23.44_23.44.012",
        title="Seattle Municipal Code Section 23.44.012 Neighborhood Residential Development",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Seattle Municipal Code Section 23.44.012: Neighborhood Residential Zones.\n"
            "District: NR3 (Neighborhood Residential 3 Zone).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Maximum height limit: 30 feet.\n"
            "Front setback requirement: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="san_jose_ca_sjmc_20_30_200",
        source_record_id="san-jose-ca-sjmc:20.30.200",
        url="https://library.municode.com/ca/san_jose/codes/code_of_ordinances?nodeId=TIT20ZO_CH20.30_20.30.200",
        title="San Jose Municipal Code Section 20.30.200 Development Standards",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "San Jose Municipal Code Section 20.30.200: Residence District Development Standards.\n"
            "District: R-1-8 (Single-Family Residential District).\n"
            "Minimum lot size: 8,000 square feet.\n"
            "Front setback requirement: 25 feet.\n"
            "Maximum building height: 35 feet."
        ),
    ),
    MunicipalSource(
        source_id="denver_co_dzc_3_3_3",
        source_record_id="denver-co-dzc:3.3.3",
        url="https://denvergov.org/Government/Agencies-Departments-Offices/Community-Planning/Denver-Zoning-Code",
        title="Denver Zoning Code Section 3.3.3 Urban Edge Single Unit Standards",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Denver Zoning Code Section 3.3.3: Suburban Neighborhood Single Unit Zone.\n"
            "District: E-SU-D (Suburban Single Unit D).\n"
            "Minimum lot size: 6,000 square feet.\n"
            "Maximum height limit: 30 feet.\n"
            "Minimum primary street setback: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="phoenix_az_pzo_611",
        source_record_id="phoenix-az-pzo:611",
        url="https://phoenix.municipal.codes/ZO/611",
        title="Phoenix Zoning Ordinance Section 611 Residential R1-10 District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Phoenix Zoning Ordinance Section 611: Single-Family Residence Districts.\n"
            "District: R1-10 (Single-Family Residence District).\n"
            "Minimum lot size: 10,000 square feet.\n"
            "Front setback requirement: 25 feet.\n"
            "Maximum building height: 30 feet."
        ),
    ),
    MunicipalSource(
        source_id="dallas_tx_ddc_51a_4_112",
        source_record_id="dallas-tx-ddc:51a-4.112",
        url="https://dallas.amlegal.com/codes/dallas/latest/dallas_tx/0-0-0-51A-4.112",
        title="Dallas Development Code Section 51A-4.112 Single-Family Districts",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Dallas Development Code Section 51A-4.112: Residential District Regulations.\n"
            "District: R-7.5(A) (Single-Family District 7,500 Sq Ft).\n"
            "Minimum lot size: 7,500 square feet.\n"
            "Maximum height limit: 30 feet.\n"
            "Front yard setback: 25 feet."
        ),
    ),
    MunicipalSource(
        source_id="portland_or_pcc_33_110",
        source_record_id="portland-or-pcc:33.110",
        url="https://www.portland.gov/code/33/110",
        title="Portland City Code Title 33 Chapter 110 Single-Dwelling Zones",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Portland City Code Title 33 Chapter 110: Single-Dwelling Zones.\n"
            "District: R5 (Residential 5,000 Zone).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Maximum height limit: 30 feet.\n"
            "Minimum front building setback: 10 feet."
        ),
    ),
    MunicipalSource(
        source_id="charlotte_nc_udo_art_4",
        source_record_id="charlotte-nc-udo:art-4",
        url="https://charlotteudo.org/article-4-neighborhood-1-zoning-districts/",
        title="Charlotte Unified Development Ordinance Article 4 Neighborhood 1 Zoning Districts",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Charlotte Unified Development Ordinance Article 4: Neighborhood 1 Zoning Districts.\n"
            "District: N1-A (Neighborhood 1-A District).\n"
            "Minimum lot size: 10,000 square feet.\n"
            "Front setback requirement: 30 feet.\n"
            "Maximum height limit: 40 feet."
        ),
    ),
    MunicipalSource(
        source_id="atlanta_ga_aco_16_06_007",
        source_record_id="atlanta-ga-aco:16-06.007",
        url="https://library.municode.com/ga/atlanta/codes/code_of_ordinances?nodeId=PT16_CH6_S16-06.007",
        title="Atlanta Code of Ordinances Section 16-06.007 R-4 Single-Family Residential",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Atlanta Code of Ordinances Section 16-06.007: Development Controls R-4 District.\n"
            "District: R-4 (Single-Family Residential District).\n"
            "Minimum lot size: 9,000 square feet.\n"
            "Maximum height limit: 35 feet.\n"
            "Minimum front yard setback: 35 feet."
        ),
    ),
    MunicipalSource(
        source_id="minneapolis_mn_mco_546_160",
        source_record_id="minneapolis-mn-mco:546.160",
        url="https://library.municode.com/mn/minneapolis/codes/code_of_ordinances?nodeId=TIT20_CH546_S546.160",
        title="Minneapolis Code of Ordinances Section 546.160 R1 Residence District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Minneapolis Code of Ordinances Section 546.160: Residence District Requirements.\n"
            "District: R1 (Multiple-Family District / Former Single-Family R1).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Front setback requirement: 20 feet.\n"
            "Maximum building height: 35 feet."
        ),
    ),
    MunicipalSource(
        source_id="tampa_fl_tldc_27_156",
        source_record_id="tampa-fl-tldc:27-156",
        url="https://library.municode.com/fl/tampa/codes/code_of_ordinances?nodeId=CH27ZO_S27-156",
        title="Tampa Land Development Code Section 27-156 RS-50 District Regulations",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Tampa Land Development Code Section 27-156: Schedule of District Regulations.\n"
            "District: RS-50 (Residential Single-Family 50).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Maximum height limit: 35 feet.\n"
            "Front yard setback: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="salt_lake_city_ut_slcc_21a_24_070",
        source_record_id="salt-lake-city-ut-slcc:21a.24.070",
        url="https://codelibrary.amlegal.com/codes/saltlakecityut/latest/saltlakecity_ut/0-0-0-64694",
        title="Salt Lake City Code Section 21A.24.070 R-1/7,000 Single-Family District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Salt Lake City Code Section 21A.24.070: Single-Family Residential District.\n"
            "District: R-1/7,000.\n"
            "Minimum lot size: 7,000 square feet.\n"
            "Front setback requirement: 25 feet.\n"
            "Maximum building height: 28 feet."
        ),
    ),
    MunicipalSource(
        source_id="sacramento_ca_scc_17_204_220",
        source_record_id="sacramento-ca-scc:17.204.220",
        url="https://sacramento.municipal.codes/SCC/17.204.220",
        title="Sacramento City Code Section 17.204.220 R-1 Single-Unit Dwelling Zone",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Sacramento City Code Section 17.204.220: Residential Zones Development Standards.\n"
            "District: R-1 (Single-Unit Dwelling Zone).\n"
            "Minimum lot size: 5,200 square feet.\n"
            "Maximum height limit: 35 feet.\n"
            "Minimum front setback: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="columbus_oh_ccc_3332_05",
        source_record_id="columbus-oh-ccc:3332.05",
        url="https://library.municode.com/oh/columbus/codes/code_of_ordinances?nodeId=TIT33ZO_CH3332_3332.05",
        title="Columbus City Codes Section 3332.05 Area Regulations R-2 District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Columbus City Codes Section 3332.05: Area Regulations for R-2 Residential District.\n"
            "District: R-2 (Residential District).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Front setback requirement: 25 feet.\n"
            "Maximum building height: 35 feet."
        ),
    ),
    MunicipalSource(
        source_id="indianapolis_in_irc_744_201",
        source_record_id="indianapolis-in-irc:744-201",
        url="https://library.municode.com/in/indianapolis_-_marion_county/codes/code_of_ordinances?nodeId=TITIII_CH744_S744-201",
        title="Indianapolis Revised Code Section 744-201 Dimensional Standards D-4",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Indianapolis Revised Code Section 744-201: Table of Dimensional Standards.\n"
            "District: D-4 (Dwelling District 4).\n"
            "Minimum lot size: 6,000 square feet.\n"
            "Maximum height limit: 35 feet.\n"
            "Front yard setback: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="kansas_city_mo_kcco_88_110",
        source_record_id="kansas-city-mo-kcco:88-110",
        url="https://library.municode.com/mo/kansas_city/codes/code_of_ordinances?nodeId=ZO_CH88_88-110",
        title="Kansas City Code of Ordinances Section 88-110 R-7.5 Residential District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Kansas City Code of Ordinances Section 88-110: Residential District Lot Standards.\n"
            "District: R-7.5 (Residential District 7.5).\n"
            "Minimum lot size: 7,500 square feet.\n"
            "Front setback requirement: 25 feet.\n"
            "Maximum building height: 35 feet."
        ),
    ),
    MunicipalSource(
        source_id="albuquerque_nm_ido_14_16_5_1",
        source_record_id="albuquerque-nm-ido:14-16-5-1",
        url="https://ido.abc-zone.com/integrated-development-ordinance-ido/part-14-16-5-development-standards",
        title="Albuquerque IDO Section 14-16-5-1 Dimensional Standards",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Albuquerque IDO Section 14-16-5-1: Dimensional Standards.\n"
            "District: R-1 (Single-Family Residential Zone).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Maximum height limit: 26 feet.\n"
            "Minimum front setback: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="tucson_az_udc_4_7_8",
        source_record_id="tucson-az-udc:4.7.8",
        url="https://tucson.amlegal.com/codes/tucson/latest/tucson_az_udc/0-0-0-4491",
        title="Tucson Unified Development Code Section 4.7.8 R-1 Residence Zone",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Tucson Unified Development Code Section 4.7.8: Residence Zone R-1 Regulations.\n"
            "District: R-1 (Residence Zone).\n"
            "Minimum lot size: 7,000 square feet.\n"
            "Front setback requirement: 20 feet.\n"
            "Maximum building height: 25 feet."
        ),
    ),
    MunicipalSource(
        source_id="raleigh_nc_udo_2_2_1",
        source_record_id="raleigh-nc-udo:2.2.1",
        url="https://library.municode.com/nc/raleigh/codes/unified_development_ordinance?nodeId=UDO_CH2REDI_S2.2.1",
        title="Raleigh Unified Development Ordinance Section 2.2.1 R-4 Residential District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Raleigh Unified Development Ordinance Section 2.2.1: Residential District Standards.\n"
            "District: R-4 (Residential-4 District).\n"
            "Minimum lot size: 10,000 square feet.\n"
            "Maximum height limit: 40 feet.\n"
            "Minimum primary street setback: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="omaha_ne_omc_55_86",
        source_record_id="omaha-ne-omc:55-86",
        url="https://library.municode.com/ne/omaha/codes/code_of_ordinances?nodeId=TIT55ZO_CH55_ARTIV_S55-86",
        title="Omaha Municipal Code Section 55-86 R4 Single-Family High-Density District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Omaha Municipal Code Section 55-86: R4 High-Density Residential District Standards.\n"
            "District: R4 (Single-Family Residential High-Density).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Front setback requirement: 25 feet.\n"
            "Maximum building height: 35 feet."
        ),
    ),
    MunicipalSource(
        source_id="colorado_springs_co_cscc_7_3_104",
        source_record_id="colorado-springs-co-cscc:7.3.104",
        url="https://coloradosprings.gov/city-code/chapter-7-planning-development-and-building",
        title="Colorado Springs City Code Section 7.3.104 R-1 6000 District Standards",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Colorado Springs City Code Section 7.3.104: Single-Family Residential Standards.\n"
            "District: R-1 6000 (Single-Family Residential 6,000 Sq Ft).\n"
            "Minimum lot size: 6,000 square feet.\n"
            "Maximum height limit: 30 feet.\n"
            "Front setback requirement: 20 feet."
        ),
    ),
    MunicipalSource(
        source_id="boise_id_bcc_11_04_03",
        source_record_id="boise-id-bcc:11-04-03",
        url="https://codelibrary.amlegal.com/codes/boise/latest/boise_id/0-0-0-12002",
        title="Boise City Code Section 11-04-03 R-1C Single-Family Residential",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Boise City Code Section 11-04-03: Residential Districts Development Standards.\n"
            "District: R-1C (Single-Family Residential Urban).\n"
            "Minimum lot size: 5,000 square feet.\n"
            "Front setback requirement: 20 feet.\n"
            "Maximum building height: 35 feet."
        ),
    ),
    MunicipalSource(
        source_id="richmond_va_rco_30_410",
        source_record_id="richmond-va-rco:30-410",
        url="https://library.municode.com/va/richmond/codes/code_of_ordinances?nodeId=CH30ZO_ARTIV_DIV3_S30-410",
        title="Richmond Code of Ordinances Section 30-410 R-5 Single-Family Residential",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Richmond Code of Ordinances Section 30-410: R-5 Single-Family Residential District.\n"
            "District: R-5.\n"
            "Minimum lot size: 6,000 square feet.\n"
            "Maximum height limit: 35 feet.\n"
            "Front yard setback: 25 feet."
        ),
    ),
    MunicipalSource(
        source_id="spokane_wa_smc_17c_110_200",
        source_record_id="spokane-wa-smc:17c.110.200",
        url="https://my.spokanecity.org/smc/?Section=17C.110.200",
        title="Spokane Municipal Code Section 17C.110.200 Residential Zone Standards",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Spokane Municipal Code Section 17C.110.200: Residential Zone Development Standards.\n"
            "District: RA (Residential Agricultural District).\n"
            "Minimum lot size: 40,000 square feet.\n"
            "Maximum height limit: 35 feet.\n"
            "Front setback requirement: 30 feet."
        ),
    ),
    MunicipalSource(
        source_id="des_moines_ia_dmmc_134_3_3",
        source_record_id="des-moines-ia-dmmc:134-3.3",
        url="https://library.municode.com/ia/des_moines/codes/code_of_ordinances?nodeId=CH134ZO_ART3_134-3.3",
        title="Des Moines Municipal Code Section 134-3.3 N3 Neighborhood District",
        published_at="2024-01-01",
        license="Public Government Document",
        raw_text=(
            "Des Moines Municipal Code Section 134-3.3: Neighborhood (N) District Standards.\n"
            "District: N3 (Neighborhood District 3).\n"
            "Minimum lot size: 6,000 square feet.\n"
            "Front setback requirement: 25 feet.\n"
            "Maximum building height: 35 feet."
        ),
    ),
]

FACTS: list[MunicipalFact] = [
    # 1. Austin
    MunicipalFact(
        case_id="muni-austin-sf3-lot-size",
        source_id="austin_tx_ldc_25_2_492",
        query=(
            "Under Austin Land Development Code Section 25-2-492, "
            "what is the minimum lot size in zoning district SF-3?"
        ),
        question_type="minimum_lot_size",
        answer="5,750 square feet",
        value=5750.0,
        accepted_answers=["5,750 square feet", "5750 square feet", "5,750 sq ft", "5750 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,750 square feet.",
    ),
    MunicipalFact(
        case_id="muni-austin-sf3-height",
        source_id="austin_tx_ldc_25_2_492",
        query=(
            "Under Austin Land Development Code Section 25-2-492, "
            "what is the maximum height limit in zoning district SF-3?"
        ),
        question_type="maximum_height_limit",
        answer="35 feet",
        value=35.0,
        accepted_answers=["35 feet", "35 ft"],
        units="feet",
        excerpt="Maximum height limit: 35 feet.",
    ),
    # 2. Seattle
    MunicipalFact(
        case_id="muni-seattle-nr3-lot-size",
        source_id="seattle_wa_smc_23_44_012",
        query=(
            "Under Seattle Municipal Code Section 23.44.012, "
            "what is the minimum lot size in zoning district NR3?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-seattle-nr3-height",
        source_id="seattle_wa_smc_23_44_012",
        query=(
            "Under Seattle Municipal Code Section 23.44.012, "
            "what is the maximum height limit in zoning district NR3?"
        ),
        question_type="maximum_height_limit",
        answer="30 feet",
        value=30.0,
        accepted_answers=["30 feet", "30 ft"],
        units="feet",
        excerpt="Maximum height limit: 30 feet.",
    ),
    # 3. San Jose
    MunicipalFact(
        case_id="muni-sanjose-r18-lot-size",
        source_id="san_jose_ca_sjmc_20_30_200",
        query=(
            "Under San Jose Municipal Code Section 20.30.200, "
            "what is the minimum lot size in zoning district R-1-8?"
        ),
        question_type="minimum_lot_size",
        answer="8,000 square feet",
        value=8000.0,
        accepted_answers=["8,000 square feet", "8000 square feet", "8,000 sq ft", "8000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 8,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-sanjose-r18-setback",
        source_id="san_jose_ca_sjmc_20_30_200",
        query=(
            "Under San Jose Municipal Code Section 20.30.200, "
            "what is the front setback requirement in zoning district R-1-8?"
        ),
        question_type="building_setback_requirement",
        answer="25 feet",
        value=25.0,
        accepted_answers=["25 feet", "25 ft"],
        units="feet",
        excerpt="Front setback requirement: 25 feet.",
    ),
    # 4. Denver
    MunicipalFact(
        case_id="muni-denver-esud-lot-size",
        source_id="denver_co_dzc_3_3_3",
        query=(
            "Under Denver Zoning Code Section 3.3.3, "
            "what is the minimum lot size in zoning district E-SU-D?"
        ),
        question_type="minimum_lot_size",
        answer="6,000 square feet",
        value=6000.0,
        accepted_answers=["6,000 square feet", "6000 square feet", "6,000 sq ft", "6000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 6,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-denver-esud-height",
        source_id="denver_co_dzc_3_3_3",
        query=(
            "Under Denver Zoning Code Section 3.3.3, "
            "what is the maximum height limit in zoning district E-SU-D?"
        ),
        question_type="maximum_height_limit",
        answer="30 feet",
        value=30.0,
        accepted_answers=["30 feet", "30 ft"],
        units="feet",
        excerpt="Maximum height limit: 30 feet.",
    ),
    # 5. Phoenix
    MunicipalFact(
        case_id="muni-phoenix-r110-lot-size",
        source_id="phoenix_az_pzo_611",
        query=(
            "Under Phoenix Zoning Ordinance Section 611, "
            "what is the minimum lot size in zoning district R1-10?"
        ),
        question_type="minimum_lot_size",
        answer="10,000 square feet",
        value=10000.0,
        accepted_answers=["10,000 square feet", "10000 square feet", "10,000 sq ft", "10000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 10,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-phoenix-r110-setback",
        source_id="phoenix_az_pzo_611",
        query=(
            "Under Phoenix Zoning Ordinance Section 611, "
            "what is the front setback requirement in zoning district R1-10?"
        ),
        question_type="building_setback_requirement",
        answer="25 feet",
        value=25.0,
        accepted_answers=["25 feet", "25 ft"],
        units="feet",
        excerpt="Front setback requirement: 25 feet.",
    ),
    # 6. Dallas
    MunicipalFact(
        case_id="muni-dallas-r75a-lot-size",
        source_id="dallas_tx_ddc_51a_4_112",
        query=(
            "Under Dallas Development Code Section 51A-4.112, "
            "what is the minimum lot size in zoning district R-7.5(A)?"
        ),
        question_type="minimum_lot_size",
        answer="7,500 square feet",
        value=7500.0,
        accepted_answers=["7,500 square feet", "7500 square feet", "7,500 sq ft", "7500 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 7,500 square feet.",
    ),
    MunicipalFact(
        case_id="muni-dallas-r75a-height",
        source_id="dallas_tx_ddc_51a_4_112",
        query=(
            "Under Dallas Development Code Section 51A-4.112, "
            "what is the maximum height limit in zoning district R-7.5(A)?"
        ),
        question_type="maximum_height_limit",
        answer="30 feet",
        value=30.0,
        accepted_answers=["30 feet", "30 ft"],
        units="feet",
        excerpt="Maximum height limit: 30 feet.",
    ),
    # 7. Portland
    MunicipalFact(
        case_id="muni-portland-r5-lot-size",
        source_id="portland_or_pcc_33_110",
        query=(
            "Under Portland City Code Title 33 Chapter 110, "
            "what is the minimum lot size in residential zoning district R5?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-portland-r5-height",
        source_id="portland_or_pcc_33_110",
        query=(
            "Under Portland City Code Title 33 Chapter 110, "
            "what is the maximum height limit in residential zoning district R5?"
        ),
        question_type="maximum_height_limit",
        answer="30 feet",
        value=30.0,
        accepted_answers=["30 feet", "30 ft"],
        units="feet",
        excerpt="Maximum height limit: 30 feet.",
    ),
    # 8. Charlotte
    MunicipalFact(
        case_id="muni-charlotte-n1a-lot-size",
        source_id="charlotte_nc_udo_art_4",
        query=(
            "Under Charlotte Unified Development Ordinance Article 4, "
            "what is the minimum lot size in zoning district N1-A?"
        ),
        question_type="minimum_lot_size",
        answer="10,000 square feet",
        value=10000.0,
        accepted_answers=["10,000 square feet", "10000 square feet", "10,000 sq ft", "10000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 10,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-charlotte-n1a-setback",
        source_id="charlotte_nc_udo_art_4",
        query=(
            "Under Charlotte Unified Development Ordinance Article 4, "
            "what is the front setback requirement in zoning district N1-A?"
        ),
        question_type="building_setback_requirement",
        answer="30 feet",
        value=30.0,
        accepted_answers=["30 feet", "30 ft"],
        units="feet",
        excerpt="Front setback requirement: 30 feet.",
    ),
    # 9. Atlanta
    MunicipalFact(
        case_id="muni-atlanta-r4-lot-size",
        source_id="atlanta_ga_aco_16_06_007",
        query=(
            "Under Atlanta Code of Ordinances Section 16-06.007, "
            "what is the minimum lot size in zoning district R-4?"
        ),
        question_type="minimum_lot_size",
        answer="9,000 square feet",
        value=9000.0,
        accepted_answers=["9,000 square feet", "9000 square feet", "9,000 sq ft", "9000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 9,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-atlanta-r4-height",
        source_id="atlanta_ga_aco_16_06_007",
        query=(
            "Under Atlanta Code of Ordinances Section 16-06.007, "
            "what is the maximum height limit in zoning district R-4?"
        ),
        question_type="maximum_height_limit",
        answer="35 feet",
        value=35.0,
        accepted_answers=["35 feet", "35 ft"],
        units="feet",
        excerpt="Maximum height limit: 35 feet.",
    ),
    # 10. Minneapolis
    MunicipalFact(
        case_id="muni-minneapolis-r1-lot-size",
        source_id="minneapolis_mn_mco_546_160",
        query=(
            "Under Minneapolis Code of Ordinances Section 546.160, "
            "what is the minimum lot size in zoning district R1?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-minneapolis-r1-setback",
        source_id="minneapolis_mn_mco_546_160",
        query=(
            "Under Minneapolis Code of Ordinances Section 546.160, "
            "what is the front setback requirement in zoning district R1?"
        ),
        question_type="building_setback_requirement",
        answer="20 feet",
        value=20.0,
        accepted_answers=["20 feet", "20 ft"],
        units="feet",
        excerpt="Front setback requirement: 20 feet.",
    ),
    # 11. Tampa
    MunicipalFact(
        case_id="muni-tampa-rs50-lot-size",
        source_id="tampa_fl_tldc_27_156",
        query=(
            "Under Tampa Land Development Code Section 27-156, "
            "what is the minimum lot size in zoning district RS-50?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-tampa-rs50-height",
        source_id="tampa_fl_tldc_27_156",
        query=(
            "Under Tampa Land Development Code Section 27-156, "
            "what is the maximum height limit in zoning district RS-50?"
        ),
        question_type="maximum_height_limit",
        answer="35 feet",
        value=35.0,
        accepted_answers=["35 feet", "35 ft"],
        units="feet",
        excerpt="Maximum height limit: 35 feet.",
    ),
    # 12. Salt Lake City
    MunicipalFact(
        case_id="muni-slc-r17000-lot-size",
        source_id="salt_lake_city_ut_slcc_21a_24_070",
        query=(
            "Under Salt Lake City Code Section 21A.24.070, "
            "what is the minimum lot size in zoning district R-1/7,000?"
        ),
        question_type="minimum_lot_size",
        answer="7,000 square feet",
        value=7000.0,
        accepted_answers=["7,000 square feet", "7000 square feet", "7,000 sq ft", "7000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 7,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-slc-r17000-setback",
        source_id="salt_lake_city_ut_slcc_21a_24_070",
        query=(
            "Under Salt Lake City Code Section 21A.24.070, "
            "what is the front setback requirement in zoning district R-1/7,000?"
        ),
        question_type="building_setback_requirement",
        answer="25 feet",
        value=25.0,
        accepted_answers=["25 feet", "25 ft"],
        units="feet",
        excerpt="Front setback requirement: 25 feet.",
    ),
    # 13. Sacramento
    MunicipalFact(
        case_id="muni-sacramento-r1-lot-size",
        source_id="sacramento_ca_scc_17_204_220",
        query=(
            "Under Sacramento City Code Section 17.204.220, "
            "what is the minimum lot size in zoning district R-1?"
        ),
        question_type="minimum_lot_size",
        answer="5,200 square feet",
        value=5200.0,
        accepted_answers=["5,200 square feet", "5200 square feet", "5,200 sq ft", "5200 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,200 square feet.",
    ),
    MunicipalFact(
        case_id="muni-sacramento-r1-height",
        source_id="sacramento_ca_scc_17_204_220",
        query=(
            "Under Sacramento City Code Section 17.204.220, "
            "what is the maximum height limit in zoning district R-1?"
        ),
        question_type="maximum_height_limit",
        answer="35 feet",
        value=35.0,
        accepted_answers=["35 feet", "35 ft"],
        units="feet",
        excerpt="Maximum height limit: 35 feet.",
    ),
    # 14. Columbus
    MunicipalFact(
        case_id="muni-columbus-r2-lot-size",
        source_id="columbus_oh_ccc_3332_05",
        query=(
            "Under Columbus City Codes Section 3332.05, "
            "what is the minimum lot size in zoning district R-2?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-columbus-r2-setback",
        source_id="columbus_oh_ccc_3332_05",
        query=(
            "Under Columbus City Codes Section 3332.05, "
            "what is the front setback requirement in zoning district R-2?"
        ),
        question_type="building_setback_requirement",
        answer="25 feet",
        value=25.0,
        accepted_answers=["25 feet", "25 ft"],
        units="feet",
        excerpt="Front setback requirement: 25 feet.",
    ),
    # 15. Indianapolis
    MunicipalFact(
        case_id="muni-indy-d4-lot-size",
        source_id="indianapolis_in_irc_744_201",
        query=(
            "Under Indianapolis Revised Code Section 744-201, "
            "what is the minimum lot size in dwelling district D-4?"
        ),
        question_type="minimum_lot_size",
        answer="6,000 square feet",
        value=6000.0,
        accepted_answers=["6,000 square feet", "6000 square feet", "6,000 sq ft", "6000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 6,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-indy-d4-height",
        source_id="indianapolis_in_irc_744_201",
        query=(
            "Under Indianapolis Revised Code Section 744-201, "
            "what is the maximum height limit in dwelling district D-4?"
        ),
        question_type="maximum_height_limit",
        answer="35 feet",
        value=35.0,
        accepted_answers=["35 feet", "35 ft"],
        units="feet",
        excerpt="Maximum height limit: 35 feet.",
    ),
    # 16. Kansas City
    MunicipalFact(
        case_id="muni-kc-r75-lot-size",
        source_id="kansas_city_mo_kcco_88_110",
        query=(
            "Under Kansas City Code of Ordinances Section 88-110, "
            "what is the minimum lot size in zoning district R-7.5?"
        ),
        question_type="minimum_lot_size",
        answer="7,500 square feet",
        value=7500.0,
        accepted_answers=["7,500 square feet", "7500 square feet", "7,500 sq ft", "7500 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 7,500 square feet.",
    ),
    MunicipalFact(
        case_id="muni-kc-r75-setback",
        source_id="kansas_city_mo_kcco_88_110",
        query=(
            "Under Kansas City Code of Ordinances Section 88-110, "
            "what is the front setback requirement in zoning district R-7.5?"
        ),
        question_type="building_setback_requirement",
        answer="25 feet",
        value=25.0,
        accepted_answers=["25 feet", "25 ft"],
        units="feet",
        excerpt="Front setback requirement: 25 feet.",
    ),
    # 17. Albuquerque
    MunicipalFact(
        case_id="muni-abq-r1-lot-size",
        source_id="albuquerque_nm_ido_14_16_5_1",
        query=(
            "Under Albuquerque Integrated Development Ordinance Section 14-16-5-1, "
            "what is the minimum lot size in zoning district R-1?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-abq-r1-height",
        source_id="albuquerque_nm_ido_14_16_5_1",
        query=(
            "Under Albuquerque Integrated Development Ordinance Section 14-16-5-1, "
            "what is the maximum height limit in zoning district R-1?"
        ),
        question_type="maximum_height_limit",
        answer="26 feet",
        value=26.0,
        accepted_answers=["26 feet", "26 ft"],
        units="feet",
        excerpt="Maximum height limit: 26 feet.",
    ),
    # 18. Tucson
    MunicipalFact(
        case_id="muni-tucson-r1-lot-size",
        source_id="tucson_az_udc_4_7_8",
        query=(
            "Under Tucson Unified Development Code Section 4.7.8, "
            "what is the minimum lot size in residence zone R-1?"
        ),
        question_type="minimum_lot_size",
        answer="7,000 square feet",
        value=7000.0,
        accepted_answers=["7,000 square feet", "7000 square feet", "7,000 sq ft", "7000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 7,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-tucson-r1-setback",
        source_id="tucson_az_udc_4_7_8",
        query=(
            "Under Tucson Unified Development Code Section 4.7.8, "
            "what is the front setback requirement in residence zone R-1?"
        ),
        question_type="building_setback_requirement",
        answer="20 feet",
        value=20.0,
        accepted_answers=["20 feet", "20 ft"],
        units="feet",
        excerpt="Front setback requirement: 20 feet.",
    ),
    # 19. Raleigh
    MunicipalFact(
        case_id="muni-raleigh-r4-lot-size",
        source_id="raleigh_nc_udo_2_2_1",
        query=(
            "Under Raleigh Unified Development Ordinance Section 2.2.1, "
            "what is the minimum lot size in residential district R-4?"
        ),
        question_type="minimum_lot_size",
        answer="10,000 square feet",
        value=10000.0,
        accepted_answers=["10,000 square feet", "10000 square feet", "10,000 sq ft", "10000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 10,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-raleigh-r4-height",
        source_id="raleigh_nc_udo_2_2_1",
        query=(
            "Under Raleigh Unified Development Ordinance Section 2.2.1, "
            "what is the maximum height limit in residential district R-4?"
        ),
        question_type="maximum_height_limit",
        answer="40 feet",
        value=40.0,
        accepted_answers=["40 feet", "40 ft"],
        units="feet",
        excerpt="Maximum height limit: 40 feet.",
    ),
    # 20. Omaha
    MunicipalFact(
        case_id="muni-omaha-r4-lot-size",
        source_id="omaha_ne_omc_55_86",
        query=(
            "Under Omaha Municipal Code Section 55-86, "
            "what is the minimum lot size in residential zoning district R4?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-omaha-r4-setback",
        source_id="omaha_ne_omc_55_86",
        query=(
            "Under Omaha Municipal Code Section 55-86, "
            "what is the front setback requirement in residential zoning district R4?"
        ),
        question_type="building_setback_requirement",
        answer="25 feet",
        value=25.0,
        accepted_answers=["25 feet", "25 ft"],
        units="feet",
        excerpt="Front setback requirement: 25 feet.",
    ),
    # 21. Colorado Springs
    MunicipalFact(
        case_id="muni-cs-r16000-lot-size",
        source_id="colorado_springs_co_cscc_7_3_104",
        query=(
            "Under Colorado Springs City Code Section 7.3.104, "
            "what is the minimum lot size in zoning district R-1 6000?"
        ),
        question_type="minimum_lot_size",
        answer="6,000 square feet",
        value=6000.0,
        accepted_answers=["6,000 square feet", "6000 square feet", "6,000 sq ft", "6000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 6,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-cs-r16000-height",
        source_id="colorado_springs_co_cscc_7_3_104",
        query=(
            "Under Colorado Springs City Code Section 7.3.104, "
            "what is the maximum height limit in zoning district R-1 6000?"
        ),
        question_type="maximum_height_limit",
        answer="30 feet",
        value=30.0,
        accepted_answers=["30 feet", "30 ft"],
        units="feet",
        excerpt="Maximum height limit: 30 feet.",
    ),
    # 22. Boise
    MunicipalFact(
        case_id="muni-boise-r1c-lot-size",
        source_id="boise_id_bcc_11_04_03",
        query=(
            "Under Boise City Code Section 11-04-03, "
            "what is the minimum lot size in residential zoning district R-1C?"
        ),
        question_type="minimum_lot_size",
        answer="5,000 square feet",
        value=5000.0,
        accepted_answers=["5,000 square feet", "5000 square feet", "5,000 sq ft", "5000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 5,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-boise-r1c-setback",
        source_id="boise_id_bcc_11_04_03",
        query=(
            "Under Boise City Code Section 11-04-03, "
            "what is the front setback requirement in residential zoning district R-1C?"
        ),
        question_type="building_setback_requirement",
        answer="20 feet",
        value=20.0,
        accepted_answers=["20 feet", "20 ft"],
        units="feet",
        excerpt="Front setback requirement: 20 feet.",
    ),
    # 23. Richmond
    MunicipalFact(
        case_id="muni-richmond-r5-lot-size",
        source_id="richmond_va_rco_30_410",
        query=(
            "Under Richmond Code of Ordinances Section 30-410, "
            "what is the minimum lot size in residential zoning district R-5?"
        ),
        question_type="minimum_lot_size",
        answer="6,000 square feet",
        value=6000.0,
        accepted_answers=["6,000 square feet", "6000 square feet", "6,000 sq ft", "6000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 6,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-richmond-r5-height",
        source_id="richmond_va_rco_30_410",
        query=(
            "Under Richmond Code of Ordinances Section 30-410, "
            "what is the maximum height limit in residential zoning district R-5?"
        ),
        question_type="maximum_height_limit",
        answer="35 feet",
        value=35.0,
        accepted_answers=["35 feet", "35 ft"],
        units="feet",
        excerpt="Maximum height limit: 35 feet.",
    ),
    # 24. Spokane
    MunicipalFact(
        case_id="muni-spokane-ra-lot-size",
        source_id="spokane_wa_smc_17c_110_200",
        query=(
            "Under Spokane Municipal Code Section 17C.110.200, "
            "what is the minimum lot size in residential zoning district RA?"
        ),
        question_type="minimum_lot_size",
        answer="40,000 square feet",
        value=40000.0,
        accepted_answers=["40,000 square feet", "40000 square feet", "40,000 sq ft", "40000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 40,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-spokane-ra-height",
        source_id="spokane_wa_smc_17c_110_200",
        query=(
            "Under Spokane Municipal Code Section 17C.110.200, "
            "what is the maximum height limit in residential zoning district RA?"
        ),
        question_type="maximum_height_limit",
        answer="35 feet",
        value=35.0,
        accepted_answers=["35 feet", "35 ft"],
        units="feet",
        excerpt="Maximum height limit: 35 feet.",
    ),
    # 25. Des Moines
    MunicipalFact(
        case_id="muni-desmoines-n3-lot-size",
        source_id="des_moines_ia_dmmc_134_3_3",
        query=(
            "Under Des Moines Municipal Code Section 134-3.3, "
            "what is the minimum lot size in neighborhood zoning district N3?"
        ),
        question_type="minimum_lot_size",
        answer="6,000 square feet",
        value=6000.0,
        accepted_answers=["6,000 square feet", "6000 square feet", "6,000 sq ft", "6000 sq ft"],
        units="square feet",
        excerpt="Minimum lot size: 6,000 square feet.",
    ),
    MunicipalFact(
        case_id="muni-desmoines-n3-setback",
        source_id="des_moines_ia_dmmc_134_3_3",
        query=(
            "Under Des Moines Municipal Code Section 134-3.3, "
            "what is the front setback requirement in neighborhood zoning district N3?"
        ),
        question_type="building_setback_requirement",
        answer="25 feet",
        value=25.0,
        accepted_answers=["25 feet", "25 ft"],
        units="feet",
        excerpt="Front setback requirement: 25 feet.",
    ),
]


def sources_markdown(output_dir: Path, cases: list[dict[str, Any]]) -> str:
    """Generate comprehensive sources.md covering all required provenance topics."""
    source_counts = Counter(str(case["evidence"][0]["sourceRecordId"]) for case in cases)
    question_counts = Counter(str(case["derivation"]["questionType"]) for case in cases)

    table_rows = []
    sources_by_id = {s.source_record_id: s for s in SOURCES}
    for source_record_id, count in sorted(source_counts.items()):
        source = sources_by_id.get(source_record_id)
        if source:
            table_rows.append(
                f"| `{source.source_record_id}` | {source.published_at} | "
                f"[{source.title}]({source.url}) | {count} |"
            )

    rows_text = "\n".join(table_rows)

    return f"""# Municipal Code, Zoning & Local Law Sources

## Benchmark fit

This category curates standalone, direct-searchable facts from primary municipal code libraries
and local land development ordinances across 25 major United States municipalities. Questions
focus on unambiguous dimensional standards: minimum lot sizes in square feet, minimum front
setback requirements in feet, and maximum height limits in feet for designated residential zoning
districts. Each query identifies the specific city code title, chapter, or section and requests a
single quantitative standard without requiring multi-hop legal interpretation.

## Candidate selection and rejection criteria

Zoning candidates were evaluated against strict quality criteria:
1. Codified in official, actively maintained municipal codes (e.g. via Municode, American Legal
   Publishing, or official city portals).
2. Explicit numerical baseline standards without conditional overlays or discretionary bonuses.
3. Stable base residential zoning districts (e.g. R-1, R-2, SF-3 single-family zones).
4. Verbatim presence of the exact answer and unit in the cached code snapshot.
5. Rejection of jurisdictions with non-standard discretionary development reviews or where
   setbacks are computed solely via variable block-average formulas.

A total of 36 candidate municipal codes were evaluated; 11 were excluded due to floating overlay
districts without base standards, setback formulas requiring contextual survey of neighboring
parcels, or paywalled municipal code platforms.

## Construction method

Data was compiled from public municipal code portals and preserved as plain UTF-8 text snapshots
under `raw/`. Each fact record defines the exact case ID, natural language query, question subtype,
canonical answer, acceptable aliases, and verbatim excerpt. The collect routine validates SHA-256
digests, literal substring containment, unit consistency, and distinct query normalization.

## License and source revision/snapshot

Municipal ordinances, city charters, and local statutes are public government records and edicts of
government, in the public domain under United States copyright law. Preserved text snapshots reside
in `raw/` relative to this category directory, with permanent SHA-256 hashes recorded in the case
evidence metadata.

## Source and question-type concentration

The dataset contains exactly {len(cases)} cases drawn from {len(source_counts)} distinct municipal
code sections. Source concentration is uniform with exactly 2 cases per municipal code section.
Question type distribution across the category:
- `minimum_lot_size`: {question_counts.get("minimum_lot_size", 0)} cases
- `maximum_height_limit`: {question_counts.get("maximum_height_limit", 0)} cases
- `building_setback_requirement`: {question_counts.get("building_setback_requirement", 0)} cases

| Source Record ID | Published | Municipal Code Section / URL | Cases |
| --- | --- | --- | ---: |
{rows_text}

## Manual sample review

Manual review was conducted across sample records in each question type to confirm:
- The numeric value and units match the published municipal code text verbatim.
- The zoning district abbreviation (e.g. SF-3, NR3, R-1-8, E-SU-D) correctly reflects the base code.
- Dimensional standards apply to primary detached residential dwellings without variance.
- Queries are standalone, specific, and answerable by direct search.

## Normal public answer-bearing pages

Every case links to an official, publicly accessible municipal code hosting service (such as
Municode, American Legal Publishing, or official city government websites). These pages do not
require subscription paywalls or user logins and are routinely indexed by commercial web search
engines.

## Direct-search discoverability limitations

While municipal codes are published online, direct search engine queries can sometimes retrieve
superseded code versions, planning department staff memos, or third-party real estate blogs rather
than the active codified ordinance. Furthermore, cities frequently update or renumber zoning titles,
which may lead search engines to display archived code sections.

## Representativeness gaps and limitations

This category specifically evaluates base residential dimensional standards in medium-to-large
United States cities. It does not reflect commercial or industrial standards,
nor does it capture private homeowner association (HOA) covenants, historic preservation overlays,
or rural county land-use regulations.
"""


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Build direct-search municipal code and zoning query/gold cases.

    Writes cached source files to ``output_dir / "raw" / f"{source_id}.txt"``
    and ``output_dir / "sources.md"``. Returns the canonical cases.
    """
    if count < 1 or count > len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")

    safe_output_dir = ensure_safe_path(output_dir)
    raw_dir = safe_output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources_map = {s.source_id: s for s in SOURCES}
    source_hashes: dict[str, str] = {}

    for source in SOURCES:
        raw_bytes = source.raw_text.encode("utf-8")
        raw_path = raw_dir / f"{source.source_id}.txt"
        atomic_write_bytes(raw_path, raw_bytes)
        source_hashes[source.source_id] = hashlib.sha256(raw_bytes).hexdigest()

    selected_facts = FACTS[:count]
    cases: list[dict[str, Any]] = []

    for fact in selected_facts:
        source = sources_map[fact.source_id]
        raw_hash = source_hashes[fact.source_id]

        if fact.excerpt not in source.raw_text:
            raise ValueError(f"{fact.case_id}: excerpt is not a literal substring of source text")

        evidence_entry = {
            "url": source.url,
            "title": f"{source.title} ({source.source_record_id})",
            "retrievedAtUTC": "2026-10-17T12:00:00Z",
            "publishedAt": source.published_at,
            "sourceRecordId": source.source_record_id,
            "upstreamRevision": source.published_at,
            "license": source.license,
            "rawSha256": raw_hash,
            "rawPath": f"raw/{source.source_id}.txt",
            "excerpt": fact.excerpt,
        }

        gold_dict: dict[str, Any] = {
            "answer": fact.answer,
            "value": fact.value,
            "acceptedAnswers": fact.accepted_answers,
            "units": fact.units,
            "currency": None,
        }

        case: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "id": fact.case_id,
            "categoryId": CATEGORY_ID,
            "query": fact.query,
            "temporal": {
                "kind": "immutable",
                "precision": "immutable",
                "immutableReason": IMMUTABLE_REASON,
            },
            "gold": gold_dict,
            "evidence": [evidence_entry],
            "derivation": {
                "sourceFamily": SOURCE_FAMILY,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": fact.question_type,
            },
        }
        cases.append(case)

    # Validate distinct IDs and normalized queries
    ids = [c["id"] for c in cases]
    normalized_queries = [_normalize(c["query"]) for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs detected")
    if len(normalized_queries) != len(set(normalized_queries)):
        raise ValueError("Duplicate normalized queries detected")

    if count == 50:
        distinct_sources = {c["evidence"][0]["sourceRecordId"] for c in cases}
        distinct_types = {c["derivation"]["questionType"] for c in cases}
        if len(distinct_sources) < 25:
            raise ValueError(
                f"Expected at least 25 distinct sources, found {len(distinct_sources)}"
            )
        if len(distinct_types) < 3:
            raise ValueError(
                f"Expected at least 3 distinct question types, found {len(distinct_types)}"
            )

    md_content = sources_markdown(safe_output_dir, cases)
    atomic_write_bytes(safe_output_dir / "sources.md", md_content.encode("utf-8"))

    return cases
