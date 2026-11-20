from pathlib import Path

import pytest

from openstatement.services.filename_metadata import (
    DEFAULT_FILENAME_PATTERN,
    account_ids_match,
    normalize_balance,
    normalize_statement_date,
    parse_filename_metadata,
)


def test_parse_filename_metadata_default_pattern_success() -> None:
    result = parse_filename_metadata(
        Path("Checking_12345678_2026-04-24_1520.44.csv"),
        DEFAULT_FILENAME_PATTERN,
    )
    assert result.metadata is not None
    assert result.metadata.account_id == "12345678"
    assert result.metadata.statement_date == "2026-04-24"
    assert result.metadata.ending_balance == "1520.44"


def test_parse_filename_metadata_handles_negative_balance() -> None:
    result = parse_filename_metadata(
        Path("Checking_12345678_2026-04-24_-120.55.csv"),
        DEFAULT_FILENAME_PATTERN,
    )
    assert result.metadata is not None
    assert result.metadata.ending_balance == "-120.55"


def test_parse_filename_metadata_failure_is_nonfatal() -> None:
    result = parse_filename_metadata(
        Path("bad_name.csv"),
        DEFAULT_FILENAME_PATTERN,
    )
    assert result.metadata is None
    assert result.error


def test_normalizers() -> None:
    assert normalize_statement_date("2026-04-24") == "2026-04-24"
    assert normalize_statement_date("04/24/2026") == "2026-04-24"
    assert normalize_statement_date("24.04.2026") == "2026-04-24"
    assert normalize_statement_date("not-a-date") == ""
    assert normalize_balance("1,520.4") == "1520.40"
    assert normalize_balance("-120.555") == "-120.56"
    assert normalize_balance("abc") == ""


def test_normalize_balance_comma_decimal() -> None:
    assert normalize_balance("1.520,40", ",") == "1520.40"
    assert normalize_balance("-120,555", ",") == "-120.56"



@pytest.mark.parametrize(
    ("filename", "account_name", "account_id", "balance"),
    [
        ("Vacation Fund_87654321_2026-11-01_1520.44.csv", "Vacation Fund", "87654321", "1520.44"),
        ("Vacation_Fund_87654321_2026-11-01_1520.44.csv", "Vacation_Fund", "87654321", "1520.44"),
        ("Vacation-Fund_87654321_2026-11-01_1,520.44.csv", "Vacation-Fund", "87654321", "1520.44"),
    ],
)
def test_parse_filename_metadata_multi_word_names_and_grouped_balance(
    filename: str, account_name: str, account_id: str, balance: str
) -> None:
    result = parse_filename_metadata(Path(filename), DEFAULT_FILENAME_PATTERN)
    assert result.metadata is not None
    assert result.metadata.account_name == account_name
    assert result.metadata.account_id == account_id
    assert result.metadata.ending_balance == balance


@pytest.mark.parametrize(
    ("candidate", "account_id", "expected"),
    [
        ("87654321", "87654321", True),
        ("XXXX4321", "87654321", True),
        ("****4321", "87654321", True),
        ("4321", "87654321", True),
        ("87654321", "4321", True),
        ("DE89 3704 0044 0532 0130 00", "DE89370400440532013000", True),
        ("XXXX4321", "12345678", False),
        ("321", "87654321", False),  # too few digits to trust
        ("", "87654321", False),
        ("acme_checking", "ACME-Checking", True),
        ("acme_checking", "acme_savings", False),
    ],
)
def test_account_ids_match(candidate: str, account_id: str, expected: bool) -> None:
    assert account_ids_match(candidate, account_id) is expected
