import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

DEFAULT_FILENAME_PATTERN = "{account_name}_{account_id}_{statement_date}_{ending_balance}.csv"

_TEMPLATE_FIELDS = {
    "account_name": r"(?P<account_name>[A-Za-z0-9_]+)",
    "last8": r"(?P<last8>[A-Za-z0-9][A-Za-z0-9_-]{1,31})",
    "account_id": r"(?P<account_id>[A-Za-z0-9][A-Za-z0-9_-]{1,31})",
    "statement_date": r"(?P<statement_date>[A-Za-z0-9._/-]+)",
    "ending_balance": r"(?P<ending_balance>-?\d+\.\d{2})",
}


@dataclass
class FilenameMetadata:
    account_name: str = ""
    account_id: str = ""
    statement_date: str = ""
    ending_balance: str = ""


@dataclass
class ParseResult:
    metadata: FilenameMetadata | None
    error: str = ""


def build_filename_regex(template: str) -> re.Pattern[str]:
    text = template or DEFAULT_FILENAME_PATTERN
    stripped = re.sub(r"\{[a-z0-9_]+\}", "", text)
    if "{" in stripped or "}" in stripped:
        raise ValueError("Pattern contains unknown placeholders.")

    parts: list[str] = []
    cursor = 0
    token_pattern = re.compile(r"\{([a-z0-9_]+)\}")

    for match in token_pattern.finditer(text):
        start, end = match.span()
        parts.append(re.escape(text[cursor:start]))
        name = match.group(1)
        token = _TEMPLATE_FIELDS.get(name)
        if not token:
            raise ValueError("Pattern contains unknown placeholders.")
        parts.append(token)
        cursor = end

    parts.append(re.escape(text[cursor:]))

    return re.compile("^" + "".join(parts) + "$")


def parse_filename_metadata(path: Path, template: str = DEFAULT_FILENAME_PATTERN) -> ParseResult:
    try:
        regex = build_filename_regex(template)
    except ValueError as exc:
        return ParseResult(None, str(exc))

    match = regex.match(path.name)
    if not match:
        return ParseResult(None, "Filename does not match the configured pattern.")

    values = match.groupdict()
    date_text = values.get("statement_date", "")
    balance_text = values.get("ending_balance", "")

    normalized_date = normalize_statement_date(date_text)
    if not normalized_date:
        return ParseResult(None, "Detected statement date is invalid.")

    normalized_balance = normalize_balance(balance_text)
    if not normalized_balance:
        return ParseResult(None, "Detected ending balance is invalid.")

    account_id = values.get("account_id") or values.get("last8", "")
    return ParseResult(
        FilenameMetadata(
            account_name=values.get("account_name", ""),
            account_id=account_id,
            statement_date=normalized_date,
            ending_balance=normalized_balance,
        )
    )


def normalize_statement_date(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    compact = re.sub(r"[^0-9]", "", text)
    if len(compact) == 8 and compact[:4].isdigit() and compact[:4].startswith(("19", "20")):
        try:
            return datetime.strptime(compact, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return ""

    pieces = [part for part in re.split(r"[-_./]", text) if part]
    if len(pieces) == 3 and all(part.isdigit() for part in pieces):
        try:
            if len(pieces[0]) == 4:
                year, month, day = int(pieces[0]), int(pieces[1]), int(pieces[2])
            elif len(pieces[2]) == 4:
                year = int(pieces[2])
                first = int(pieces[0])
                second = int(pieces[1])
                if first > 12:
                    day, month = first, second
                elif second > 12:
                    month, day = first, second
                else:
                    month, day = first, second
            else:
                return ""
            dt = datetime(year, month, day)
        except ValueError:
            return ""
        return dt.strftime("%Y-%m-%d")

    common_formats = (
        "%Y-%m-%d",
        "%Y_%m_%d",
        "%Y.%m.%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%m_%d_%Y",
        "%m.%d.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d_%m_%Y",
        "%d.%m.%Y",
    )
    for fmt in common_formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def normalize_balance(value: str) -> str:
    text = (value or "").strip().replace(",", "")
    if not text:
        return ""

    try:
        amount = Decimal(text)
    except InvalidOperation:
        return ""

    normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{normalized:.2f}"
