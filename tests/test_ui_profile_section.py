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

    date_idx = window.mapping_combos["date"].findText(" Date ")
    amount_idx = window.mapping_combos["amount"].findText("Amount")
    window.mapping_combos["date"].setCurrentIndex(date_idx)
    window.mapping_combos["amount"].setCurrentIndex(amount_idx)

    profile = window._build_profile_from_ui()

    assert profile.delimiter == ":"
    assert profile.currency == "USD"
    assert profile.account_id == "secu_checking"
    assert profile.headers == ["date", "amount"]


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
