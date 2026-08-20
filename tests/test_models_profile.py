import json
from pathlib import Path

from openstatement.models.profile import BankProfile, ProfileStore, normalize_header, to_account_id


def test_normalize_header() -> None:
    assert normalize_header("  Transaction Date ") == "transaction date"


def test_to_account_id() -> None:
    assert to_account_id("SECU Checking") == "secu_checking"
    assert to_account_id("!!!") == "default_account"


def test_bank_profile_from_dict_defaults() -> None:
    profile = BankProfile.from_dict({"name": "Test"})
    assert profile.name == "Test"
    assert profile.delimiter == ","
    assert profile.account_type == "CHECKING"
    assert profile.currency == "USD"
    assert profile.auto_parse_filename_metadata is False
    assert profile.has_header is True
    assert profile.leading_rows_to_skip == 0
    assert profile.trailing_rows_to_skip == 0


def test_bank_profile_from_dict_missing_row_skip_fields_defaults_to_zero() -> None:
    raw = {
        "name": "Old Profile",
        "headers": ["date", "amount"],
        "delimiter": ",",
        "field_map": {"date": "Date", "amount": "Amount"},
        "debit_col": "",
        "credit_col": "",
        "use_split_amounts": False,
        "date_format": "",
        "dayfirst": False,
        "account_type": "CHECKING",
        "account_id": "old",
        "currency": "USD",
        "auto_parse_filename_metadata": False,
        "filename_pattern": "{account_name}_{last8}_{statement_date}_{ending_balance}.csv",
        "has_header": True,
    }
    profile = BankProfile.from_dict(raw)
    assert profile.leading_rows_to_skip == 0
    assert profile.trailing_rows_to_skip == 0


def test_bank_profile_from_dict_negative_row_skip_values_clamped_to_zero() -> None:
    profile = BankProfile.from_dict(
        {"name": "Test", "leading_rows_to_skip": -3, "trailing_rows_to_skip": -1}
    )
    assert profile.leading_rows_to_skip == 0
    assert profile.trailing_rows_to_skip == 0


def test_profile_store_load_missing_returns_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "openstatement.models.profile.QStandardPaths.writableLocation",
        lambda *_args: str(tmp_path),
    )
    store = ProfileStore()
    assert store.load() == {}


def test_profile_store_load_invalid_json_returns_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "openstatement.models.profile.QStandardPaths.writableLocation",
        lambda *_args: str(tmp_path),
    )
    store = ProfileStore()
    store.path.write_text("{not json", encoding="utf-8")
    assert store.load() == {}


def test_profile_store_save_and_load_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "openstatement.models.profile.QStandardPaths.writableLocation",
        lambda *_args: str(tmp_path),
    )
    store = ProfileStore()
    profile = BankProfile(
        name="SECU",
        headers=["date", "amount"],
        delimiter=",",
        field_map={"date": "Date", "amount": "Amount"},
        debit_col="",
        credit_col="",
        use_split_amounts=False,
        date_format="%m/%d/%Y",
        dayfirst=False,
        account_type="CHECKING",
        account_id="secu",
        currency="USD",
        auto_parse_filename_metadata=False,
        filename_pattern="{account_name}_{last8}_{statement_date}_{ending_balance}.csv",
        has_header=True,
        leading_rows_to_skip=3,
        trailing_rows_to_skip=2,
    )

    store.save({"SECU": profile})

    saved_raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert "SECU" in saved_raw
    assert saved_raw["SECU"]["currency"] == "USD"
    assert saved_raw["SECU"]["leading_rows_to_skip"] == 3
    assert saved_raw["SECU"]["trailing_rows_to_skip"] == 2

    loaded = store.load()
    assert loaded["SECU"].field_map["date"] == "Date"
    assert loaded["SECU"].leading_rows_to_skip == 3
    assert loaded["SECU"].trailing_rows_to_skip == 2
