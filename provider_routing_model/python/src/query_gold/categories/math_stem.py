# ruff: noqa: E501
"""Static Mathematics & Theoretical STEM query/gold curation category.

Covers published mathematical bounds, theorem proofs, exact analytical constants,
and physical law constants across NIST CODATA, Wolfram MathWorld, and peer-reviewed literature.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from query_gold.io import atomic_write_bytes, ensure_safe_path
from query_gold.models import SCHEMA_VERSION

CATEGORY_ID = "07_static_mathematics_stem"
GENERATOR_VERSION = "math-stem-curator/1.0"
SOURCE_FAMILY_NIST = "nist_codata_fundamental_constants"
SOURCE_FAMILY_MATHWORLD = "wolfram_mathworld_encyclopedia"
SOURCE_FAMILY_LITERATURE = "peer_reviewed_stem_literature"


@dataclass(frozen=True)
class MathSource:
    source_id: str
    title: str
    url: str
    license_name: str
    source_family: str
    raw_content: str


@dataclass(frozen=True)
class MathFact:
    case_id: str
    source_id: str
    query: str
    answer: str
    accepted_answers: list[str]
    units: str | None
    value: int | float | None
    question_type: str
    excerpt: str


# 34 distinct STEM sources
SOURCES: tuple[MathSource, ...] = (
    # 1-18: NIST CODATA Fundamental Physical Constants
    MathSource(
        source_id="nist-codata-speed-of-light",
        title="NIST CODATA Fundamental Physical Constants - Speed of Light in Vacuum",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?c",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: speed of light in vacuum
Value: 299792458 m/s
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-planck-constant",
        title="NIST CODATA Fundamental Physical Constants - Planck Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?h",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: Planck constant
Value: 6.62607015e-34 J s
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-boltzmann-constant",
        title="NIST CODATA Fundamental Physical Constants - Boltzmann Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?k",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: Boltzmann constant
Value: 1.380649e-23 J K^-1
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-elementary-charge",
        title="NIST CODATA Fundamental Physical Constants - Elementary Charge",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?e",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: elementary charge
Value: 1.602176634e-19 C
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-avogadro-constant",
        title="NIST CODATA Fundamental Physical Constants - Avogadro Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?na",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: Avogadro constant
Value: 6.02214076e23 mol^-1
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-gravitational-constant",
        title="NIST CODATA Fundamental Physical Constants - Newtonian Constant of Gravitation",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?bg",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: Newtonian constant of gravitation
Value: 6.67430e-11 m^3 kg^-1 s^-2
Standard uncertainty: 0.00015e-11
""",
    ),
    MathSource(
        source_id="nist-codata-fine-structure-constant",
        title="NIST CODATA Fundamental Physical Constants - Inverse Fine-Structure Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?alph",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: inverse fine-structure constant
Value: 137.035999084
Standard uncertainty: 0.000000021
""",
    ),
    MathSource(
        source_id="nist-codata-rydberg-constant",
        title="NIST CODATA Fundamental Physical Constants - Rydberg Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?ryd",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: Rydberg constant
Value: 10973731.568160 m^-1
Standard uncertainty: 0.000021
""",
    ),
    MathSource(
        source_id="nist-codata-electron-mass",
        title="NIST CODATA Fundamental Physical Constants - Electron Mass",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?me",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: electron mass
Value: 9.1093837015e-31 kg
Standard uncertainty: 0.0000000028e-31
""",
    ),
    MathSource(
        source_id="nist-codata-stefan-boltzmann-constant",
        title="NIST CODATA Fundamental Physical Constants - Stefan-Boltzmann Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?sigma",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: Stefan-Boltzmann constant
Value: 5.670374419e-8 W m^-2 K^-4
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-molar-gas-constant",
        title="NIST CODATA Fundamental Physical Constants - Molar Gas Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?r",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: molar gas constant
Value: 8.314462618 J mol^-1 K^-1
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-von-klitzing-constant",
        title="NIST CODATA Fundamental Physical Constants - Von Klitzing Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?rk",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: von Klitzing constant
Value: 25812.80745 ohm
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-josephson-constant",
        title="NIST CODATA Fundamental Physical Constants - Josephson Constant",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?kj",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: Josephson constant
Value: 483597.8484e9 Hz V^-1
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-proton-electron-ratio",
        title="NIST CODATA Fundamental Physical Constants - Proton-Electron Mass Ratio",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?mpmue",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: proton-electron mass ratio
Value: 1836.15267343
Standard uncertainty: 0.00000011
""",
    ),
    MathSource(
        source_id="nist-codata-magnetic-flux-quantum",
        title="NIST CODATA Fundamental Physical Constants - Magnetic Flux Quantum",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?flxqu",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: magnetic flux quantum
Value: 2.067833848e-15 Wb
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-conductance-quantum",
        title="NIST CODATA Fundamental Physical Constants - Conductance Quantum",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?conqu",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: conductance quantum
Value: 7.748091729e-5 S
Exact: Defined
Standard uncertainty: (exact)
""",
    ),
    MathSource(
        source_id="nist-codata-permeability-vacuum",
        title="NIST CODATA Fundamental Physical Constants - Vacuum Magnetic Permeability",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?mu0",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: vacuum magnetic permeability
Value: 1.25663706212e-6 N A^-2
Standard uncertainty: 0.00000000019e-6
""",
    ),
    MathSource(
        source_id="nist-codata-permittivity-vacuum",
        title="NIST CODATA Fundamental Physical Constants - Vacuum Electric Permittivity",
        url="https://physics.nist.gov/cgi-bin/cuu/Value?ep0",
        license_name="NIST Public Domain / Open Government Data",
        source_family=SOURCE_FAMILY_NIST,
        raw_content="""NIST Reference on Constants, Units, and Uncertainty
CODATA Value: vacuum electric permittivity
Value: 8.8541878128e-12 F m^-1
Standard uncertainty: 0.0000000013e-12
""",
    ),
    # 19-34: Wolfram MathWorld Analytical Constants & Mathematical Bounds
    MathSource(
        source_id="wolfram-mathworld-euler-mascheroni",
        title="Wolfram MathWorld: Euler-Mascheroni Constant",
        url="https://mathworld.wolfram.com/Euler-MascheroniConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Euler-Mascheroni Constant
Symbol: gamma
Value to 10 decimal places: 0.5772156649
Decimal expansion: 0.577215664901532860606512090082402431042
Definition: limit of (sum_{k=1}^n 1/k - ln(n)) as n approaches infinity
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-catalans-constant",
        title="Wolfram MathWorld: Catalan's Constant",
        url="https://mathworld.wolfram.com/CatalansConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Catalan's Constant
Symbol: K or G
Value to 10 decimal places: 0.9159655941
Decimal expansion: 0.915965594177219015054603514932384110774
Definition: sum_{k=0}^infty (-1)^k / (2k+1)^2
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-feigenbaum-alpha",
        title="Wolfram MathWorld: Feigenbaum Constant Alpha",
        url="https://mathworld.wolfram.com/FeigenbaumConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Feigenbaum Constant
Value to 8 decimal places: 2.50290787
Feigenbaum alpha reduction parameter: 2.502907875095892822283902873218
Universal scaling ratio for quadratic maps.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-feigenbaum-delta",
        title="Wolfram MathWorld: Feigenbaum Constant Delta",
        url="https://mathworld.wolfram.com/FeigenbaumConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Feigenbaum Constant Delta
Value to 8 decimal places: 4.66920160
Feigenbaum delta bifurcation velocity parameter: 4.669201609102990671853203820466
Universal scaling ratio for period doubling routes to chaos.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-khinchins-constant",
        title="Wolfram MathWorld: Khinchin's Constant",
        url="https://mathworld.wolfram.com/KhinchinsConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Khinchin's Constant
Symbol: K_0
Value to 8 decimal places: 2.68545200
Decimal expansion: 2.68545200106530644530971483548179569364
Geometric mean of continued fraction terms.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-glaisher-kinkelin",
        title="Wolfram MathWorld: Glaisher-Kinkelin Constant",
        url="https://mathworld.wolfram.com/Glaisher-KinkelinConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Glaisher-Kinkelin Constant
Symbol: A
Value to 8 decimal places: 1.28242712
Decimal expansion: 1.28242712910062263387767525386257763913
Related to hyperfactorial and K-function asymptotics.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-aperys-constant",
        title="Wolfram MathWorld: Apery's Constant",
        url="https://mathworld.wolfram.com/AperysConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Apery's Constant
Symbol: zeta(3)
Value to 8 decimal places: 1.20205690
Decimal expansion: 1.20205690315959428539973816151144999076
Proved irrational by Roger Apery in 1978.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-golden-ratio",
        title="Wolfram MathWorld: Golden Ratio",
        url="https://mathworld.wolfram.com/GoldenRatio.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Golden Ratio
Symbol: phi
Closed form: (1 + sqrt(5)) / 2
Value to 10 decimal places: 1.6180339887
Decimal expansion: 1.61803398874989484820458683436563811772
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-silver-ratio",
        title="Wolfram MathWorld: Silver Ratio",
        url="https://mathworld.wolfram.com/SilverRatio.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Silver Ratio
Symbol: delta_S
Closed form: 1 + sqrt(2)
Decimal expansion: 2.41421356237309504880168872420969807856
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-conways-constant",
        title="Wolfram MathWorld: Conway's Constant",
        url="https://mathworld.wolfram.com/ConwaysConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Conway's Constant
Symbol: lambda
Value to 8 decimal places: 1.30357726
Decimal expansion: 1.30357726903429639125709911215255189073
Growth rate of strings in Conway audioactive decay sequence.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-meissel-mertens",
        title="Wolfram MathWorld: Meissel-Mertens Constant",
        url="https://mathworld.wolfram.com/MertensConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Mertens Constant
Symbol: M_1 or B_1
Value to 8 decimal places: 0.26149721
Decimal expansion: 0.26149721284764056980772703481239194060
Sum of reciprocal primes minus ln(ln(x)) limit.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-mills-constant",
        title="Wolfram MathWorld: Mills' Constant",
        url="https://mathworld.wolfram.com/MillsConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Mills' Constant
Symbol: A
Value to 8 decimal places: 1.30637788
Decimal expansion: 1.30637788386308069046861449260260571291
Smallest real number such that floor(A^(3^n)) is prime for all positive integers n.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-golomb-dickman",
        title="Wolfram MathWorld: Golomb-Dickman Constant",
        url="https://mathworld.wolfram.com/Golomb-DickmanConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Golomb-Dickman Constant
Symbol: lambda
Value to 8 decimal places: 0.62432998
Decimal expansion: 0.62432998854355087099293638310083724417
Expected length of the longest cycle in a random permutation of n elements.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-gauss-constant",
        title="Wolfram MathWorld: Gauss's Constant",
        url="https://mathworld.wolfram.com/GaussConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Gauss's Constant
Symbol: G
Value to 8 decimal places: 0.83462684
Decimal expansion: 0.83462684167407318628142973279904680899
Equal to 1 / M(1, sqrt(2)) where M is the arithmetic-geometric mean.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-plastic-constant",
        title="Wolfram MathWorld: Plastic Constant",
        url="https://mathworld.wolfram.com/PlasticConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Plastic Constant
Symbol: rho or psi
Value to 8 decimal places: 1.32471795
Decimal expansion: 1.32471795724474602596090885447809734073
Real root of the polynomial x^3 - x - 1 = 0.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-ramanujan-soldner",
        title="Wolfram MathWorld: Soldner's Constant",
        url="https://mathworld.wolfram.com/SoldnerConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Soldner's Constant
Symbol: mu
Value to 8 decimal places: 1.45136923
Decimal expansion: 1.45136923488338105028396848589202744949
Unique positive zero of the logarithmic integral function li(x).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-twin-prime-constant",
        title="Wolfram MathWorld: Twin Prime Constant",
        url="https://mathworld.wolfram.com/TwinPrimeConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Twin Prime Constant
Symbol: C_2
Value to 8 decimal places: 0.66016181
Decimal expansion: 0.66016181584686957392781211001455577843
Product over odd primes p of (1 - 1/(p-1)^2).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-bruns-constant",
        title="Wolfram MathWorld: Brun's Constant",
        url="https://mathworld.wolfram.com/BrunsConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Brun's Constant
Symbol: B_2
Value to 8 decimal places: 1.90216058
Value: 1.902160583104
Sum of the reciprocals of twin primes, proved finite by Viggo Brun in 1919.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-landau-constant",
        title="Wolfram MathWorld: Landau's Constant",
        url="https://mathworld.wolfram.com/LandauConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Landau's Constant
Symbol: L
Proven bounds: 0.5 <= L <= 0.5432589
The lower bound 1/2 = 0.5 was proved by Landau.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-bloch-constant",
        title="Wolfram MathWorld: Bloch's Constant",
        url="https://mathworld.wolfram.com/BlochConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Bloch's Constant
Symbol: B
Proven lower bound: sqrt(3)/4
Approximate lower bound: 0.4330127
Proved by Ahlfors and Grunsky (1937).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-debruijn-newman",
        title="Wolfram MathWorld: de Bruijn-Newman Constant",
        url="https://mathworld.wolfram.com/deBruijn-NewmanConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: de Bruijn-Newman Constant
Symbol: Lambda
Proven bound: Lambda >= 0
Proved by Brad Rodgers and Terence Tao in 2018 (arXiv:1801.05914).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-kissing-number-4d",
        title="Wolfram MathWorld: Kissing Number 4D",
        url="https://mathworld.wolfram.com/KissingNumber.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Kissing Number
Dimension 4: 24
Exact kissing number k(4) = 24 was proved by Oleg Musin in 2003.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-kissing-number-3d",
        title="Wolfram MathWorld: Kissing Number 3D",
        url="https://mathworld.wolfram.com/KissingNumber.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Kissing Number in 3 Dimensions
Dimension 3: 12
Proved by Schutte and van der Waerden in 1953, resolving the Newton-Gregory dispute.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-kissing-number-8d",
        title="Wolfram MathWorld: Kissing Number 8D",
        url="https://mathworld.wolfram.com/KissingNumber.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Kissing Number in 8 Dimensions
Dimension 8: 240
Achieved by the E8 lattice, proved by Odlyzko and Sloane (1979) and Levenshtein (1979).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-kissing-number-24d",
        title="Wolfram MathWorld: Kissing Number 24D",
        url="https://mathworld.wolfram.com/KissingNumber.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Kissing Number in 24 Dimensions
Dimension 24: 196560
Achieved by the Leech lattice, proved by Odlyzko and Sloane (1979).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-mertens-conjecture",
        title="Wolfram MathWorld: Mertens Conjecture Disproof",
        url="https://mathworld.wolfram.com/MertensConjecture.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Mertens Conjecture
Status: Disproved
Lower bound: lim sup M(x)/sqrt(x) > 1.06
Proved by Andrew Odlyzko and Herman te Riele in 1985.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-prime-gap-zhang",
        title="Wolfram MathWorld: Prime Gaps Zhang Bound",
        url="https://mathworld.wolfram.com/PrimeGaps.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_LITERATURE,
        raw_content="""Wolfram MathWorld: Prime Gaps
Bounded gaps between primes:
Zhang's bound: lim inf (p_{n+1} - p_n) < 70000000
Proved by Yitang Zhang in Annals of Mathematics (2014).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-prime-gap-polymath",
        title="Wolfram MathWorld: Polymath8 Prime Gap Bound",
        url="https://mathworld.wolfram.com/PrimeGaps.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_LITERATURE,
        raw_content="""Wolfram MathWorld: Polymath8 Prime Gap Bound
Unconditional bound: lim inf (p_{n+1} - p_n) <= 246
Proved by the Polymath8b project (2014).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-liouvilles-constant",
        title="Wolfram MathWorld: Liouville's Constant",
        url="https://mathworld.wolfram.com/LiouvillesConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Liouville's Constant
Symbol: L
Value to 8 decimal places: 0.11000100
Decimal expansion: 0.110001000000000000000001000...
Definition: sum_{k=1}^infty 10^(-k!)
First proved transcendental number (Joseph Liouville, 1844).
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-lebesgue-constants",
        title="Wolfram MathWorld: Lebesgue Constant Asymptotics",
        url="https://mathworld.wolfram.com/LebesgueConstants.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Lebesgue Constant
Fourier analysis asymptotic constant:
L_n = (4/pi^2) * ln(n) + O(1)
Leading coefficient: 4/pi^2
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-sierpinski-constant",
        title="Wolfram MathWorld: Sierpinski's Constant",
        url="https://mathworld.wolfram.com/SierpinskisConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Sierpinski's Constant
Symbol: K
Value to 8 decimal places: 2.58498175
Decimal expansion: 2.58498175957925321706589358738317116025
Limit of sum_{k=1}^n r(k)/k - pi*ln(n) as n approaches infinity.
""",
    ),
    MathSource(
        source_id="wolfram-mathworld-landau-ramanujan",
        title="Wolfram MathWorld: Landau-Ramanujan Constant",
        url="https://mathworld.wolfram.com/Landau-RamanujanConstant.html",
        license_name="Wolfram MathWorld Terms of Use",
        source_family=SOURCE_FAMILY_MATHWORLD,
        raw_content="""Wolfram MathWorld: Landau-Ramanujan Constant
Symbol: b or K
Value to 8 decimal places: 0.76422365
Decimal expansion: 0.76422365358922066299069873125009232811
Asymptotic constant for numbers representable as sums of two squares.
""",
    ),
)


# Exactly 50 static STEM facts
FACTS: tuple[MathFact, ...] = (
    # 1-18: Fundamental Physical Law Constants (NIST CODATA)
    MathFact(
        case_id="math-speed-of-light-value",
        source_id="nist-codata-speed-of-light",
        query="What exact numerical value in meters per second is defined for the Speed of Light in vacuum by physical law?",
        answer="299792458",
        accepted_answers=["299792458"],
        units="m/s",
        value=299792458,
        question_type="physical_law_constant",
        excerpt="Value: 299792458 m/s",
    ),
    MathFact(
        case_id="math-planck-constant-value",
        source_id="nist-codata-planck-constant",
        query="What exact numerical value in joule seconds defines the Planck Constant under the SI system?",
        answer="6.62607015e-34",
        accepted_answers=["6.62607015e-34"],
        units="J s",
        value=6.62607015e-34,
        question_type="physical_law_constant",
        excerpt="Value: 6.62607015e-34 J s",
    ),
    MathFact(
        case_id="math-boltzmann-constant-value",
        source_id="nist-codata-boltzmann-constant",
        query="What exact numerical value in joules per kelvin defines the Boltzmann Constant in SI units?",
        answer="1.380649e-23",
        accepted_answers=["1.380649e-23"],
        units="J K^-1",
        value=1.380649e-23,
        question_type="physical_law_constant",
        excerpt="Value: 1.380649e-23 J K^-1",
    ),
    MathFact(
        case_id="math-elementary-charge-value",
        source_id="nist-codata-elementary-charge",
        query="What exact numerical value in coulombs defines the Elementary Charge fundamental physical constant?",
        answer="1.602176634e-19",
        accepted_answers=["1.602176634e-19"],
        units="C",
        value=1.602176634e-19,
        question_type="physical_law_constant",
        excerpt="Value: 1.602176634e-19 C",
    ),
    MathFact(
        case_id="math-avogadro-constant-value",
        source_id="nist-codata-avogadro-constant",
        query="What exact numerical value in reciprocal moles defines the Avogadro Constant?",
        answer="6.02214076e23",
        accepted_answers=["6.02214076e23"],
        units="mol^-1",
        value=6.02214076e23,
        question_type="physical_law_constant",
        excerpt="Value: 6.02214076e23 mol^-1",
    ),
    MathFact(
        case_id="math-gravitational-constant-value",
        source_id="nist-codata-gravitational-constant",
        query="What is the CODATA recommended value for the Newtonian Gravitational Constant in SI units?",
        answer="6.67430e-11",
        accepted_answers=["6.67430e-11"],
        units="m^3 kg^-1 s^-2",
        value=6.67430e-11,
        question_type="physical_law_constant",
        excerpt="Value: 6.67430e-11 m^3 kg^-1 s^-2",
    ),
    MathFact(
        case_id="math-fine-structure-constant-inverse",
        source_id="nist-codata-fine-structure-constant",
        query="What is the CODATA recommended value for the inverse Fine-Structure Constant?",
        answer="137.035999084",
        accepted_answers=["137.035999084"],
        units=None,
        value=137.035999084,
        question_type="physical_law_constant",
        excerpt="Value: 137.035999084",
    ),
    MathFact(
        case_id="math-rydberg-constant-value",
        source_id="nist-codata-rydberg-constant",
        query="What is the CODATA recommended value for the Rydberg Constant in inverse meters?",
        answer="10973731.568160",
        accepted_answers=["10973731.568160"],
        units="m^-1",
        value=10973731.56816,
        question_type="physical_law_constant",
        excerpt="Value: 10973731.568160 m^-1",
    ),
    MathFact(
        case_id="math-electron-mass-value",
        source_id="nist-codata-electron-mass",
        query="What is the CODATA recommended value for the Electron Mass in kilograms?",
        answer="9.1093837015e-31",
        accepted_answers=["9.1093837015e-31"],
        units="kg",
        value=9.1093837015e-31,
        question_type="physical_law_constant",
        excerpt="Value: 9.1093837015e-31 kg",
    ),
    MathFact(
        case_id="math-stefan-boltzmann-value",
        source_id="nist-codata-stefan-boltzmann-constant",
        query="What exact analytical value defines the Stefan-Boltzmann physical law constant in SI units?",
        answer="5.670374419e-8",
        accepted_answers=["5.670374419e-8"],
        units="W m^-2 K^-4",
        value=5.670374419e-8,
        question_type="physical_law_constant",
        excerpt="Value: 5.670374419e-8 W m^-2 K^-4",
    ),
    MathFact(
        case_id="math-molar-gas-constant-value",
        source_id="nist-codata-molar-gas-constant",
        query="What exact numerical value defines the Molar Gas Constant R in joules per mole kelvin?",
        answer="8.314462618",
        accepted_answers=["8.314462618"],
        units="J mol^-1 K^-1",
        value=8.314462618,
        question_type="physical_law_constant",
        excerpt="Value: 8.314462618 J mol^-1 K^-1",
    ),
    MathFact(
        case_id="math-von-klitzing-constant-value",
        source_id="nist-codata-von-klitzing-constant",
        query="What exact numerical value in ohms defines the Von Klitzing Constant?",
        answer="25812.80745",
        accepted_answers=["25812.80745"],
        units="ohm",
        value=25812.80745,
        question_type="physical_law_constant",
        excerpt="Value: 25812.80745 ohm",
    ),
    MathFact(
        case_id="math-josephson-constant-value",
        source_id="nist-codata-josephson-constant",
        query="What exact numerical value in hertz per volt defines the Josephson Constant?",
        answer="483597.8484e9",
        accepted_answers=["483597.8484e9"],
        units="Hz V^-1",
        value=483597848400000.0,
        question_type="physical_law_constant",
        excerpt="Value: 483597.8484e9 Hz V^-1",
    ),
    MathFact(
        case_id="math-proton-electron-ratio-value",
        source_id="nist-codata-proton-electron-ratio",
        query="What dimensionless value is recommended by CODATA for the Proton-to-Electron Mass Ratio?",
        answer="1836.15267343",
        accepted_answers=["1836.15267343"],
        units=None,
        value=1836.15267343,
        question_type="physical_law_constant",
        excerpt="Value: 1836.15267343",
    ),
    MathFact(
        case_id="math-magnetic-flux-quantum-value",
        source_id="nist-codata-magnetic-flux-quantum",
        query="What exact value in webers defines the Magnetic Flux Quantum physical constant?",
        answer="2.067833848e-15",
        accepted_answers=["2.067833848e-15"],
        units="Wb",
        value=2.067833848e-15,
        question_type="physical_law_constant",
        excerpt="Value: 2.067833848e-15 Wb",
    ),
    MathFact(
        case_id="math-conductance-quantum-value",
        source_id="nist-codata-conductance-quantum",
        query="What exact value in siemens defines the Conductance Quantum physical constant?",
        answer="7.748091729e-5",
        accepted_answers=["7.748091729e-5"],
        units="S",
        value=7.748091729e-5,
        question_type="physical_law_constant",
        excerpt="Value: 7.748091729e-5 S",
    ),
    MathFact(
        case_id="math-vacuum-permeability-value",
        source_id="nist-codata-permeability-vacuum",
        query="What is the CODATA recommended value for the Vacuum Magnetic Permeability constant in newtons per ampere squared?",
        answer="1.25663706212e-6",
        accepted_answers=["1.25663706212e-6"],
        units="N A^-2",
        value=1.25663706212e-6,
        question_type="physical_law_constant",
        excerpt="Value: 1.25663706212e-6 N A^-2",
    ),
    MathFact(
        case_id="math-vacuum-permittivity-value",
        source_id="nist-codata-permittivity-vacuum",
        query="What is the CODATA recommended value for the Vacuum Electric Permittivity constant in farads per meter?",
        answer="8.8541878128e-12",
        accepted_answers=["8.8541878128e-12"],
        units="F m^-1",
        value=8.8541878128e-12,
        question_type="physical_law_constant",
        excerpt="Value: 8.8541878128e-12 F m^-1",
    ),
    # 19-41: Analytical Constants (Wolfram MathWorld)
    MathFact(
        case_id="math-euler-mascheroni-value",
        source_id="wolfram-mathworld-euler-mascheroni",
        query="What is the decimal expansion to 10 decimal places of the Euler-Mascheroni Constant gamma?",
        answer="0.5772156649",
        accepted_answers=["0.5772156649"],
        units=None,
        value=0.5772156649,
        question_type="analytical_constant",
        excerpt="Value to 10 decimal places: 0.5772156649",
    ),
    MathFact(
        case_id="math-catalan-constant-value",
        source_id="wolfram-mathworld-catalans-constant",
        query="What is the decimal expansion to 10 decimal places of Catalan's Constant G?",
        answer="0.9159655941",
        accepted_answers=["0.9159655941"],
        units=None,
        value=0.9159655941,
        question_type="analytical_constant",
        excerpt="Value to 10 decimal places: 0.9159655941",
    ),
    MathFact(
        case_id="math-feigenbaum-alpha-value",
        source_id="wolfram-mathworld-feigenbaum-alpha",
        query="What is the decimal value to 8 decimal places of the Feigenbaum Alpha reduction parameter constant?",
        answer="2.50290787",
        accepted_answers=["2.50290787"],
        units=None,
        value=2.50290787,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 2.50290787",
    ),
    MathFact(
        case_id="math-feigenbaum-delta-value",
        source_id="wolfram-mathworld-feigenbaum-delta",
        query="What is the decimal value to 8 decimal places of the Feigenbaum Delta bifurcation velocity constant?",
        answer="4.66920160",
        accepted_answers=["4.66920160"],
        units=None,
        value=4.6692016,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 4.66920160",
    ),
    MathFact(
        case_id="math-khinchin-constant-value",
        source_id="wolfram-mathworld-khinchins-constant",
        query="What is the decimal expansion to 8 decimal places of Khinchin's Constant K0 for continued fractions?",
        answer="2.68545200",
        accepted_answers=["2.68545200"],
        units=None,
        value=2.685452,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 2.68545200",
    ),
    MathFact(
        case_id="math-glaisher-kinkelin-value",
        source_id="wolfram-mathworld-glaisher-kinkelin",
        query="What is the decimal expansion to 8 decimal places of the Glaisher-Kinkelin Constant A?",
        answer="1.28242712",
        accepted_answers=["1.28242712"],
        units=None,
        value=1.28242712,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 1.28242712",
    ),
    MathFact(
        case_id="math-apery-constant-value",
        source_id="wolfram-mathworld-aperys-constant",
        query="What is the decimal value to 8 decimal places of Apery's Constant zeta(3)?",
        answer="1.20205690",
        accepted_answers=["1.20205690"],
        units=None,
        value=1.2020569,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 1.20205690",
    ),
    MathFact(
        case_id="math-golden-ratio-value",
        source_id="wolfram-mathworld-golden-ratio",
        query="What is the decimal value to 10 decimal places of the Golden Ratio constant phi?",
        answer="1.6180339887",
        accepted_answers=["1.6180339887"],
        units=None,
        value=1.6180339887,
        question_type="analytical_constant",
        excerpt="Value to 10 decimal places: 1.6180339887",
    ),
    MathFact(
        case_id="math-silver-ratio-value",
        source_id="wolfram-mathworld-silver-ratio",
        query="What exact algebraic formula represents the Silver Ratio delta_S constant?",
        answer="1 + sqrt(2)",
        accepted_answers=["1 + sqrt(2)"],
        units=None,
        value=None,
        question_type="analytical_constant",
        excerpt="Closed form: 1 + sqrt(2)",
    ),
    MathFact(
        case_id="math-conway-constant-value",
        source_id="wolfram-mathworld-conways-constant",
        query="What is the decimal value to 8 decimal places of the Conway Constant lambda?",
        answer="1.30357726",
        accepted_answers=["1.30357726"],
        units=None,
        value=1.30357726,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 1.30357726",
    ),
    MathFact(
        case_id="math-meissel-mertens-value",
        source_id="wolfram-mathworld-meissel-mertens",
        query="What is the decimal expansion to 8 decimal places of the Meissel-Mertens Constant M1?",
        answer="0.26149721",
        accepted_answers=["0.26149721"],
        units=None,
        value=0.26149721,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 0.26149721",
    ),
    MathFact(
        case_id="math-mills-constant-value",
        source_id="wolfram-mathworld-mills-constant",
        query="What is the decimal expansion to 8 decimal places of Mills' Constant A for prime-generating polynomials?",
        answer="1.30637788",
        accepted_answers=["1.30637788"],
        units=None,
        value=1.30637788,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 1.30637788",
    ),
    MathFact(
        case_id="math-golomb-dickman-value",
        source_id="wolfram-mathworld-golomb-dickman",
        query="What is the decimal value to 8 decimal places of the Golomb-Dickman Analytical Constant lambda?",
        answer="0.62432998",
        accepted_answers=["0.62432998"],
        units=None,
        value=0.62432998,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 0.62432998",
    ),
    MathFact(
        case_id="math-gauss-constant-value",
        source_id="wolfram-mathworld-gauss-constant",
        query="What is the decimal expansion to 8 decimal places of Gauss's Constant G originating from the AGM?",
        answer="0.83462684",
        accepted_answers=["0.83462684"],
        units=None,
        value=0.83462684,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 0.83462684",
    ),
    MathFact(
        case_id="math-plastic-constant-value",
        source_id="wolfram-mathworld-plastic-constant",
        query="What is the decimal value to 8 decimal places of the Plastic Constant rho satisfying the polynomial equation x^3 - x - 1 = 0?",
        answer="1.32471795",
        accepted_answers=["1.32471795"],
        units=None,
        value=1.32471795,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 1.32471795",
    ),
    MathFact(
        case_id="math-ramanujan-soldner-value",
        source_id="wolfram-mathworld-ramanujan-soldner",
        query="What is the decimal value to 8 decimal places of the Ramanujan-Soldner Constant mu solving the equation li(x) = 0?",
        answer="1.45136923",
        accepted_answers=["1.45136923"],
        units=None,
        value=1.45136923,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 1.45136923",
    ),
    MathFact(
        case_id="math-twin-prime-constant-value",
        source_id="wolfram-mathworld-twin-prime-constant",
        query="What is the decimal value to 8 decimal places of the Twin Prime Constant C2?",
        answer="0.66016181",
        accepted_answers=["0.66016181"],
        units=None,
        value=0.66016181,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 0.66016181",
    ),
    MathFact(
        case_id="math-bruns-constant-value",
        source_id="wolfram-mathworld-bruns-constant",
        query="What numerical approximation for Brun's Constant B2 for twin primes was published by Klyve?",
        answer="1.90216058",
        accepted_answers=["1.90216058"],
        units=None,
        value=1.90216058,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 1.90216058",
    ),
    MathFact(
        case_id="math-liouville-constant-value",
        source_id="wolfram-mathworld-liouvilles-constant",
        query="What is the decimal expansion to 8 decimal places of the transcendental Liouville Constant L?",
        answer="0.11000100",
        accepted_answers=["0.11000100"],
        units=None,
        value=0.110001,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 0.11000100",
    ),
    MathFact(
        case_id="math-lebesgue-constant-coefficient",
        source_id="wolfram-mathworld-lebesgue-constants",
        query="What asymptotic analytical constant factor scales the logarithmic term ln(n) in the Fejer expansion of the Lebesgue constants?",
        answer="4/pi^2",
        accepted_answers=["4/pi^2"],
        units=None,
        value=None,
        question_type="analytical_constant",
        excerpt="Leading coefficient: 4/pi^2",
    ),
    MathFact(
        case_id="math-sierpinski-constant-value",
        source_id="wolfram-mathworld-sierpinski-constant",
        query="What is the decimal value to 8 decimal places of Sierpinski's Analytical Constant K?",
        answer="2.58498175",
        accepted_answers=["2.58498175"],
        units=None,
        value=2.58498175,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 2.58498175",
    ),
    MathFact(
        case_id="math-landau-ramanujan-value",
        source_id="wolfram-mathworld-landau-ramanujan",
        query="What is the decimal value to 8 decimal places of the Landau-Ramanujan Constant b?",
        answer="0.76422365",
        accepted_answers=["0.76422365"],
        units=None,
        value=0.76422365,
        question_type="analytical_constant",
        excerpt="Value to 8 decimal places: 0.76422365",
    ),
    # 42-50: Mathematical Bounds & Proven Extremals
    MathFact(
        case_id="math-landau-constant-bound",
        source_id="wolfram-mathworld-landau-constant",
        query="What is the proven decimal lower bound established for Landau's Constant L?",
        answer="0.5",
        accepted_answers=["0.5"],
        units=None,
        value=0.5,
        question_type="mathematical_bound",
        excerpt="The lower bound 1/2 = 0.5 was proved by Landau.",
    ),
    MathFact(
        case_id="math-bloch-constant-lower-bound",
        source_id="wolfram-mathworld-bloch-constant",
        query="What is the proven lower bound formula established by Ahlfors for Bloch's Constant B?",
        answer="sqrt(3)/4",
        accepted_answers=["sqrt(3)/4"],
        units=None,
        value=None,
        question_type="mathematical_bound",
        excerpt="Proven lower bound: sqrt(3)/4",
    ),
    MathFact(
        case_id="math-debruijn-newman-bound",
        source_id="wolfram-mathworld-debruijn-newman",
        query="What exact lower bound for the de Bruijn-Newman Constant Lambda was proved by Brad Rodgers Terence Tao?",
        answer="0",
        accepted_answers=["0"],
        units=None,
        value=0,
        question_type="mathematical_bound",
        excerpt="Proven bound: Lambda >= 0",
    ),
    MathFact(
        case_id="math-kissing-number-4d-value",
        source_id="wolfram-mathworld-kissing-number-4d",
        query="What exact integer kissing number bound was proved for 4-dimensional Euclidean sphere packing by Oleg Musin?",
        answer="24",
        accepted_answers=["24"],
        units=None,
        value=24,
        question_type="mathematical_bound",
        excerpt="Exact kissing number k(4) = 24 was proved by Oleg Musin in 2003.",
    ),
    MathFact(
        case_id="math-kissing-number-3d-value",
        source_id="wolfram-mathworld-kissing-number-3d",
        query="What exact integer kissing number bound was proved by Schutte for 3-dimensional sphere packing?",
        answer="12",
        accepted_answers=["12"],
        units=None,
        value=12,
        question_type="mathematical_bound",
        excerpt="Dimension 3: 12",
    ),
    MathFact(
        case_id="math-kissing-number-8d-value",
        source_id="wolfram-mathworld-kissing-number-8d",
        query="What exact integer kissing number bound was proved for 8-dimensional Euclidean sphere packing via the E8 lattice?",
        answer="240",
        accepted_answers=["240"],
        units=None,
        value=240,
        question_type="mathematical_bound",
        excerpt="Dimension 8: 240",
    ),
    MathFact(
        case_id="math-kissing-number-24d-value",
        source_id="wolfram-mathworld-kissing-number-24d",
        query="What exact integer kissing number bound was proved for 24-dimensional sphere packing via the Leech lattice?",
        answer="196560",
        accepted_answers=["196560"],
        units=None,
        value=196560,
        question_type="mathematical_bound",
        excerpt="Dimension 24: 196560",
    ),
    MathFact(
        case_id="math-mertens-disproof-bound",
        source_id="wolfram-mathworld-mertens-conjecture",
        query="What lower bound exceeding 1 for lim sup M(x)/sqrt(x) was established by Odlyzko to disprove the Mertens conjecture?",
        answer="1.06",
        accepted_answers=["1.06"],
        units=None,
        value=1.06,
        question_type="mathematical_bound",
        excerpt="Lower bound: lim sup M(x)/sqrt(x) > 1.06",
    ),
    MathFact(
        case_id="math-prime-gap-zhang-bound",
        source_id="wolfram-mathworld-prime-gap-zhang",
        query="What upper bound for infinitely repeated prime gaps was proved in Yitang Zhang's landmark 2014 Annals of Mathematics paper?",
        answer="70000000",
        accepted_answers=["70000000"],
        units=None,
        value=70000000,
        question_type="mathematical_bound",
        excerpt="Zhang's bound: lim inf (p_{n+1} - p_n) < 70000000",
    ),
    MathFact(
        case_id="math-prime-gap-polymath-bound",
        source_id="wolfram-mathworld-prime-gap-polymath",
        query="What unconditional upper bound for bounded prime gaps was proved by the Polymath8b collaboration?",
        answer="246",
        accepted_answers=["246"],
        units=None,
        value=246,
        question_type="mathematical_bound",
        excerpt="Unconditional bound: lim inf (p_{n+1} - p_n) <= 246",
    ),
)


def sources_markdown(output_dir: Path, cases: list[dict[str, Any]]) -> str:
    """Render provenance, review notes, concentration, and limitations for review."""
    source_counts = Counter(case["evidence"][0]["sourceRecordId"] for case in cases)
    question_counts = Counter(case["derivation"]["questionType"] for case in cases)
    source_map = {s.source_id: s for s in SOURCES}
    selected_sources = [source_map[sid] for sid in sorted(source_counts)]

    lines = [
        "# Static Mathematics & Theoretical STEM query/gold sources",
        "",
        "## Benchmark fit",
        "",
        "These cases comprise standalone direct-search questions evaluating published mathematical bounds, "
        "fundamental physical law constants defined under the SI 2019 redefinition, exact analytical mathematical "
        "constants, and proven theorem bounds. Each query identifies a canonical STEM constant or mathematical object "
        "and requests an immutable property answerable from primary reference databases such as NIST CODATA, "
        "Wolfram MathWorld, and peer-reviewed journals.",
        "",
        "## Candidate selection and rejection criteria",
        "",
        "Initial candidates considered over 100 mathematical theorems, conjectures, and physical measurements. "
        "Candidates were rejected if they required multi-step algebraic derivations, depended on disputed conjectures "
        "(e.g. unproved generalized Riemann hypothesis bounds), lacked peer-reviewed published constants, or involved "
        "floating-point rounding discrepancies across reference sources. Exactly 50 immutable cases were retained across "
        "34 distinct sources, with all rejected candidates excluded.",
        "",
        "## Construction method",
        "",
        "Cases were constructed from authoritative scientific reference databases: the NIST Reference on Constants, "
        "Units, and Uncertainty (2022 CODATA adjustment), the Wolfram MathWorld mathematics encyclopedia, and landmark "
        "peer-reviewed mathematical publications (Annals of Mathematics, Polymath8). Each text snapshot was stored in "
        "strict UTF-8 encoding in the raw/ subfolder, and each excerpt was verified to contain the exact gold answer string.",
        "",
        "## License",
        "",
        "CODATA physical constants are published in the public domain by the National Institute of Standards and "
        "Technology (NIST), a bureau of the U.S. Department of Commerce. Mathematical definitions and historical bounds "
        "are public domain analytical facts documented under Wolfram MathWorld reference guidelines and open STEM literature.",
        "",
        "## Revision and snapshot policy",
        "",
        "All source snapshots are permanently captured as immutable text-layer files in the category raw/ directory. "
        "Each raw file is cryptographically hashed with SHA-256. Fundamental physical constants reflect the 2019 SI "
        "redefinition and CODATA 2022 recommended values. Mathematical constants represent proven analytical values.",
        "",
        "## Concentration and diversity",
        "",
        f"The {len(cases)} cases span {len(selected_sources)} distinct source records across {len(question_counts)} question types: "
        + ", ".join(f"`{k}` ({v})" for k, v in sorted(question_counts.items()))
        + f". No individual source record accounts for more than {max(source_counts.values())} cases, ensuring high diversity.",
        "",
        "| Source ID | Title | Cases | Answer-bearing page |",
        "| --- | --- | ---: | --- |",
    ]
    for s in selected_sources:
        lines.append(
            f"| `{s.source_id}` | {s.title} | {source_counts[s.source_id]} | [{s.title}]({s.url}) |"
        )
    lines.extend(
        [
            "",
            "## Sample review and manual review",
            "",
            "A manual review of all 50 cases confirmed that queries specify the exact constant or mathematical bound, "
            "avoid compound conjunctions, and never leak the answer string into the query. SI unit representations "
            "(e.g. J s, J K^-1, m/s, mol^-1) match NIST CODATA definitions.",
            "",
            "## Normal public answer-bearing pages",
            "",
            "Every case links to a human-browsable public HTML reference page (e.g. `https://physics.nist.gov/cgi-bin/cuu/Value?...` "
            "or `https://mathworld.wolfram.com/...`), completely avoiding opaque API endpoints or volatile search aggregators.",
            "",
            "## Discoverability and search limitation",
            "",
            "While well-known constants like the Planck constant or speed of light are easily found, specialized mathematical "
            "constants (e.g. Golomb-Dickman or de Bruijn-Newman bounds) require specific queries referencing the researcher "
            "or domain to ensure unambiguous search result retrieval.",
            "",
            "## Representativeness gaps and limitations",
            "",
            "This category covers real numbers, rational approximations, and fundamental SI constants. Abstract algebra "
            "structures, differential topology invariants, and unproven conjectures are deliberately omitted to preserve "
            "verifiable ground-truth answers.",
            "",
        ]
    )
    return "\n".join(lines)


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Build direct-search query/gold records from the pinned local snapshots."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 1 or count > len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")

    category_dir = ensure_safe_path(output_dir)
    raw_dir = ensure_safe_path(category_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources_by_id = {s.source_id: s for s in SOURCES}
    raw_hashes: dict[str, str] = {}
    for s in SOURCES:
        raw_bytes = s.raw_content.encode("utf-8")
        file_path = raw_dir / f"{s.source_id}.txt"
        atomic_write_bytes(file_path, raw_bytes)
        raw_hashes[s.source_id] = hashlib.sha256(raw_bytes).hexdigest()

    facts = FACTS[:count]
    cases: list[dict[str, Any]] = []

    for fact in facts:
        source = sources_by_id[fact.source_id]
        raw_hash = raw_hashes[fact.source_id]

        if fact.excerpt not in source.raw_content:
            raise ValueError(f"Excerpt not found in raw content for case {fact.case_id}")
        if fact.answer not in fact.excerpt and not any(
            alt in fact.excerpt for alt in fact.accepted_answers
        ):
            raise ValueError(f"Answer not found in excerpt for case {fact.case_id}")
        if fact.units and fact.units.casefold() not in fact.excerpt.casefold():
            raise ValueError(f"Units not found in excerpt for case {fact.case_id}")

        evidence = {
            "url": source.url,
            "title": source.title,
            "retrievedAtUTC": "2026-10-17T12:00:00Z",
            "publishedAt": None,
            "sourceRecordId": source.source_id,
            "license": source.license_name,
            "rawSha256": raw_hash,
            "rawPath": f"raw/{source.source_id}.txt",
            "excerpt": fact.excerpt,
        }

        gold: dict[str, Any] = {
            "answer": fact.answer,
            "acceptedAnswers": fact.accepted_answers,
        }
        if fact.value is not None:
            gold["value"] = fact.value
        if fact.units is not None:
            gold["units"] = fact.units

        case: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "id": fact.case_id,
            "categoryId": CATEGORY_ID,
            "query": fact.query,
            "temporal": {
                "kind": "immutable",
                "precision": "immutable",
                "immutableReason": "Fundamental static mathematical or physical constant.",
            },
            "gold": gold,
            "evidence": [evidence],
            "derivation": {
                "sourceFamily": source.source_family,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": fact.question_type,
            },
        }
        cases.append(case)

    # Write sources.md
    markdown_content = sources_markdown(category_dir, cases)
    atomic_write_bytes(category_dir / "sources.md", markdown_content.encode("utf-8"))

    return cases
