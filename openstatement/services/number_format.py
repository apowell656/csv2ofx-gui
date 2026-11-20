"""Locale-aware parsing and detection for CSV amounts, dates, currencies, and delimiters.

US exports typically look like ``1,234.56`` and ``11/13/2026`` while many
other countries export ``1.234,56``, ``1 234,56``, ``1'234.56``, ``13.11.2026``,
``2026/11/13`` or ``13. Nov. 2026``. These helpers let a profile state (or the
app guess) which convention a file uses.

The amount parser and month-name normaliser are also emitted as source text into
the csv2ofx mapping file (see ``conversion.write_mapping_file``), so keep them
self-contained: only ``re``, ``unicodedata`` and ``decimal`` may be used.
"""

import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

DECIMAL_PERIOD = "."
DECIMAL_COMMA = ","
DECIMAL_SEPARATORS = (DECIMAL_PERIOD, DECIMAL_COMMA)

# ---------------------------------------------------------------------------
# Amounts
# ---------------------------------------------------------------------------

_STRIP_CHARS_RE = re.compile(r"[^0-9.,+\-]")
# Unicode minus, en dash, figure dash, small/full-width hyphen-minus.
_MINUS_LIKE = "−–‒﹣－"
# "DR 12.50" / "12.50 DR" / "12.50Cr." -- but not currency codes like "CRC" or "SCR".
_LEADING_DRCR_RE = re.compile(r"^(dr|cr)\.?(?![a-z])\s*(.*)$", re.IGNORECASE)
_TRAILING_DRCR_RE = re.compile(r"^(.*?)(?<![a-z])(dr|cr)\.?$", re.IGNORECASE)


def normalize_decimal_separator(value: str | None) -> str:
    return DECIMAL_COMMA if (value or "").strip() == DECIMAL_COMMA else DECIMAL_PERIOD


def parse_amount(value: object, decimal_separator: str = DECIMAL_PERIOD) -> Decimal | None:
    """Parse a bank amount string into a Decimal, or None when empty/invalid.

    Handles any currency symbol or code, spaces (including non-breaking and
    narrow spaces), apostrophe grouping (``1'234.56``), Indian grouping
    (``1,23,456.78``), accounting parentheses (``(12.50)``), trailing minus
    signs (``12,50-``), Unicode minus signs (``−12,50``) and ``DR``/``CR``
    markers (``12.50 DR`` is negative).
    """
    text = str(value if value is not None else "").strip()
    for ch in _MINUS_LIKE:
        text = text.replace(ch, "-")
    if not text:
        return None

    negative = False
    leading = _LEADING_DRCR_RE.match(text)
    trailing = None if leading else _TRAILING_DRCR_RE.match(text)
    if leading:
        negative = leading.group(1).lower() == "dr"
        text = leading.group(2).strip()
    elif trailing:
        negative = trailing.group(2).lower() == "dr"
        text = trailing.group(1).strip()

    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()
    if text.endswith("-") and not text.startswith("-"):
        negative = True
        text = text[:-1].strip()

    cleaned = _STRIP_CHARS_RE.sub("", text)
    if decimal_separator == DECIMAL_COMMA:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    return -amount if negative else amount


def detect_decimal_separator(samples: Iterable[str]) -> str | None:
    """Guess the decimal separator used by a set of amount strings.

    Returns None when the samples give no evidence either way (e.g. all
    whole numbers), so callers can keep their current setting.
    """
    period_votes = 0
    comma_votes = 0

    for raw in samples:
        text = _STRIP_CHARS_RE.sub("", str(raw or ""))
        if not text:
            continue
        last_period = text.rfind(".")
        last_comma = text.rfind(",")

        if last_period >= 0 and last_comma >= 0:
            # Whichever separator appears last is the decimal mark.
            if last_comma > last_period:
                comma_votes += 1
            else:
                period_votes += 1
            continue

        mark, idx = (",", last_comma) if last_comma >= 0 else (".", last_period)
        if idx < 0:
            continue
        digits_after = len(text) - idx - 1
        if text.count(mark) > 1:
            # "1.234.567" / "1,234,567": a repeated mark is a thousands separator.
            if mark == ",":
                period_votes += 1
            else:
                comma_votes += 1
        elif digits_after == 3:
            # "1,234" or "1.234" is ambiguous; don't vote.
            continue
        elif mark == ",":
            comma_votes += 1
        else:
            period_votes += 1

    if comma_votes > period_votes:
        return DECIMAL_COMMA
    if period_votes > comma_votes:
        return DECIMAL_PERIOD
    return None


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

# Month names (full forms, plus Polish genitive) for the languages most often
# seen in bank exports. Abbreviations are matched as unambiguous prefixes, so
# "Nov.", "févr", "Okt", "dic", "set" etc. all resolve without listing them.
MONTH_NAMES: dict[int, tuple[str, ...]] = {
    1: ("january", "januar", "janvier", "enero", "gennaio", "janeiro", "januari", "styczen", "stycznia"),
    2: ("february", "februar", "fevrier", "febrero", "febbraio", "fevereiro", "februari", "luty", "lutego"),
    3: ("march", "marz", "maerz", "mars", "marzo", "marco", "maart", "marts", "marzec", "marca", "mrt"),
    4: ("april", "avril", "abril", "aprile", "kwiecien", "kwietnia"),
    5: ("may", "mai", "mayo", "maggio", "maio", "mei", "maj", "maja"),
    6: ("june", "juni", "juin", "junio", "giugno", "junho", "czerwiec", "czerwca"),
    7: ("july", "juli", "juillet", "julio", "luglio", "julho", "lipiec", "lipca"),
    8: ("august", "aout", "agosto", "augustus", "augusti", "sierpien", "sierpnia"),
    9: ("september", "septembre", "septiembre", "settembre", "setembro", "wrzesien", "wrzesnia"),
    10: ("october", "oktober", "octobre", "octubre", "ottobre", "outubro", "pazdziernik", "pazdziernika"),
    11: ("november", "novembre", "noviembre", "novembro", "listopad", "listopada"),
    12: ("december", "dezember", "decembre", "diciembre", "dicembre", "dezembro", "desember", "grudzien", "grudnia"),
}
ENGLISH_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_MONTH_WORD_RE = re.compile(r"[^\W\d_]+\.?")


def _fold(text: str) -> str:
    """Lowercase and strip accents/umlauts ("März" -> "marz", "févr" -> "fevr")."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("ł", "l")


def _month_for_word(word: str) -> int | None:
    token = _fold(word.rstrip("."))
    if len(token) < 3:
        return None
    matches = {month for month, names in MONTH_NAMES.items() for name in names if name.startswith(token)}
    return matches.pop() if len(matches) == 1 else None


def normalize_date_text(value: object) -> str:
    """Replace localized month names with English abbreviations and tidy whitespace.

    "13. Nov. 2026" -> "13. Nov 2026", "13 de noviembre de 2026" -> "13 de Nov de 2026",
    "3 März 2026" -> "3 Mar 2026". Purely numeric dates pass through unchanged.
    """
    text = " ".join(str(value if value is not None else "").split())
    if not text or not any(ch.isalpha() for ch in text):
        return text

    def replace(match: re.Match) -> str:
        month = _month_for_word(match.group(0))
        return ENGLISH_MONTH_ABBR[month - 1] if month else match.group(0)

    return _MONTH_WORD_RE.sub(replace, text)


_BASE_DATE_FORMATS = (
    # ISO / year-first (ISO, China, Japan, Korea, Hungary, Sweden, Lithuania)
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y.%m.%d.",
    "%Y. %m. %d.",
    "%Y%m%d",
    # Numeric, month-first (US) and day-first (most of the world)
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%d/%m/%y",
    "%d.%m.%y",
    "%d-%m-%y",
    # Month names (after normalize_date_text has made them English)
    "%d %b %Y",
    "%d. %b %Y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %y",
    "%d/%b/%Y",
    "%d de %b de %Y",
    "%b %d, %Y",
    "%b %d %Y",
)
_TIME_SUFFIXES = ("", " %H:%M", " %H:%M:%S", "T%H:%M:%S", ", %H:%M", ", %H:%M:%S")

CANDIDATE_DATE_FORMATS = tuple(base + suffix for suffix in _TIME_SUFFIXES for base in _BASE_DATE_FORMATS)


def _is_month_first(fmt: str) -> bool:
    if fmt.startswith("%Y"):
        return False
    month = fmt.find("%m") if "%m" in fmt else fmt.find("%b")
    return 0 <= month < fmt.find("%d")


def detect_date_format(samples: Iterable[str], prefer_dayfirst: bool = False) -> str | None:
    """Return the first candidate strftime format that parses every sample.

    Samples are passed through ``normalize_date_text`` first, so the result is
    the format of the *normalized* text. When every sample is ambiguous (e.g.
    "03/04/2026"), month-first wins unless ``prefer_dayfirst`` is set.
    """
    values = [normalize_date_text(s) for s in samples if str(s or "").strip()]
    if not values:
        return None

    candidates = CANDIDATE_DATE_FORMATS
    if prefer_dayfirst:
        candidates = tuple(sorted(candidates, key=_is_month_first))

    for fmt in candidates:
        try:
            for value in values:
                datetime.strptime(value, fmt)
        except ValueError:
            continue
        return fmt
    return None


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

# Symbols that identify a single currency. "$", "kr", "¥" are deliberately
# absent because several currencies share them.
CURRENCY_SYMBOLS = (
    ("R$", "BRL"),
    ("zł", "PLN"),
    ("Kč", "CZK"),
    ("€", "EUR"),
    ("£", "GBP"),
    ("₹", "INR"),
    ("₩", "KRW"),
    ("₽", "RUB"),
    ("₺", "TRY"),
    ("₪", "ILS"),
    ("₱", "PHP"),
    ("₫", "VND"),
    ("₴", "UAH"),
    ("฿", "THB"),
    ("₦", "NGN"),
)

ISO_CURRENCY_CODES = frozenset(
    "AED ARS AUD BGN BHD BRL CAD CHF CLP CNY COP CZK DKK EGP EUR GBP HKD HUF IDR ILS INR ISK JPY "
    "KES KRW KWD MAD MXN MYR NGN NOK NZD PEN PHP PKR PLN QAR RON RSD RUB SAR SEK SGD THB TRY TWD "
    "UAH USD VND ZAR".split()
)

_ISO_CODE_RE = re.compile(r"(?<![A-Za-z])([A-Z]{3})(?![A-Za-z])")


def detect_currency(samples: Iterable[str]) -> str | None:
    """Guess an ISO 4217 code from amount strings or a currency column's values."""
    votes: dict[str, int] = {}
    for raw in samples:
        text = str(raw or "")
        found = None
        for code in _ISO_CODE_RE.findall(text):
            if code in ISO_CURRENCY_CODES:
                found = code
                break
        if not found:
            found = next((code for symbol, code in CURRENCY_SYMBOLS if symbol in text), None)
        if found:
            votes[found] = votes.get(found, 0) + 1

    if not votes:
        return None
    return max(votes, key=votes.get)


# ---------------------------------------------------------------------------
# Delimiter
# ---------------------------------------------------------------------------


def detect_delimiter(first_line: str, current: str) -> str:
    """Pick a better delimiter if the current one clearly doesn't split the header line."""
    if current and current in first_line:
        return current
    counts = {candidate: first_line.count(candidate) for candidate in (";", "\t", ",", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else current
