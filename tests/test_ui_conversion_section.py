from pathlib import Path

from openstatement.models.profile import BankProfile
from openstatement.ui.main_window import MainWindow


def _profile() -> BankProfile:
    return BankProfile(
        name="SECU",
        headers=["date", "amount"],
        delimiter=",",
        field_map={"date": "Date", "amount": "Amount"},
        debit_col="",
        credit_col="",
        use_split_amounts=False,
        date_format="",
        dayfirst=False,
        account_type="CHECKING",
        account_id="secu",
        currency="USD",
        auto_parse_filename_metadata=False,
        filename_pattern="{account_name}_{last8}_{statement_date}_{ending_balance}.csv",
    )


def test_resolve_source_csv_path_missing_warns(qapp, monkeypatch) -> None:
    window = MainWindow()
    messages = []

    monkeypatch.setattr(
        "openstatement.ui.sections.conversion.QMessageBox.warning",
        lambda *_args: messages.append("warn"),
    )

    window.csv_path_input.setText("")
    assert window._resolve_source_csv_path() is None
    assert messages


def test_prepare_conversion_inputs_success(qapp, monkeypatch, tmp_path: Path) -> None:
    window = MainWindow()
    source = tmp_path / "input.csv"
    source.write_text("Date,Amount\n", encoding="utf-8")

    monkeypatch.setattr(window, "_resolve_source_csv_path", lambda: source)
    monkeypatch.setattr(window, "_build_valid_profile", lambda: _profile())
    monkeypatch.setattr(window, "_validate_mapped_columns", lambda *_args: True)
    monkeypatch.setattr(window, "_find_csv2ofx_binary", lambda: "csv2ofx")

    result = window._prepare_conversion_inputs()
    assert result is not None
    binary, path, profile = result
    assert binary == "csv2ofx"
    assert path == source
    assert profile.name == "SECU"
