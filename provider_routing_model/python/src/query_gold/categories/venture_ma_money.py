"""Money token parsing for first-party funding and deal facts."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_MONEY_RE = re.compile(
    r"(?P<currency>USD|EUR|GBP|CAD|AUD|JPY|CNY|[$???????])"
    r"\s*(?P<number>\d[\d,]*(?:\.\d+)?)"
    r"\s*(?P<scale>trillion|billion|million|thousand|tn|bn|m|b|t|k)?\b",
    re.IGNORECASE,
)


def _parse_money_token(token: str) -> tuple[Decimal, str]:
    match = _MONEY_RE.fullmatch(token.strip())
    if match is None:
        raise ValueError("money answer token is not a supported amount")
    raw_currency = match.group("currency").upper()
    currency = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}.get(raw_currency, raw_currency)
    try:
        amount = Decimal(match.group("number").replace(",", ""))
    except InvalidOperation as error:
        raise ValueError("money answer token has an invalid numeric amount") from error
    scale_name = (match.group("scale") or "").casefold()
    scale = {
        "": Decimal(1),
        "thousand": Decimal(1000),
        "k": Decimal(1000),
        "million": Decimal(1000000),
        "m": Decimal(1000000),
        "billion": Decimal(1000000000),
        "bn": Decimal(1000000000),
        "b": Decimal(1000000000),
        "trillion": Decimal(1000000000000),
        "tn": Decimal(1000000000000),
        "t": Decimal(1000000000000),
    }.get(scale_name)
    if scale is None:
        raise ValueError("money answer token has an unsupported scale")
    return (amount * scale, currency)
