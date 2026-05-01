import csv
import importlib.util
import io
import re
import shutil
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..models.profile import BankProfile, quote_py_string, to_account_id

CSV2OFX_MODULE_RUNNER = "__csv2ofx_module__"


@dataclass
class OfxMetadataOverrides:
    account_id: str = ""
    statement_date: str = ""
    ending_balance: str = ""


def _mapping_column_name(column: str, has_header: bool) -> str:
    if has_header:
        return column
    match = re.fullmatch(r"col_(\d+)", (column or "").strip(), flags=re.IGNORECASE)
    if match:
        return f"column_{match.group(1)}"
    return column


def find_csv2ofx_binary() -> str | None:
    binary = shutil.which("csv2ofx")
    if binary:
        return binary

    if importlib.util.find_spec("csv2ofx.main") is not None:
        return CSV2OFX_MODULE_RUNNER

    return None


def mapped_columns_missing(source_csv: Path, profile: BankProfile) -> list[str]:
    try:
        with source_csv.open("r", encoding="utf-8-sig", newline="") as src:
            if profile.has_header:
                reader = csv.DictReader(src, delimiter=profile.delimiter)
                headers = set(reader.fieldnames or [])
            else:
                reader = csv.reader(src, delimiter=profile.delimiter)
                first_row = next(reader, [])
                headers = {f"col_{idx}" for idx in range(1, len(first_row) + 1)}
    except OSError as exc:
        return [f"Could not read CSV: {exc}"]

    required = [value for value in profile.field_map.values() if value]
    if profile.use_split_amounts:
        required.extend([profile.debit_col, profile.credit_col])

    return [col for col in required if col and col not in headers]


def run_conversion(
    csv2ofx_bin: str,
    source_csv: Path,
    destination_ofx: Path,
    profile: BankProfile,
    overrides: OfxMetadataOverrides | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix="openstatement_") as temp_dir:
        mapping_file = Path(temp_dir) / "mapping.py"
        write_mapping_file(mapping_file, profile)

        args = [
            "-x",
            str(mapping_file),
            "-a",
            profile.account_type,
            "-o",
            str(source_csv),
            str(destination_ofx),
        ]

        if csv2ofx_bin == CSV2OFX_MODULE_RUNNER:
            _run_csv2ofx_module(args)
        else:
            _run_csv2ofx_subprocess([csv2ofx_bin, *args])

    if overrides:
        apply_ofx_overrides(destination_ofx, overrides)


def _run_csv2ofx_subprocess(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "Unknown csv2ofx error").strip()
        raise RuntimeError(f"csv2ofx failed:\n{details}")


def _run_csv2ofx_module(args: list[str]) -> None:
    from csv2ofx.main import run as csv2ofx_run

    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            csv2ofx_run(args)
    except SystemExit as exc:
        code = exc.code
        if code in (0, None):
            return

        details = ""
        if isinstance(code, str):
            details = code.strip()

        if not details:
            details = (stderr.getvalue() or stdout.getvalue() or "Unknown csv2ofx error").strip()

        raise RuntimeError(f"csv2ofx failed:\n{details}") from None


def build_ofx_preview(csv2ofx_bin: str, source_csv: Path, profile: BankProfile) -> str:
    with tempfile.TemporaryDirectory(prefix="openstatement_preview_") as temp_dir:
        preview_ofx = Path(temp_dir) / "preview.ofx"
        run_conversion(csv2ofx_bin, source_csv, preview_ofx, profile)
        content = preview_ofx.read_text(encoding="utf-8", errors="replace")
    return format_preview(content)


def apply_ofx_overrides(destination_ofx: Path, overrides: OfxMetadataOverrides) -> None:
    text = destination_ofx.read_text(encoding="utf-8", errors="replace")
    updated = text

    if overrides.account_id and not _has_tag_value(updated, "ACCTID"):
        updated = _set_or_insert_account_id(updated, overrides.account_id)

    should_set_ledger = bool(overrides.statement_date or overrides.ending_balance)
    if should_set_ledger and (not _has_tag_value(updated, "DTASOF") or not _has_tag_value(updated, "BALAMT")):
        updated = _set_or_insert_ledger_values(
            updated,
            statement_date=overrides.statement_date,
            ending_balance=overrides.ending_balance,
        )

    if updated != text:
        destination_ofx.write_text(updated, encoding="utf-8")


def _has_tag_value(content: str, tag: str) -> bool:
    match = re.search(rf"<{tag}>([^<\r\n]+)", content, flags=re.IGNORECASE)
    return bool(match and match.group(1).strip())


def _replace_tag_in_block(block: str, tag: str, value: str) -> str:
    if not value:
        return block

    pattern = re.compile(rf"(<{tag}>)([^<\r\n]*)", flags=re.IGNORECASE)
    if pattern.search(block):
        return pattern.sub(rf"\1{value}", block, count=1)
    return block.replace(">", ">\n" + f"<{tag}>{value}", 1)


def _set_or_insert_account_id(content: str, account_id: str) -> str:
    acctid_pattern = re.compile(r"(<ACCTID>)([^<\r\n]*)", flags=re.IGNORECASE)
    if acctid_pattern.search(content):
        return acctid_pattern.sub(rf"\1{account_id}", content, count=1)

    block_pattern = re.compile(r"<(BANKACCTFROM|CCACCTFROM)>(.*?)</\1>", flags=re.IGNORECASE | re.DOTALL)
    match = block_pattern.search(content)
    if not match:
        return content

    block = match.group(0)
    new_block = block.replace(">", ">\n" + f"<ACCTID>{account_id}", 1)
    return content.replace(block, new_block, 1)


def _set_or_insert_ledger_values(content: str, statement_date: str, ending_balance: str) -> str:
    ledger_pattern = re.compile(r"<LEDGERBAL>(.*?)</LEDGERBAL>", flags=re.IGNORECASE | re.DOTALL)
    match = ledger_pattern.search(content)

    statement_value = statement_date.replace("-", "") if statement_date else ""
    balance_value = ending_balance

    if match:
        block = match.group(0)
        updated_block = block
        if statement_value and not _has_tag_value(block, "DTASOF"):
            updated_block = _replace_tag_in_block(updated_block, "DTASOF", statement_value)
        if balance_value and not _has_tag_value(block, "BALAMT"):
            updated_block = _replace_tag_in_block(updated_block, "BALAMT", balance_value)
        return content.replace(block, updated_block, 1)

    if not (statement_value or balance_value):
        return content

    pieces = ["<LEDGERBAL>"]
    if balance_value:
        pieces.append(f"<BALAMT>{balance_value}")
    if statement_value:
        pieces.append(f"<DTASOF>{statement_value}")
    pieces.append("</LEDGERBAL>")
    insert_block = "\n".join(pieces) + "\n"

    stmtrs_close = re.search(r"</STMTRS>", content, flags=re.IGNORECASE)
    if stmtrs_close:
        idx = stmtrs_close.start()
        return content[:idx] + insert_block + content[idx:]
    return content


def extract_tag(block: str, tag: str) -> str:
    match = re.search(rf"<{tag}>([^<\r\n]+)", block, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def format_ofx_date(raw: str) -> str:
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 8:
        return raw
    try:
        dt = datetime.strptime(digits[:14] if len(digits) >= 14 else digits[:8], "%Y%m%d%H%M%S" if len(digits) >= 14 else "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return raw


def format_preview(ofx_content: str, max_rows: int = 20) -> str:
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", ofx_content, flags=re.IGNORECASE | re.DOTALL)
    if not blocks:
        lines = ofx_content.splitlines()
        head = "\n".join(lines[:60])
        return "Could not parse transaction blocks. Raw OFX preview:\n\n" + head

    rows = []
    for block in blocks[:max_rows]:
        posted = format_ofx_date(extract_tag(block, "DTPOSTED"))
        amount = extract_tag(block, "TRNAMT")
        name = extract_tag(block, "NAME")
        memo = extract_tag(block, "MEMO")
        fitid = extract_tag(block, "FITID")
        rows.append(f"{posted:12} {amount:>12}  {name} | {memo} | id={fitid}")

    header = "Date         Amount        Name | Memo | id\n"
    divider = "-" * 96
    suffix = ""
    if len(blocks) > max_rows:
        suffix = f"\n\nShowing first {max_rows} of {len(blocks)} transactions."

    return f"{header}{divider}\n" + "\n".join(rows) + suffix


def write_mapping_file(mapping_file: Path, profile: BankProfile) -> None:
    fallback_account = profile.name or "Account"
    fallback_bank = profile.name or "Bank"
    amount_col = _mapping_column_name(profile.field_map.get("amount", ""), profile.has_header)
    debit_col = _mapping_column_name(profile.debit_col, profile.has_header)
    credit_col = _mapping_column_name(profile.credit_col, profile.has_header)

    lines = [
        "from operator import itemgetter",
        "",
        "def _to_float(value):",
        "    text = str(value or '').strip()",
        "    if not text:",
        "        return 0.0",
        "    negative = text.startswith('(') and text.endswith(')')",
        "    if negative:",
        "        text = text[1:-1]",
        "    cleaned = text.replace('$', '').replace(',', '').replace(' ', '')",
        "    cleaned = ''.join(ch for ch in cleaned if ch in '0123456789+-.')",
        "    if cleaned in {'', '+', '-', '.', '+.', '-.'}:",
        "        return 0.0",
        "    amount = float(cleaned)",
        "    return -amount if negative else amount",
        "",
        "def _split_amount(record):",
        f"    debit = _to_float(record.get({quote_py_string(debit_col)}, ''))",
        f"    credit = _to_float(record.get({quote_py_string(credit_col)}, ''))",
        "    return credit - abs(debit)",
        "",
        "def _amount(record):",
        f"    return _to_float(record.get({quote_py_string(amount_col)}, ''))",
        "",
        "mapping = {",
        f"    'has_header': {profile.has_header},",
        f"    'delimiter': {quote_py_string(profile.delimiter or ',')},",
        f"    'currency': {quote_py_string(profile.currency)},",
        f"    'account_id': {quote_py_string(profile.account_id or to_account_id(profile.name))},",
    ]

    date_col = _mapping_column_name(profile.field_map["date"], profile.has_header)
    lines.append(f"    'date': itemgetter({quote_py_string(date_col)}),")

    if profile.use_split_amounts:
        lines.append("    'amount': _split_amount,")
    else:
        lines.append("    'amount': _amount,")

    account_col = profile.field_map.get("account")
    if account_col:
        account_col = _mapping_column_name(account_col, profile.has_header)
        lines.append(f"    'account': itemgetter({quote_py_string(account_col)}),")
    else:
        lines.append(f"    'account': {quote_py_string(fallback_account)},")

    bank_col = profile.field_map.get("bank")
    if bank_col:
        bank_col = _mapping_column_name(bank_col, profile.has_header)
        lines.append(f"    'bank': itemgetter({quote_py_string(bank_col)}),")
    else:
        lines.append(f"    'bank': {quote_py_string(fallback_bank)},")

    for field in ["payee", "desc", "notes", "check_num", "id", "balance", "class"]:
        col = profile.field_map.get(field)
        if col:
            col = _mapping_column_name(col, profile.has_header)
            lines.append(f"    '{field}': itemgetter({quote_py_string(col)}),")

    if profile.date_format:
        lines.append(f"    'parse_fmt': {quote_py_string(profile.date_format)},")
    if profile.dayfirst:
        lines.append("    'dayfirst': True,")

    lines.extend(["}", ""])
    mapping_file.write_text("\n".join(lines), encoding="utf-8")
