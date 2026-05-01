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
    )

    store.save({"SECU": profile})

    saved_raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert "SECU" in saved_raw
    assert saved_raw["SECU"]["currency"] == "USD"

    loaded = store.load()
    assert loaded["SECU"].field_map["date"] == "Date"
