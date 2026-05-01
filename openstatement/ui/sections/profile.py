from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ...models.profile import BankProfile, DEFAULT_FILENAME_PATTERN, normalize_filename_pattern, normalize_header, to_account_id


class ProfileSectionMixin:
    def _refresh_profile_combo(self) -> None:
        existing = self.profile_combo.currentText()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("")
        for name in sorted(self.profiles.keys()):
            self.profile_combo.addItem(name)
        if existing:
            idx = self.profile_combo.findText(existing, Qt.MatchFixedString)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        self.profile_combo.blockSignals(False)

    def _apply_selected_profile(self) -> None:
        name = self.profile_combo.currentText().strip()
        if not name:
            return
        profile = self.profiles.get(name)
        if not profile:
            return
        self._load_profile_to_ui(profile)

    def _load_profile_to_ui(self, profile: BankProfile) -> None:
        self.bank_name_input.setText(profile.name)
        self.delimiter_input.setText(self._delimiter_for_input(profile.delimiter))
        self.date_format_input.setText(profile.date_format)
        self.dayfirst_check.setChecked(profile.dayfirst)
        self.account_id_input.setText(profile.account_id)
        self.currency_input.setText(profile.currency)
        self.auto_parse_filename_check.setChecked(profile.auto_parse_filename_metadata)
        self.filename_pattern_input.setText(normalize_filename_pattern(profile.filename_pattern))
        self.csv_has_header_check.setChecked(profile.has_header)

        type_idx = self.account_type_combo.findText(profile.account_type, Qt.MatchFixedString)
        if type_idx >= 0:
            self.account_type_combo.setCurrentIndex(type_idx)

        for field, combo in self.mapping_combos.items():
            self._set_combo_value(combo, profile.field_map.get(field, ""))

        self.use_split_amounts.setChecked(profile.use_split_amounts)
        self._set_combo_value(self.debit_col, profile.debit_col)
        self._set_combo_value(self.credit_col, profile.credit_col)

    def _build_profile_from_ui(self) -> BankProfile:
        name = self.bank_name_input.text().strip()
        field_map = {
            field: str(combo.currentData() or combo.currentText()).strip()
            for field, combo in self.mapping_combos.items()
            if str(combo.currentData() or combo.currentText()).strip()
        }
        return BankProfile(
            name=name,
            headers=[normalize_header(h) for h in self.current_headers],
            delimiter=self._effective_delimiter(self.delimiter_input.text()),
            field_map=field_map,
            debit_col=str(self.debit_col.currentData() or self.debit_col.currentText()).strip(),
            credit_col=str(self.credit_col.currentData() or self.credit_col.currentText()).strip(),
            use_split_amounts=self.use_split_amounts.isChecked(),
            date_format=self.date_format_input.text().strip(),
            dayfirst=self.dayfirst_check.isChecked(),
            account_type=self.account_type_combo.currentText(),
            account_id=self.account_id_input.text().strip() or to_account_id(name),
            currency=(self.currency_input.text().strip() or "USD").upper(),
            auto_parse_filename_metadata=self.auto_parse_filename_check.isChecked(),
            filename_pattern=(
                normalize_filename_pattern(self.filename_pattern_input.text())
                or DEFAULT_FILENAME_PATTERN
            ),
            has_header=self.csv_has_header_check.isChecked(),
        )

    def save_profile(self) -> None:
        if not self.current_headers:
            QMessageBox.warning(self, "Missing CSV", "Load a CSV file before saving a profile.")
            return

        name = self.bank_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Profile Name", "Enter a profile name (for example your bank name).")
            return

        profile = self._build_profile_from_ui()

        if not self._validate_required_fields(profile):
            return

        self.profiles[name] = profile
        self.profile_store.save(self.profiles)
        self._refresh_profile_combo()
        idx = self.profile_combo.findText(name, Qt.MatchFixedString)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

        QMessageBox.information(self, "Saved", f"Profile '{name}' saved.")

    def manage_profiles(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Profiles")
        dialog.resize(860, 500)

        layout = QVBoxLayout(dialog)

        content = QHBoxLayout()
        content.setSpacing(12)

        profile_list = QListWidget()
        profile_list.addItems(sorted(self.profiles.keys()))
        profile_list.setMinimumWidth(240)

        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlaceholderText("Select a saved profile to review its details.")

        content.addWidget(profile_list, 0)
        content.addWidget(details, 1)
        layout.addLayout(content)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        load_btn = QPushButton("Load Selected")
        delete_btn = QPushButton("Delete Selected")
        close_btn = QPushButton("Close")

        button_row.addStretch(1)
        button_row.addWidget(load_btn)
        button_row.addWidget(delete_btn)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        def selected_profile() -> BankProfile | None:
            item = profile_list.currentItem()
            if item is None:
                return None
            return self.profiles.get(item.text())

        def refresh_details() -> None:
            profile = selected_profile()
            if profile is None:
                details.clear()
                return
            details.setPlainText(self._format_profile_summary(profile))

        def load_selected() -> None:
            item = profile_list.currentItem()
            if item is None:
                QMessageBox.information(dialog, "Manage Profiles", "Select a saved profile first.")
                return
            profile = self.profiles.get(item.text())
            if profile is None:
                return
            self._load_profile_to_ui(profile)
            idx = self.profile_combo.findText(profile.name, Qt.MatchFixedString)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            dialog.accept()

        def delete_selected() -> None:
            item = profile_list.currentItem()
            if item is None:
                QMessageBox.information(dialog, "Manage Profiles", "Select a saved profile first.")
                return

            profile_name = item.text()
            answer = QMessageBox.question(
                dialog,
                "Delete Profile?",
                f"Delete saved profile '{profile_name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

            if profile_name not in self.profiles:
                return

            del self.profiles[profile_name]
            self.profile_store.save(self.profiles)
            self._refresh_profile_combo()

            current_name = self.bank_name_input.text().strip()
            if current_name == profile_name:
                self.profile_combo.setCurrentIndex(0)

            row = profile_list.row(item)
            profile_list.takeItem(row)
            if profile_list.count():
                profile_list.setCurrentRow(min(row, profile_list.count() - 1))
            else:
                details.clear()

        profile_list.currentItemChanged.connect(lambda *_args: refresh_details())
        load_btn.clicked.connect(load_selected)
        delete_btn.clicked.connect(delete_selected)
        close_btn.clicked.connect(dialog.accept)

        if profile_list.count():
            current_name = self.profile_combo.currentText().strip()
            if current_name:
                matches = profile_list.findItems(current_name, Qt.MatchFixedString)
                if matches:
                    profile_list.setCurrentItem(matches[0])
                else:
                    profile_list.setCurrentRow(0)
            else:
                profile_list.setCurrentRow(0)

        dialog.exec()

    def _format_profile_summary(self, profile: BankProfile) -> str:
        field_lines = []
        for field_name in sorted(profile.field_map):
            mapped_value = profile.field_map[field_name]
            field_lines.append(f"{field_name}: {mapped_value}")

        if profile.use_split_amounts:
            field_lines.append(f"debit: {profile.debit_col or '(not set)'}")
            field_lines.append(f"credit: {profile.credit_col or '(not set)'}")

        headers_text = ", ".join(profile.headers) if profile.headers else "(none)"
        mappings_text = "\n".join(field_lines) if field_lines else "(none)"

        return (
            f"Name: {profile.name}\n"
            f"Account ID: {profile.account_id or '(none)'}\n"
            f"Account Type: {profile.account_type}\n"
            f"Currency: {profile.currency}\n"
            f"Delimiter: {profile.delimiter!r}\n"
            f"Date Format: {profile.date_format or '(none)'}\n"
            f"Day-first Dates: {'Yes' if profile.dayfirst else 'No'}\n"
            f"Auto-parse Filename Metadata: {'Yes' if profile.auto_parse_filename_metadata else 'No'}\n"
            f"Filename Pattern: {profile.filename_pattern}\n"
            f"CSV Has Header Row: {'Yes' if profile.has_header else 'No'}\n"
            f"Use Split Amounts: {'Yes' if profile.use_split_amounts else 'No'}\n\n"
            f"Headers:\n{headers_text}\n\n"
            f"Field Mappings:\n{mappings_text}"
        )

    def _validate_required_fields(self, profile: BankProfile) -> bool:
        if not profile.field_map.get("date"):
            QMessageBox.warning(self, "Missing Mapping", "Map the required csv2ofx field 'date'.")
            return False

        if profile.use_split_amounts:
            if not profile.debit_col or not profile.credit_col:
                QMessageBox.warning(
                    self,
                    "Missing Mapping",
                    "Choose both debit and credit columns when using split amounts.",
                )
                return False
        elif not profile.field_map.get("amount"):
            QMessageBox.warning(self, "Missing Mapping", "Map the required csv2ofx field 'amount'.")
            return False

        return True
