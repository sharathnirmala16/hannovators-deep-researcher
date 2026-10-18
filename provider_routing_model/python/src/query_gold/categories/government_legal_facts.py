from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FederalFactSpec:
    """One source field and one independently answerable Federal Register query."""

    id: str
    document_number: str
    question_type: str
    mode: str
    prompt: str
    expected: str | None = None
    answer: str | None = None
    support: str | None = None
    value: Any = None
    units: str | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class LawSource:
    """A fixed, enacted public-law package and its normal answer-bearing page."""

    key: str
    public_law_id: str
    short_title: str
    enacted_date: str
    url: str
    raw_path: str

    def version(self, section: str) -> str:
        return f"Pub. L. {self.public_law_id} (enacted {self.enacted_date}), § {section}"


@dataclass(frozen=True, slots=True)
class StatuteFactSpec:
    """A one-section, one-field question whose answer is stated in the law text."""

    id: str
    law_key: str
    section: str
    question_type: str
    prompt: str
    answer: str
    support: str
    value: Any = None
    units: str | None = None
    currency: str | None = None


LAWS: dict[str, LawSource] = {
    "ira": LawSource(
        key="ira",
        public_law_id="117-169",
        short_title="Inflation Reduction Act of 2022",
        enacted_date="2022-08-16",
        url="https://www.govinfo.gov/content/pkg/PLAW-117publ169/html/PLAW-117publ169.htm",
        raw_path="raw/plaw-117publ169.html",
    ),
    "faa": LawSource(
        key="faa",
        public_law_id="118-63",
        short_title="FAA Reauthorization Act of 2024",
        enacted_date="2024-05-16",
        url="https://www.govinfo.gov/content/pkg/PLAW-118publ63/html/PLAW-118publ63.htm",
        raw_path="raw/plaw-118publ63.html",
    ),
}


def _fr_spec(
    case_id: str,
    document_number: str,
    question_type: str,
    mode: str,
    prompt: str,
    *,
    expected: str | None = None,
    answer: str | None = None,
    support: str | None = None,
    value: Any = None,
    units: str | None = None,
    currency: str | None = None,
) -> FederalFactSpec:
    return FederalFactSpec(
        case_id,
        document_number,
        question_type,
        mode,
        prompt,
        expected,
        answer,
        support,
        value,
        units,
        currency,
    )


def _statute_spec(
    case_id: str,
    section: str,
    question_type: str,
    prompt: str,
    answer: str,
    support: str,
    *,
    law_key: str = "ira",
    value: Any = None,
    units: str | None = None,
    currency: str | None = None,
) -> StatuteFactSpec:
    return StatuteFactSpec(
        case_id, law_key, section, question_type, prompt, answer, support, value, units, currency
    )


FEDERAL_FACTS: tuple[FederalFactSpec, ...] = (
    _fr_spec(
        "legal-fr-2023-27783-access-fee",
        "2023-27783",
        "rule_access_fee_change",
        "abstract",
        (
            "what fee did the FMC's 2024 Carrier Automated Tariffs rule remove carriers' "
            "option to charge?"
        ),
        answer="a fee to access their tariff",
        support="a fee to access their tariff",
    ),
    _fr_spec(
        "legal-fr-2024-06566-effective-date",
        "2024-06566",
        "rule_effective_date",
        "effective_date",
        "what effective date does CMS list for its 2024 Medicaid/CHIP eligibility rule?",
    ),
    _fr_spec(
        "legal-fr-2024-06572-walkaround-representative",
        "2024-06572",
        "rule_representative_eligibility",
        "abstract",
        (
            "under OSHA's 2024 walkaround final rule, besides an employee of the employer, "
            "whom may employees designate as their representative for workplace inspections?"
        ),
        answer="a third party",
        support="a third party",
    ),
    _fr_spec(
        "legal-fr-2024-06929-eoir-docket",
        "2024-06929",
        "rule_docket_identifier",
        "docket",
        "what EOIR docket number does DOJ list for its 2024 Board of Immigration Appeals rule?",
        expected="EOIR Docket No. EOIR 20-0010",
    ),
    _fr_spec(
        "legal-fr-2024-07105-medicare-docket",
        "2024-07105",
        "rule_docket_identifier",
        "docket",
        "what docket identifiers does CMS list for its 2024 Medicare Advantage/Part D rule?",
        expected="CMS-4201-F3 and CMS-4205-F",
    ),
    _fr_spec(
        "legal-fr-2024-07180-telemarketing-part",
        "2024-07180",
        "rule_cfr_part",
        "cfr_part",
        "which title 16 CFR part does the FTC's 2024 Telemarketing Sales Rule reference?",
        expected="16:310",
    ),
    _fr_spec(
        "legal-fr-2024-07773-pfoa-mcl",
        "2024-07773",
        "rule_contaminant_limit",
        "abstract",
        "what PFOA maximum contaminant level did EPA's 2024 PFAS water rule set?",
        answer="4.0 nanograms per liter (ng/L)",
        support="PFOA and PFOS at 4.0 nanograms per liter (ng/L)",
        value=4.0,
        units="ng/L",
    ),
    _fr_spec(
        "legal-fr-2024-08038-overtime-effective-date",
        "2024-08038",
        "rule_effective_date",
        "effective_date",
        "what effective date does DOL list for its 2024 overtime-exemption final rule?",
    ),
    _fr_spec(
        "legal-fr-2024-08792-ceq-docket",
        "2024-08792",
        "rule_docket_identifier",
        "docket",
        "what docket number does CEQ list for its 2024 NEPA implementing-rule?",
        expected="CEQ-2023-0003",
    ),
    _fr_spec(
        "legal-fr-2024-09520-sba-rin",
        "2024-09520",
        "rule_regulation_identifier",
        "rin",
        "what RIN does SBA list for its 2024 Microloan Program direct final rule?",
        expected="3245-AH83",
    ),
    _fr_spec(
        "legal-fr-2024-10844-regcc-effective-date",
        "2024-10844",
        "rule_effective_date",
        "effective_date",
        "what effective date does the Federal Reserve list for its 2024 Regulation CC rule?",
    ),
    _fr_spec(
        "legal-fr-2024-11800-bnpl-applicability-date",
        "2024-11800",
        "interpretive_rule_applicability_date",
        "applicability_date",
        "from what date does CFPB say its 2024 BNPL digital-account interpretive rule applies?",
    ),
    _fr_spec(
        "legal-fr-2024-18087-zuranolone-schedule",
        "2024-18087",
        "controlled_substance_schedule",
        "abstract",
        (
            "which Controlled Substances Act schedule did DEA maintain for zuranolone in its "
            "2024 final rule?"
        ),
        answer="schedule IV",
        support="in schedule IV of the Controlled Substances Act",
    ),
    _fr_spec(
        "legal-fr-2024-18591-hearing-manners",
        "2024-18591",
        "hearing_appearance_modes",
        "abstract",
        "which standard claimant-hearing appearance modes does SSA's 2024 rule identify?",
        answer="by agency video, by online video, by audio, or in person",
        support="by agency video, by online video, by audio, or in person",
    ),
    _fr_spec(
        "legal-fr-2024-19431-dnc-registry",
        "2024-19431",
        "telemarketing_registry",
        "abstract",
        "which registry's access fees did FTC update in its 2024 telemarketing rule?",
        answer="the National Do Not Call Registry",
        support="the National Do Not Call Registry",
    ),
    _fr_spec(
        "legal-fr-2024-23211-cpsc-astm-reference",
        "2024-23211",
        "product_standard_reference",
        "abstract",
        (
            "which revised ASTM specification did CPSC reference in its 2024 infant bath seat "
            "direct final rule?"
        ),
        answer="ASTM F1967-24",
        support="ASTM F1967-24",
    ),
    _fr_spec(
        "legal-fr-2024-24433-fdic-compliance-date",
        "2024-24433",
        "rule_compliance_date",
        "compliance_date",
        "to what date did the FDIC delay compliance for amendments to 12 CFR part 328 in 2024?",
        expected="2025-05-01",
    ),
    _fr_spec(
        "legal-fr-2024-26698-ed-effective-date",
        "2024-26698",
        "interim_rule_effective_date",
        "effective_date",
        (
            "what effective date did Education list in its 2024 income-driven-repayment "
            "interim final rule?"
        ),
    ),
    _fr_spec(
        "legal-fr-2024-30242-gsa-fpmr-case",
        "2024-30242",
        "rule_docket_identifier",
        "docket",
        "what FPMR Case number does GSA list for its 2024 civil-penalties adjustment rule?",
        expected="FPMR Case 2025-01",
    ),
    _fr_spec(
        "legal-fr-2024-30793-fhfa-rin",
        "2024-30793",
        "rule_regulation_identifier",
        "rin",
        (
            "what RIN does FHFA list for its 2025-2027 Enterprise Housing Goals rule "
            "published in 2024?"
        ),
        expected="2590-AB34",
    ),
)
STATUTE_FACTS: tuple[StatuteFactSpec, ...] = (
    _statute_spec(
        "legal-pl117-169-s13401-critical-mineral-credit",
        "13401",
        "statutory_vehicle_credit_amount",
        "what per-vehicle amount does 26 U.S.C. § 30D(b)(2) assign to critical minerals?",
        "$3,750",
        "$3,750",
        value=3750,
        units="USD per vehicle",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13401-final-assembly-region",
        "13401",
        "statutory_geographic_requirement",
        "what region must final assembly of a new clean vehicle occur in under § 30D(d)(1)(G)?",
        "North America",
        "North America",
    ),
    _statute_spec(
        "legal-pl117-169-s13402-joint-income-threshold",
        "13402",
        "statutory_income_threshold",
        "what MAGI threshold applies to a joint return or surviving spouse under 26 U.S.C. § 25E?",
        "$150,000",
        "$150,000",
        value=150000,
        units="USD per taxable year",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13402-model-year-gap",
        "13402",
        "statutory_vehicle_age_threshold",
        (
            "how many years earlier must a previously-owned vehicle's model year be under "
            "§ 25E(c)(1)(A)?"
        ),
        "At least 2 years earlier",
        "at least 2 years",
        value=2,
        units="years",
    ),
    _statute_spec(
        "legal-pl117-169-s13402-credit-cap",
        "13402",
        "statutory_credit_cap",
        "what credit ceiling does 26 U.S.C. § 25E(a)(1) set?",
        "$4,000",
        "$4,000",
        value=4000,
        units="USD per vehicle",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13301-annual-cap",
        "13301",
        "statutory_annual_credit_cap",
        (
            "what annual limit does amended 26 U.S.C. § 25C(b)(1) set for the nonbusiness "
            "energy property credit?"
        ),
        "$1,200",
        "$1,200",
        value=1200,
        units="USD per taxpayer per taxable year",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13301-heat-pump-limit",
        "13301",
        "statutory_heat_pump_credit_limit",
        "what annual credit ceiling applies to heat-pump property under amended § 25C(b)(5)?",
        "$2,000",
        "$2,000",
        value=2000,
        units="USD per taxpayer per taxable year",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13302-credit-rate",
        "13302",
        "statutory_residential_credit_rate",
        (
            "for residential clean-energy property placed in service after 2021-12-31 and "
            "before 2033-01-01, what rate applies under § 25D(g)(3)?"
        ),
        "30 percent",
        "30 percent",
        value=30,
        units="percent",
    ),
    _statute_spec(
        "legal-pl117-169-s13302-battery-capacity",
        "13302",
        "statutory_battery_capacity_threshold",
        "what minimum capacity must qualified battery storage technology have under § 25D(d)(6)?",
        "Not less than 3 kilowatt hours",
        "capacity of not less than 3 kilowatt",
        value=3,
        units="kilowatt hours",
    ),
    _statute_spec(
        "legal-pl117-169-s13303-energy-savings-threshold",
        "13303",
        "statutory_energy_savings_threshold",
        (
            "what percentage reduction in annual energy costs must a building exceed under "
            "§ 179D(b)(2)?"
        ),
        "Greater than 25 percent",
        "greater than 25 percent",
        value=25,
        units="percent",
    ),
    _statute_spec(
        "legal-pl117-169-s13403-commercial-credit-rate",
        "13403",
        "statutory_commercial_vehicle_credit_rate",
        (
            "what basis percentage does § 45W(b)(1)(A) use for a commercial clean vehicle "
            "without a gasoline or diesel engine?"
        ),
        "30 percent",
        "percent in the case of a vehicle not powered by a",
        value=30,
        units="percent",
    ),
    _statute_spec(
        "legal-pl117-169-s13403-low-weight-cap",
        "13403",
        "statutory_commercial_vehicle_credit_cap",
        "what per-vehicle cap applies under § 45W(b)(4)(A) below 14,000 pounds GVWR?",
        "$7,500",
        "$7,500",
        value=7500,
        units="USD per vehicle",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13404-item-cap",
        "13404",
        "statutory_refueling_property_cap",
        "what per-item credit cap does amended § 30C(b)(1) set for qualified refueling property?",
        "$100,000",
        "$100,000",
        value=100000,
        units="USD per item",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13404-fuel-volume",
        "13404",
        "statutory_fuel_composition_threshold",
        (
            "what minimum fuel-volume share applies to the specified alternative fuels under "
            "amended 26 U.S.C. § 30C(c)(1)(B)(i)?"
        ),
        "At least 85 percent",
        "at least 85 percent of the volume",
        value=85,
        units="percent of volume",
    ),
    _statute_spec(
        "legal-pl117-169-s13501-total-credit-cap",
        "13501",
        "statutory_project_credit_allocation_cap",
        (
            "what total allocation limit does § 48C(e)(2) set for the additional advanced-energy "
            "project program?"
        ),
        "$10,000,000,000",
        "$10,000,000,000",
        value=10000000000,
        units="USD total program allocation",
        currency="USD",
    ),
    _statute_spec(
        "legal-pl117-169-s13701-base-production-rate",
        "13701",
        "statutory_clean_electricity_production_rate",
        (
            "what base amount does § 45Y(b)(2)(A) set per kilowatt-hour for the clean electricity "
            "production credit?"
        ),
        "0.3 cents",
        "applicable amount shall be 0.3 cents",
        value=0.3,
        units="cents per kilowatt hour",
    ),
    _statute_spec(
        "legal-pl118-63-s411-working-group-deadline",
        "411",
        "statutory_working_group_establishment_deadline",
        "within how many days must the FAA Administrator establish the aeromedical working group?",
        "Not later than 180 days",
        "Not later than 180 days after the date of enactment",
        law_key="faa",
        value=180,
        units="days",
    ),
    _statute_spec(
        "legal-pl118-63-s411-working-group-size",
        "411",
        "statutory_working_group_minimum_members",
        "what minimum number of non-chair appointees must the aeromedical working group include?",
        "Not less than 15 individuals",
        "not less than 15",
        law_key="faa",
        value=15,
        units="individuals",
    ),
    _statute_spec(
        "legal-pl118-63-s413-task-group-deadline",
        "413",
        "statutory_task_group_establishment_deadline",
        (
            "within how many days must the co-chairs establish the medical portal task group "
            "after the working group?"
        ),
        "Not later than 120 days",
        "Not later than 120 days after the working group pursuant to section 411 is established",
        law_key="faa",
        value=120,
        units="days",
    ),
    _statute_spec(
        "legal-pl118-63-s420-regulation-deadline",
        "420",
        "statutory_regulation_issuance_deadline",
        (
            "what deadline after enactment applies to FAA regulations implementing the "
            "remote-dispatching prohibition under § 420(a)(2)?"
        ),
        "Not later than 1 year",
        "Not later than 1 year after the date of enactment",
        law_key="faa",
        value=1,
        units="years",
    ),
)


@dataclass(frozen=True, slots=True)
class CourtFactSpec:
    """A case-specific field from an official Washington Supreme Court page."""

    id: str
    filename: str
    docket: str
    case_title: str
    filed_date: str
    majority_author: str


COURT_FACTS: tuple[CourtFactSpec, ...] = (
    CourtFactSpec(
        "legal-wa-sc-2024-102402-majority",
        "1024029MAJ",
        "102,402-9",
        "State v. Smith",
        "2024-09-12",
        "Debra L. Stephens",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-102311-majority",
        "1023111MAJ",
        "102,311-1",
        "State v. Harris",
        "2024-11-27",
        "Barbara A. Madsen",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-101828-majority",
        "1018282MAJ",
        "101,828-2",
        "State v. Luthi",
        "2024-06-13",
        "Mary I. Yu",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-101703-majority",
        "1017031MAJ",
        "101,703-1",
        "State v. Buck",
        "2024-03-14",
        "G. Helen Whitener",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-101045-majority",
        "1010451MAJ",
        "101,045-1",
        "Barlow v. State",
        "2024-01-04",
        "Charles W. Johnson",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-101894-majority",
        "1018941MAJ",
        "101,894-1",
        "City of Sammamish v. Titcomb",
        "2024-09-12",
        "Charles W. Johnson",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-102355-majority",
        "1023553MAJ",
        "102,355-3",
        "In re Marriage of Porter",
        "2024-08-29",
        "G. Helen Whitener",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-102486-majority",
        "1024860MAJ",
        "102,486-0",
        "In re Dependency of M.L.W.",
        "2024-11-14",
        "Sheryl Gordon McCloud",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-101799-majority",
        "1017995MAJ",
        "101,799-5",
        "M.G. v. Yakima Sch. Dist. No. 7",
        "2024-03-07",
        "Barbara A. Madsen",
    ),
    CourtFactSpec(
        "legal-wa-sc-2024-102627-majority",
        "1026277MAJ",
        "102,627-7",
        "State v. Richards",
        "2024-11-21",
        "Charles W. Johnson",
    ),
)
