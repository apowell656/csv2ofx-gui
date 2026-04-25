from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from ...models.profile import BankProfile, normalize_header, to_account_id


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
        self.delimiter_input.setText(profile.delimiter or ",")
        self.date_format_input.setText(profile.date_format)
        self.dayfirst_check.setChecked(profile.dayfirst)
        self.account_id_input.setText(profile.account_id)
        self.currency_input.setText(profile.currency)

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
            field: combo.currentText().strip()
            for field, combo in self.mapping_combos.items()
            if combo.currentText().strip()
        }
        return BankProfile(
            name=name,
            headers=[normalize_header(h) for h in self.current_headers],
            delimiter=(self.delimiter_input.text() or ",")[:1],
            field_map=field_map,
            debit_col=self.debit_col.currentText().strip(),
            credit_col=self.credit_col.currentText().strip(),
            use_split_amounts=self.use_split_amounts.isChecked(),
            date_format=self.date_format_input.text().strip(),
            dayfirst=self.dayfirst_check.isChecked(),
            account_type=self.account_type_combo.currentText(),
            account_id=self.account_id_input.text().strip() or to_account_id(name),
            currency=(self.currency_input.text().strip() or "USD").upper(),
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

    def open_profiles_file(self) -> None:
        path = self.profile_store.path
        if not path.exists():
            try:
                path.write_text("{}", encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self, "Profiles File", f"Could not create profiles file:\n{exc}")
                return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not opened:
            QMessageBox.information(self, "Profiles File", f"Profiles file path:\n{path}")

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
