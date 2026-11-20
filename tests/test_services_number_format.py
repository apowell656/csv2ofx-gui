from decimal import Decimal

import pytest

from openstatement.services.number_format import (
    detect_currency,
    detect_date_format,
    detect_decimal_separator,
    detect_delimiter,
    normalize_date_text,
    parse_amount,
)


@pytest.mark.parametrize(
    ("raw", "separator", "expected"),
    [
        ("1,234.56", ".", Decimal("1234.56")),
        ("$1,234.56", ".", Decimal("1234.56")),
        ("(12.50)", ".", Decimal("-12.50")),
        ("-12.50", ".", Decimal("-12.50")),
        ("1.234,56", ",", Decimal("1234.56")),
        ("-12,50", ",", Decimal("-12.50")),
        ("12,50-", ",", Decimal("-12.50")),
        ("1.234,56 €", ",", Decimal("1234.56")),
        ("1 234,56", ",", Decimal("1234.56")),
        ("1'234.56", ".", Decimal("1234.56")),
        ("+5", ",", Decimal("5")),
        ("", ".", None),
        ("abc", ".", None),
        ("-", ",", None),
        ("−12,50 kr", ",", Decimal("-12.50")),
        ("–12.50", ".", Decimal("-12.50")),
        ("12.50 DR", ".", Decimal("-12.50")),
        ("DR 12.50", ".", Decimal("-12.50")),
        ("12.50Cr.", ".", Decimal("12.50")),
        ("CRC 1.234,50", ",", Decimal("1234.50")),
        ("1234 SCR", ".", Decimal("1234")),
        ("£1,234.56", ".", Decimal("1234.56")),
        ("R$ 1.234,56", ",", Decimal("1234.56")),
        ("¥12,345", ".", Decimal("12345")),
        ("1,23,456.78", ".", Decimal("123456.78")),
        ("-1.234,567 KWD", ",", Decimal("-1234.567")),
        ("1 234,50 zł", ",", Decimal("1234.50")),
        ("NaN", ".", None),
    ],
)
def test_parse_amount(raw: str, separator: str, expected: Decimal | None) -> None:
    assert parse_amount(raw, separator) == expected


def test_detect_decimal_separator_comma() -> None:
    assert detect_decimal_separator(["-12,50", "1.234,56", "7,00"]) == ","


def test_detect_decimal_separator_period() -> None:
    assert detect_decimal_separator(["-12.50", "1,234.56", "$7.00"]) == "."


def test_detect_decimal_separator_ambiguous_returns_none() -> None:
    assert detect_decimal_separator(["1,234", "100", ""]) is None


def test_detect_decimal_separator_repeated_grouping() -> None:
    assert detect_decimal_separator(["1.234.567"]) == ","
    assert detect_decimal_separator(["1,234,567"]) == "."


def test_detect_date_format() -> None:
    assert detect_date_format(["13.11.2026", "01.12.2026"]) == "%d.%m.%Y"
    assert detect_date_format(["11/13/2026", "4/1/2026"]) == "%m/%d/%Y"
    assert detect_date_format(["13/11/2026", "01/12/2026"]) == "%d/%m/%Y"
    assert detect_date_format(["2026-11-13"]) == "%Y-%m-%d"
    assert detect_date_format(["13.11.26"]) == "%d.%m.%y"
    assert detect_date_format(["garbage"]) is None
    assert detect_date_format([]) is None


def test_detect_delimiter() -> None:
    assert detect_delimiter("Datum;Betrag;Saldo\n", ",") == ";"
    assert detect_delimiter("Date,Amount\n", ",") == ","
    assert detect_delimiter("Date\tAmount\n", ",") == "\t"
    assert detect_delimiter("SingleColumn\n", ",") == ","


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("13. Nov. 2026", "13. Nov 2026"),
        ("13 de noviembre de 2026", "13 de Nov de 2026"),
        ("3 März 2026", "3 Mar 2026"),
        ("3 Maerz 2026", "3 Mar 2026"),
        ("13 févr. 2026", "13 Feb 2026"),
        ("13 août 2026", "13 Aug 2026"),
        ("13 dic 2026", "13 Dec 2026"),
        ("13 settembre 2026", "13 Sep 2026"),
        ("13 outubro 2026", "13 Oct 2026"),
        ("13 mrt 2026", "13 Mar 2026"),
        ("13 mei 2026", "13 May 2026"),
        ("13 listopada 2026", "13 Nov 2026"),
        ("13 października 2026", "13 Oct 2026"),
        ("13 juil. 2026", "13 Jul 2026"),
        ("13 jui 2026", "13 jui 2026"),  # ambiguous juin/juillet: left alone
        ("13.11.2026", "13.11.2026"),
    ],
)
def test_normalize_date_text(raw: str, expected: str) -> None:
    assert normalize_date_text(raw) == expected


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        (["2026-11-13"], "%Y-%m-%d"),  # ISO
        (["2026/11/13"], "%Y/%m/%d"),  # Japan, China, Taiwan
        (["2026.11.13."], "%Y.%m.%d."),  # Hungary
        (["2026. 11. 13."], "%Y. %m. %d."),  # Korea
        (["20261113"], "%Y%m%d"),
        (["13.11.2026", "1.12.2026"], "%d.%m.%Y"),  # DE, AT, CH, PL, RU, NO, FI...
        (["13.11.26"], "%d.%m.%y"),
        (["13/11/2026"], "%d/%m/%Y"),  # UK, FR, ES, IT, IN, AU, BR...
        (["13-11-2026"], "%d-%m-%Y"),  # NL, DK, IN
        (["13-11-26"], "%d-%m-%y"),
        (["11/13/2026", "4/1/2026"], "%m/%d/%Y"),  # US
        (["13 Nov 2026"], "%d %b %Y"),
        (["13-Nov-26"], "%d-%b-%y"),
        (["13. Nov. 2026"], "%d. %b %Y"),
        (["13 de noviembre de 2026"], "%d de %b de %Y"),
        (["Nov 13, 2026"], "%b %d, %Y"),
        (["13.11.2026 14:30"], "%d.%m.%Y %H:%M"),
        (["13/11/2026 14:30:05"], "%d/%m/%Y %H:%M:%S"),
        (["2026-11-13T10:15:00"], "%Y-%m-%dT%H:%M:%S"),
        (["garbage"], None),
        ([], None),
    ],
)
def test_detect_date_format_international(samples: list[str], expected: str | None) -> None:
    assert detect_date_format(samples) == expected


def test_detect_date_format_ambiguous_prefers_dayfirst_when_asked() -> None:
    assert detect_date_format(["03/04/2026"]) == "%m/%d/%Y"
    assert detect_date_format(["03/04/2026"], prefer_dayfirst=True) == "%d/%m/%Y"
    # Unambiguous data wins over the preference.
    assert detect_date_format(["11/13/2026"], prefer_dayfirst=True) == "%m/%d/%Y"


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        (["12,50 €"], "EUR"),
        (["£12.50"], "GBP"),
        (["R$ 1.234,56"], "BRL"),
        (["1 234,50 zł"], "PLN"),
        (["₹1,23,456.78"], "INR"),
        (["1234 CHF", "5 CHF"], "CHF"),
        (["EUR", "EUR", "USD"], "EUR"),
        (["SEK"], "SEK"),
        (["$5.00"], None),  # USD/CAD/AUD/... ambiguous
        (["12,50 kr"], None),  # SEK/NOK/DKK ambiguous
        (["Grocery"], None),
    ],
)
def test_detect_currency(samples: list[str], expected: str | None) -> None:
    assert detect_currency(samples) == expected
