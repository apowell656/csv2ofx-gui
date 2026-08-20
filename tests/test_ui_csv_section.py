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
        has_header=True,
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


def test_load_csv_headers_without_header_generates_column_names(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    csv_path = tmp_path / "no_header.csv"
    csv_path.write_text("2026-01-01,10.25,Store\n", encoding="utf-8")
    window.csv_has_header_check.setChecked(False)

    window.load_csv_headers(str(csv_path))

    assert window.current_headers == ["col_1", "col_2", "col_3"]
    assert window.mapping_combos["date"].itemText(1).startswith("col_1 (2026-01-01)")
    assert window.mapping_combos["date"].itemData(1) == "col_1"


def test_load_csv_headers_supports_tab_delimiter_token(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    csv_path = tmp_path / "tab_file.csv"
    csv_path.write_text("Date\tAmount\tDesc\n2026-01-01\t10\tStore\n", encoding="utf-8")
    window.delimiter_input.setText(r"\t")

    window.load_csv_headers(str(csv_path))

    assert window.current_headers == ["Date", "Amount", "Desc"]


def test_load_csv_headers_respects_leading_rows_to_skip_with_header(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    csv_path = tmp_path / "with_metadata.csv"
    csv_path.write_text(
        "Bank Statement\nAccount 123\nDate,Description,Amount\n2026-01-01,Coffee,-5.00\n",
        encoding="utf-8",
    )
    window.leading_rows_spin.setValue(2)

    window.load_csv_headers(str(csv_path))

    assert window.current_headers == ["Date", "Description", "Amount"]


def test_load_csv_headers_respects_leading_rows_to_skip_without_header(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    csv_path = tmp_path / "with_metadata_no_header.csv"
    csv_path.write_text(
        "Bank Statement\nAccount 123\n2026-01-01,Coffee,-5.00\n",
        encoding="utf-8",
    )
    window.csv_has_header_check.setChecked(False)
    window.leading_rows_spin.setValue(2)

    window.load_csv_headers(str(csv_path))

    assert window.current_headers == ["col_1", "col_2", "col_3"]
    assert window.mapping_combos["date"].itemText(1).startswith("col_1 (2026-01-01)")


def test_load_csv_headers_leading_rows_exceeding_file_shows_clean_error(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    window = MainWindow()
    csv_path = tmp_path / "short.csv"
    csv_path.write_text("Date,Amount\n2026-01-01,10\n", encoding="utf-8")
    window.leading_rows_spin.setValue(10)

    messages = []
    monkeypatch.setattr(
        "openstatement.ui.sections.csv.QMessageBox.critical",
        lambda *_args: messages.append("error"),
    )

    window.load_csv_headers(str(csv_path))

    assert messages
    assert window.status_label.text() == "CSV load failed"


def test_changing_leading_rows_spin_reloads_currently_selected_csv(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    csv_path = tmp_path / "with_metadata.csv"
    csv_path.write_text(
        "Bank Statement\nDate,Amount\n2026-01-01,10\n",
        encoding="utf-8",
    )
    window.csv_path_input.setText(str(csv_path))
    window.load_csv_headers(str(csv_path))
    assert window.current_headers == ["Bank Statement"]

    window.leading_rows_spin.setValue(1)

    assert window.current_headers == ["Date", "Amount"]
