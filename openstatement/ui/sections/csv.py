import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ...models.profile import normalize_header


class CsvSectionMixin:
    def choose_csv(self) -> None:
        start_dir = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose CSV file",
            start_dir,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        self.csv_path_input.setText(path)
        self.load_csv_headers(path)

    def load_csv_headers(self, path: str) -> None:
        delimiter = self.delimiter_input.text() or ","

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle, delimiter=delimiter)
                headers = next(reader)
        except (OSError, StopIteration, csv.Error) as exc:
            QMessageBox.critical(self, "CSV Error", f"Could not read CSV headers:\n{exc}")
            return

        headers = [h.strip() for h in headers]
        self._set_headers(headers)
        self._guess_default_fields(headers)
        self._detect_saved_profile(headers)

    def _guess_default_fields(self, headers: list[str]) -> None:
        guesses = {
            "date": ["date", "posted", "transaction date"],
            "amount": ["amount", "total", "value"],
            "payee": ["payee", "merchant", "description", "name"],
            "desc": ["description", "details", "merchant"],
            "notes": ["memo", "note", "notes"],
            "check_num": ["check", "check num", "reference"],
            "id": ["id", "transaction id", "fitid"],
            "balance": ["balance", "running balance"],
            "class": ["class", "category"],
            "account": ["account", "account name"],
            "bank": ["bank", "institution"],
            "debit": ["debit", "withdrawal", "outflow", "money out"],
            "credit": ["credit", "deposit", "inflow", "money in"],
        }

        normalized = {normalize_header(h): h for h in headers}

        for field, candidates in guesses.items():
            target = self.mapping_combos.get(field)
            if field == "debit":
                target = self.debit_col
            if field == "credit":
                target = self.credit_col
            if target is None:
                continue

            for candidate in candidates:
                match = next((original for key, original in normalized.items() if candidate in key), None)
                if not match:
                    continue
                idx = target.findText(match, Qt.MatchFixedString)
                if idx >= 0:
                    target.setCurrentIndex(idx)
                    break

    def _detect_saved_profile(self, headers: list[str]) -> None:
        signature = [normalize_header(h) for h in headers]
        matched = [p for p in self.profiles.values() if p.headers == signature]

        if not matched:
            self.detected_label.setText("No matching saved profile found for this CSV format.")
            return

        names = ", ".join(profile.name for profile in matched)
        self.detected_label.setText(f"Found matching profile(s): {names}")

        profile = matched[0]
        answer = QMessageBox.question(
            self,
            "Use saved profile?",
            f"A saved bank format was found: '{profile.name}'.\nApply it now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if answer == QMessageBox.Yes:
            self._load_profile_to_ui(profile)
            idx = self.profile_combo.findText(profile.name, Qt.MatchFixedString)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
