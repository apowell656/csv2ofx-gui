from pathlib import Path

from openstatement.models.profile import BankProfile
from openstatement.ui.main_window import MainWindow


def test_validate_required_fields_missing_date_shows_warning(qapp, monkeypatch) -> None:
    window = MainWindow()
    messages = []

    monkeypatch.setattr(
        "openstatement.ui.sections.profile.QMessageBox.warning",
        lambda *_args: messages.append("warn"),
    )

    profile = BankProfile(
        name="X",
        headers=[],
        delimiter=",",
        field_map={},
        debit_col="",
        credit_col="",
        use_split_amounts=False,
        date_format="",
        dayfirst=False,
        account_type="CHECKING",
        account_id="",
        currency="USD",
        auto_parse_filename_metadata=False,
        filename_pattern="{account_name}_{last8}_{statement_date}_{ending_balance}.csv",
        has_header=True,
    )

    assert window._validate_required_fields(profile) is False
    assert messages


def test_build_profile_from_ui_applies_normalization(qapp) -> None:
    window = MainWindow()
    window._set_headers([" Date ", "Amount"])

    window.bank_name_input.setText("SECU Checking")
    window.delimiter_input.setText("::")
    window.currency_input.setText("usd")
    window.account_id_input.setText("")
    window.auto_parse_filename_check.setChecked(True)
    window.csv_has_header_check.setChecked(False)
    window.filename_pattern_input.setText("{account_name}_{last8}_{statement_date}_{ending_balance}.csv")

    date_idx = window.mapping_combos["date"].findText(" Date ")
    amount_idx = window.mapping_combos["amount"].findText("Amount")
    window.mapping_combos["date"].setCurrentIndex(date_idx)
    window.mapping_combos["amount"].setCurrentIndex(amount_idx)

    profile = window._build_profile_from_ui()

    assert profile.delimiter == ":"
    assert profile.currency == "USD"
    assert profile.account_id == "secu_checking"
    assert profile.headers == ["date", "amount"]
    assert profile.auto_parse_filename_metadata is True
    assert profile.has_header is False


def test_build_profile_from_ui_accepts_tab_delimiter_token(qapp) -> None:
    window = MainWindow()
    window._set_headers(["Date", "Amount"])
    window.delimiter_input.setText(r"\t")

    date_idx = window.mapping_combos["date"].findText("Date")
    amount_idx = window.mapping_combos["amount"].findText("Amount")
    window.mapping_combos["date"].setCurrentIndex(date_idx)
    window.mapping_combos["amount"].setCurrentIndex(amount_idx)

    profile = window._build_profile_from_ui()
    assert profile.delimiter == "\t"


def test_save_profile_requires_loaded_csv(qapp, monkeypatch) -> None:
    window = MainWindow()
    messages = []

    monkeypatch.setattr(
        "openstatement.ui.sections.profile.QMessageBox.warning",
        lambda *_args: messages.append("warn"),
    )

    window.current_headers = []
    window.save_profile()

    assert messages
