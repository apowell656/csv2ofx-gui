from pathlib import Path

from openstatement.models.profile import BankProfile
from openstatement.services.filename_metadata import FilenameMetadata, ParseResult
from openstatement.ui.main_window import MainWindow


def _profile(name: str) -> BankProfile:
    return BankProfile(
        name=name,
        headers=["date", "amount"],
        delimiter=",",
        field_map={"date": "Date", "amount": "Amount"},
        debit_col="",
        credit_col="",
        use_split_amounts=False,
        date_format="",
        dayfirst=False,
        account_type="CHECKING",
        account_id="acc",
        currency="USD",
        auto_parse_filename_metadata=False,
        filename_pattern="{account_name}_{last8}_{statement_date}_{ending_balance}.csv",
    )


def test_guess_default_fields_sets_expected_combos(qapp) -> None:
    window = MainWindow()
    headers = ["Transaction Date", "Credit Amount", "Description", "Debit Amount"]
    window._set_headers(headers)

    window._guess_default_fields(headers)

    assert window.mapping_combos["date"].currentText() == "Transaction Date"
    assert window.mapping_combos["payee"].currentText() == "Description"
    assert window.credit_col.currentText() == "Credit Amount"
    assert window.debit_col.currentText() == "Debit Amount"


def test_detect_saved_profile_no_match_sets_label(qapp) -> None:
    window = MainWindow()
    window.profiles = {"SECU": _profile("SECU")}

    window._detect_saved_profile(["Other", "Headers"])
    assert "No matching saved profile" in window.detected_label.text()


def test_detect_saved_profile_yes_applies_profile(qapp, monkeypatch) -> None:
    window = MainWindow()
    p = _profile("SECU")
    window.profiles = {"SECU": p}

    monkeypatch.setattr(
        "openstatement.ui.sections.csv.QMessageBox.question",
        lambda *_args, **_kwargs: 16384,  # QMessageBox.Yes
    )

    window._set_headers(["Date", "Amount"])
    window._detect_saved_profile(["Date", "Amount"])

    assert "Found matching profile" in window.detected_label.text()
    assert window.bank_name_input.text() == "SECU"


def test_refresh_filename_metadata_sets_detected_values(qapp, monkeypatch) -> None:
    window = MainWindow()
    window.auto_parse_filename_check.setChecked(True)

    monkeypatch.setattr(
        "openstatement.ui.sections.csv.parse_filename_metadata",
        lambda *_args, **_kwargs: ParseResult(
            FilenameMetadata(
                account_name="Checking",
                account_id="31676003",
                statement_date="2026-04-24",
                ending_balance="1520.44",
            )
        ),
    )

    window._refresh_filename_metadata(Path("Checking_31676003_2026-04-24_1520.44.csv"))
    assert "Detected from filename" in window.filename_metadata_label.text()
    assert window.filename_account_input.text() == "31676003"
    assert window.bank_name_input.text() == "Checking"
    assert window.account_id_input.text() == "31676003"
