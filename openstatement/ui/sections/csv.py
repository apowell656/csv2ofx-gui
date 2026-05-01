import csv
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ...models.profile import normalize_header
from ...services.filename_metadata import FilenameMetadata, parse_filename_metadata


class CsvSectionMixin:
    def _build_headerless_display_labels(self, first_row: list[str]) -> dict[str, str]:
        labels: dict[str, str] = {}
        for idx, value in enumerate(first_row, start=1):
            key = f"col_{idx}"
            sample = " ".join(str(value).split()).strip()
            if len(sample) > 28:
                sample = sample[:28].rstrip() + "..."
            labels[key] = f"{key} ({sample})" if sample else key
        return labels

    def _on_header_setting_changed(self, *_args) -> None:
        source = self.csv_path_input.text().strip()
        if not source:
            return
        self.load_csv_headers(source)

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
        self.status_label.setText(Path(path).name)
        self.load_csv_headers(path)

    def load_csv_headers(self, path: str) -> None:
        delimiter = self._effective_delimiter(self.delimiter_input.text())
        has_header = self.csv_has_header_check.isChecked()
        source_path = Path(path)

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle, delimiter=delimiter)
                first_row = next(reader)
        except (OSError, StopIteration, csv.Error) as exc:
            QMessageBox.critical(self, "CSV Error", f"Could not read CSV headers:\n{exc}")
            self.status_label.setText("CSV load failed")
            return

        if has_header:
            headers = [h.strip() for h in first_row]
            display_labels = None
        else:
            headers = [f"col_{idx}" for idx in range(1, len(first_row) + 1)]
            display_labels = self._build_headerless_display_labels(first_row)

        self._set_headers(headers, display_labels=display_labels)
        if has_header:
            self._guess_default_fields(headers)
        metadata = self._refresh_filename_metadata(source_path)
        self._detect_saved_profile(headers, metadata)
        self.status_label.setText(source_path.name)

    def _on_filename_metadata_settings_changed(self, *_args) -> None:
        source = self.csv_path_input.text().strip()
        if not source:
            return
        self._refresh_filename_metadata(Path(source))

    def _refresh_filename_metadata(self, source_path: Path) -> FilenameMetadata | None:
        result = parse_filename_metadata(source_path, self.filename_pattern_input.text().strip())

        if not self.auto_parse_filename_check.isChecked():
            self.filename_metadata_label.setText("Filename metadata parsing is off.")
            return result.metadata

        if result.metadata is None:
            self.filename_metadata_label.setText(
                f"Could not parse filename metadata: {result.error} You can still enter values manually."
            )
            self.filename_account_input.clear()
            self.filename_date_input.clear()
            self.filename_balance_input.clear()
            return None

        self.filename_metadata_label.setText("Detected from filename. Review and edit if needed before conversion.")
        self.filename_account_input.setText(result.metadata.account_id)
        self.filename_date_input.setText(result.metadata.statement_date)
        self.filename_balance_input.setText(result.metadata.ending_balance)
        self.bank_name_input.setText(result.metadata.account_name)
        self.account_id_input.setText(result.metadata.account_id)
        return result.metadata

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

    def _detect_saved_profile(self, headers: list[str], metadata: FilenameMetadata | None = None) -> None:
        signature = [normalize_header(h) for h in headers]
        csv_has_header = self.csv_has_header_check.isChecked()
        ranked: list[tuple[int, int, int, str, object]] = []

        for profile in self.profiles.values():
            score = 0
            metadata_score = 0
            header_score = 0
            reasons: list[str] = []
            exact_header_match = csv_has_header and profile.has_header and profile.headers == signature

            if exact_header_match:
                header_score += 25
                reasons.append("CSV headers")

            if metadata and metadata.account_id and profile.account_id == metadata.account_id:
                metadata_score += 100
                reasons.append("filename account ID")

            parsed_name = self._normalize_match_name(metadata.account_name) if metadata else ""
            profile_name = self._normalize_match_name(profile.name)
            if parsed_name and profile_name and parsed_name == profile_name:
                metadata_score += 35
                reasons.append("filename account name")

            score = metadata_score + header_score
            if score:
                ranked.append((score, metadata_score, header_score, ", ".join(reasons), profile))

        if not ranked:
            self.detected_label.setText("No matching saved profile found for this CSV format.")
            return

        ranked.sort(key=lambda item: (item[0], item[1], item[2], item[4].name.casefold()), reverse=True)
        top_score = ranked[0][0]
        top_matches = [item for item in ranked if item[0] == top_score]
        top_names = ", ".join(item[4].name for item in top_matches)

        profile = ranked[0][4]
        header_score = ranked[0][2]
        metadata_score = ranked[0][1]
        exact_header_match = header_score > 0
        match_reason = ranked[0][3]

        if metadata_score > 0:
            if exact_header_match:
                self.detected_label.setText(f"Found profile(s): {top_names} (matched by {match_reason})")
                prompt_text = (
                    f"A bank profile was found: '{profile.name}'.\n"
                    f"Matched by {match_reason}.\nApply it now?"
                )
            else:
                self.detected_label.setText(f"Found likely profile(s): {top_names} (matched by {match_reason})")
                prompt_text = (
                    f"A likely bank profile was found: '{profile.name}'.\n"
                    f"Matched by {match_reason}.\nApply it now?"
                )
        elif exact_header_match:
            self.detected_label.setText(f"Found matching profile(s): {top_names}")
            prompt_text = f"A saved bank format was found: '{profile.name}'.\nApply it now?"
        else:
            self.detected_label.setText(f"Found likely profile(s): {top_names} (matched by {match_reason})")
            prompt_text = (
                f"A likely bank profile was found: '{profile.name}'.\n"
                f"Matched by {match_reason}.\nApply it now?"
            )

        answer = QMessageBox.question(
            self,
            "Use saved profile?",
            prompt_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if answer == QMessageBox.Yes:
            self._load_profile_to_ui(profile)
            idx = self.profile_combo.findText(profile.name, Qt.MatchFixedString)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)

    def _normalize_match_name(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()
