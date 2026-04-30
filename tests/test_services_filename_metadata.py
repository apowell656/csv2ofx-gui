from pathlib import Path

from openstatement.services.filename_metadata import (
    DEFAULT_FILENAME_PATTERN,
    normalize_balance,
    normalize_statement_date,
    parse_filename_metadata,
)


def test_parse_filename_metadata_default_pattern_success() -> None:
    result = parse_filename_metadata(
        Path("Checking_31676003_2026-04-24_1520.44.csv"),
        DEFAULT_FILENAME_PATTERN,
    )
    assert result.metadata is not None
    assert result.metadata.account_id == "31676003"
    assert result.metadata.statement_date == "2026-04-24"
    assert result.metadata.ending_balance == "1520.44"


def test_parse_filename_metadata_handles_negative_balance() -> None:
    result = parse_filename_metadata(
        Path("Checking_31676003_2026-04-24_-120.55.csv"),
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
    assert normalize_statement_date("04/24/2026") == ""
    assert normalize_balance("1,520.4") == "1520.40"
    assert normalize_balance("-120.555") == "-120.56"
    assert normalize_balance("abc") == ""
