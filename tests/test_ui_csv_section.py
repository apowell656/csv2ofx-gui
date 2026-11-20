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
    window.profiles = {"ACME": _profile("ACME")}

    window._detect_saved_profile(["Other", "Headers"])
    assert "No matching saved profile" in window.detected_label.text()


def test_detect_saved_profile_yes_applies_profile(qapp, monkeypatch) -> None:
    window = MainWindow()
    p = _profile("ACME")
    window.profiles = {"ACME": p}

    monkeypatch.setattr(
        "openstatement.ui.sections.csv.QMessageBox.question",
        lambda *_args, **_kwargs: 16384,  # QMessageBox.Yes
    )

    window._set_headers(["Date", "Amount"])
    window._detect_saved_profile(["Date", "Amount"])

    assert "Found matching profile" in window.detected_label.text()
    assert window.bank_name_input.text() == "ACME"


def test_refresh_filename_metadata_sets_detected_values(qapp, monkeypatch) -> None:
    window = MainWindow()
    window.auto_parse_filename_check.setChecked(True)

    monkeypatch.setattr(
        "openstatement.ui.sections.csv.parse_filename_metadata",
        lambda *_args, **_kwargs: ParseResult(
            FilenameMetadata(
                account_name="Checking",
                account_id="12345678",
                statement_date="2026-04-24",
                ending_balance="1520.44",
            )
        ),
    )

    window._refresh_filename_metadata(Path("Checking_12345678_2026-04-24_1520.44.csv"))
    assert "Detected from filename" in window.filename_metadata_label.text()
    assert window.filename_account_input.text() == "12345678"
    assert window.bank_name_input.text() == "Checking"
    assert window.account_id_input.text() == "12345678"


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


def test_load_german_csv_detects_delimiter_date_and_decimal(qapp, tmp_path: Path) -> None:
    source = tmp_path / "konto.csv"
    source.write_text(
        "Buchungstag;Betrag;Empfaenger;Saldo\n"
        "13.11.2026;-12,50;Baeckerei;1.222,06\n"
        "14.11.2026;1.234,56;Gehalt;2.456,62\n",
        encoding="utf-8",
    )
    window = MainWindow()
    window.profiles = {}
    window.csv_path_input.setText(str(source))
    window.load_csv_headers(str(source))

    assert window.delimiter_input.text() == ";"
    assert window.current_headers == ["Buchungstag", "Betrag", "Empfaenger", "Saldo"]
    assert window.mapping_combos["date"].currentText() == "Buchungstag"
    assert window.mapping_combos["amount"].currentText() == "Betrag"
    assert window.date_format_input.text() == "%d.%m.%Y"
    assert window.decimal_separator_combo.currentData() == ","

    profile = window._build_profile_from_ui()
    assert profile.decimal_separator == ","


def test_load_us_csv_keeps_us_defaults(qapp, tmp_path: Path) -> None:
    source = tmp_path / "us.csv"
    source.write_text("Date,Amount\n11/13/2026,-12.50\n11/14/2026,\"1,234.56\"\n", encoding="utf-8")
    window = MainWindow()
    window.profiles = {}
    window.load_csv_headers(str(source))

    assert window.delimiter_input.text() == ","
    assert window.date_format_input.text() == "%m/%d/%Y"
    assert window.decimal_separator_combo.currentData() == "."


def test_load_csv_detects_currency_from_currency_column(qapp, tmp_path: Path) -> None:
    source = tmp_path / "konto.csv"
    source.write_text(
        "Buchungstag;Betrag;Waehrung\n13.11.2026;-12,50;EUR\n14.11.2026;100,00;EUR\n",
        encoding="utf-8",
    )
    window = MainWindow()
    window.profiles = {}
    window.load_csv_headers(str(source))

    assert window.currency_input.text() == "EUR"


def test_load_csv_ambiguous_dates_use_dayfirst_with_decimal_comma(qapp, tmp_path: Path) -> None:
    source = tmp_path / "banco.csv"
    source.write_text(
        "Date;Amount\n03/04/2026;-12,50 €\n05/06/2026;1.234,56 €\n",
        encoding="utf-8",
    )
    window = MainWindow()
    window.profiles = {}
    window.load_csv_headers(str(source))

    assert window.decimal_separator_combo.currentData() == ","
    assert window.date_format_input.text() == "%d/%m/%Y"
    assert window.currency_input.text() == "EUR"


def test_load_csv_with_localized_month_names(qapp, tmp_path: Path) -> None:
    source = tmp_path / "releve.csv"
    source.write_text(
        "Date;Amount\n13 oct. 2026;-12,50\n14 nov. 2026;1 234,56\n",
        encoding="utf-8",
    )
    window = MainWindow()
    window.profiles = {}
    window.load_csv_headers(str(source))

    assert window.date_format_input.text() == "%d %b %Y"
    assert window.decimal_separator_combo.currentData() == ","


def _account_profile(name: str, account_id: str, **overrides) -> BankProfile:
    profile = _profile(name)
    profile.headers = ["date", "amount", "payee"]
    profile.account_id = account_id
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


class _DialogSpy:
    def __init__(self, monkeypatch, choose: str | None = None, confirm: bool = True) -> None:
        self.questions: list[str] = []
        self.choosers: list[list[str]] = []
        self._choose = choose
        self._confirm = confirm
        monkeypatch.setattr("openstatement.ui.sections.csv.QMessageBox.question", self.question)
        monkeypatch.setattr("openstatement.ui.sections.csv.QInputDialog.getItem", self.get_item)

    def question(self, _parent, _title, text, *_args, **_kwargs):
        from PySide6.QtWidgets import QMessageBox

        self.questions.append(text)
        return QMessageBox.Yes if self._confirm else QMessageBox.No

    def get_item(self, _parent, _title, _label, items, *_args, **_kwargs):
        self.choosers.append(list(items))
        if self._choose is None:
            return "", False
        return next(item for item in items if item.startswith(self._choose)), True

    @property
    def total(self) -> int:
        return len(self.questions) + len(self.choosers)


def _load(window: MainWindow, path: Path) -> None:
    window.csv_path_input.setText(str(path))
    window.load_csv_headers(str(path))


def test_two_accounts_same_bank_lets_user_choose_once(qapp, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "export.csv"
    source.write_text("Date,Amount,Payee\n11/01/2026,1.00,X\n", encoding="utf-8")
    spy = _DialogSpy(monkeypatch, choose="Bank Savings")
    window = MainWindow()
    window.profiles = {
        "Bank Checking": _account_profile("Bank Checking", "1111"),
        "Bank Savings": _account_profile("Bank Savings", "2222"),
    }
    window._refresh_profile_combo()

    _load(window, source)

    assert spy.questions == []
    assert len(spy.choosers) == 1
    assert spy.choosers[0][0].startswith("Bank Checking") and "1111" in spy.choosers[0][0]
    assert "2222" in spy.choosers[0][1]
    assert window.bank_name_input.text() == "Bank Savings"
    assert window.account_id_input.text() == "2222"
    assert window.profile_combo.currentText() == "Bank Savings"
    assert "2 matching profiles" in window.detected_label.text()


def test_choosing_nothing_applies_no_profile(qapp, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "export.csv"
    source.write_text("Date,Amount,Payee\n11/01/2026,1.00,X\n", encoding="utf-8")
    spy = _DialogSpy(monkeypatch, choose=None)
    window = MainWindow()
    window.profiles = {
        "Bank Checking": _account_profile("Bank Checking", "1111"),
        "Bank Savings": _account_profile("Bank Savings", "2222"),
    }

    _load(window, source)

    assert spy.total == 1
    assert window.bank_name_input.text() == ""


def test_filename_account_id_picks_single_profile_with_one_prompt(qapp, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "Savings_2222_2026-11-01_100.00.csv"
    source.write_text("Date,Amount,Payee\n11/01/2026,1.00,X\n", encoding="utf-8")
    spy = _DialogSpy(monkeypatch)
    window = MainWindow()
    window.auto_parse_filename_check.setChecked(True)
    window.profiles = {
        "Bank Checking": _account_profile("Bank Checking", "1111", auto_parse_filename_metadata=True),
        "Bank Savings": _account_profile("Bank Savings", "2222", auto_parse_filename_metadata=True),
    }

    _load(window, source)

    assert spy.choosers == []
    assert len(spy.questions) == 1 and "Bank Savings" in spy.questions[0]
    assert window.bank_name_input.text() == "Bank Savings"
    # Statement metadata from the filename is still filled in.
    assert window.filename_balance_input.text() == "100.00"


def test_applying_profile_that_changes_header_setting_prompts_once_and_keeps_values(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "Checking_1111_2026-11-01_100.00.csv"
    source.write_text("13.11.2026;-12,50;Shop\n", encoding="utf-8")
    spy = _DialogSpy(monkeypatch)
    window = MainWindow()
    window.auto_parse_filename_check.setChecked(True)
    headerless = _account_profile(
        "My Bank",
        "1111",
        has_header=False,
        delimiter=";",
        field_map={"date": "col_1", "amount": "col_2", "payee": "col_3"},
        date_format="%d.%m.%Y",
        decimal_separator=",",
        currency="EUR",
        auto_parse_filename_metadata=True,
    )
    window.profiles = {"My Bank": headerless}

    _load(window, source)

    assert spy.total == 1
    assert window.csv_has_header_check.isChecked() is False
    assert window.current_headers == ["col_1", "col_2", "col_3"]
    assert window.mapping_combos["date"].currentData() == "col_1"
    assert window.mapping_combos["amount"].currentData() == "col_2"
    assert window.date_format_input.text() == "%d.%m.%Y"
    assert window.decimal_separator_combo.currentData() == ","
    assert window.currency_input.text() == "EUR"
    assert window.bank_name_input.text() == "My Bank"


def test_toggling_header_checkbox_does_not_prompt_again(qapp, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "export.csv"
    source.write_text("Date,Amount,Payee\n11/01/2026,1.00,X\n", encoding="utf-8")
    spy = _DialogSpy(monkeypatch, confirm=False)
    window = MainWindow()
    window.profiles = {"Bank Checking": _account_profile("Bank Checking", "1111")}

    _load(window, source)
    window.csv_has_header_check.setChecked(False)
    window.csv_has_header_check.setChecked(True)

    assert spy.total == 1


def test_selecting_profile_from_dropdown_never_prompts(qapp, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "export.csv"
    source.write_text("Date,Amount,Payee\n11/01/2026,1.00,X\n", encoding="utf-8")
    spy = _DialogSpy(monkeypatch, choose=None)
    window = MainWindow()
    window.profiles = {
        "Bank Checking": _account_profile("Bank Checking", "1111"),
        "Bank Savings": _account_profile("Bank Savings", "2222", has_header=False),
    }
    window._refresh_profile_combo()
    _load(window, source)
    assert spy.total == 1

    window.profile_combo.setCurrentIndex(window.profile_combo.findText("Bank Savings"))

    assert spy.total == 1
    assert window.bank_name_input.text() == "Bank Savings"
    assert window.csv_has_header_check.isChecked() is False


def test_account_number_column_picks_the_right_same_bank_account(qapp, monkeypatch, tmp_path: Path) -> None:
    headers = ["date", "account", "account number", "description", "credit", "debit"]
    everyday = _account_profile("Everyday", "12345678", headers=headers)
    vacation = _account_profile("Vacation Fund", "87654321", headers=headers)
    source = tmp_path / "export.csv"
    source.write_text(
        "Date,Account,Account Number,Description,Credit,Debit\n11/01/2026,Share,XXXX4321,Deposit,10.00,\n",
        encoding="utf-8",
    )
    spy = _DialogSpy(monkeypatch)
    window = MainWindow()
    window.profiles = {"Everyday": everyday, "Vacation Fund": vacation}

    _load(window, source)

    assert spy.choosers == []
    assert len(spy.questions) == 1 and "Vacation Fund" in spy.questions[0]
    assert "account number in CSV" in spy.questions[0]
    assert window.bank_name_input.text() == "Vacation Fund"


def test_detection_ignores_skipped_preamble_and_footer_rows(qapp, tmp_path: Path) -> None:
    source = tmp_path / "umsaetze.csv"
    source.write_text(
        "Kontoauszug ACME Bank\n"
        "Zeitraum: 01.11.2026 - 14.11.2026\n"
        "Buchungstag;Betrag;Empfaenger\n"
        "13.11.2026;-12,50;Baeckerei\n"
        "14.11.2026;1.234,56;Gehalt\n"
        "Summe;1.222,06;\n",
        encoding="utf-8",
    )
    window = MainWindow()
    window.profiles = {}
    window.trailing_rows_spin.setValue(1)
    window.leading_rows_spin.blockSignals(True)
    window.leading_rows_spin.setValue(2)
    window.leading_rows_spin.blockSignals(False)

    window.load_csv_headers(str(source))

    assert window.delimiter_input.text() == ";"
    assert window.current_headers == ["Buchungstag", "Betrag", "Empfaenger"]
    assert window.date_format_input.text() == "%d.%m.%Y"
    assert window.decimal_separator_combo.currentData() == ","


def test_applying_profile_with_leading_rows_prompts_once(qapp, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "Checking_12345678_2026-11-01_100.00.csv"
    source.write_text(
        "ACME Bank export\nDate,Amount,Payee\n11/01/2026,1.00,X\n",
        encoding="utf-8",
    )
    spy = _DialogSpy(monkeypatch)
    window = MainWindow()
    window.auto_parse_filename_check.setChecked(True)
    profile = _account_profile(
        "Everyday",
        "12345678",
        leading_rows_to_skip=1,
        trailing_rows_to_skip=0,
        auto_parse_filename_metadata=True,
        field_map={"date": "Date", "amount": "Amount", "payee": "Payee"},
    )
    window.profiles = {"Everyday": profile}

    _load(window, source)

    assert spy.total == 1
    assert window.leading_rows_spin.value() == 1
    assert window.current_headers == ["Date", "Amount", "Payee"]
    assert window.mapping_combos["payee"].currentText() == "Payee"
    assert window.bank_name_input.text() == "Everyday"


def test_profile_matching_reads_file_with_each_profiles_row_skipping(qapp, monkeypatch, tmp_path: Path) -> None:
    """A fresh form skips no rows, but the bank's export has a preamble: match as the profile would read it."""
    headers = ["date", "account number", "description", "credit", "debit"]
    common = dict(headers=headers, leading_rows_to_skip=2, trailing_rows_to_skip=1)
    everyday = _account_profile("Everyday", "12345678", **common)
    vacation = _account_profile("Vacation Fund", "87654321", **common)
    source = tmp_path / "export.csv"
    source.write_text(
        "Account Activity Export\n"
        "Generated 11/19/2026\n"
        "Date,Account Number,Description,Credit,Debit\n"
        "11/01/2026,XXXX4321,Deposit,10.00,\n"
        "Total,,,10.00,\n",
        encoding="utf-8",
    )
    spy = _DialogSpy(monkeypatch)
    window = MainWindow()
    window.profiles = {"Everyday": everyday, "Vacation Fund": vacation}
    assert window.leading_rows_spin.value() == 0

    _load(window, source)

    assert spy.total == 1
    assert "Vacation Fund" in spy.questions[0]
    assert "account number in CSV" in spy.questions[0]
    assert window.bank_name_input.text() == "Vacation Fund"
    assert window.leading_rows_spin.value() == 2
    assert window.trailing_rows_spin.value() == 1
    assert window.current_headers == ["Date", "Account Number", "Description", "Credit", "Debit"]
