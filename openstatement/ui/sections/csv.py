import csv
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from ...models.profile import normalize_header
from ...services.filename_metadata import FilenameMetadata, account_ids_match, parse_filename_metadata
from ...services.number_format import (
    detect_currency,
    detect_date_format,
    detect_decimal_separator,
    detect_delimiter,
)

FORMAT_SAMPLE_ROWS = 50
ACCOUNT_NUMBER_HEADER_HINTS = (
    "account number",
    "account no",
    "account #",
    "acct number",
    "acct no",
    "acct #",
    "account id",
    "kontonummer",
    "iban",
)
CURRENCY_HEADER_HINTS = ("currency", "waehrung", "währung", "devise", "moneda", "valuta", "waluta", "valuuta")


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
        # The user is adjusting the current file, not opening a new one: don't ask about profiles again.
        self.load_csv_headers(source, prompt_profile=False)

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

    def load_csv_headers(self, path: str, *, detect: bool = True, prompt_profile: bool = True) -> None:
        """Read the CSV's first rows and rebuild the column pickers.

        ``detect`` guesses mappings, value formats, filename metadata and saved
        profiles; it is turned off when re-reading the file while a profile is
        being applied. ``prompt_profile`` controls whether a matching saved
        profile is offered, which should happen once per newly opened file.
        """
        delimiter = self._effective_delimiter(self.delimiter_input.text())
        has_header = self.csv_has_header_check.isChecked()
        leading_rows_to_skip = self.leading_rows_spin.value()
        source_path = Path(path)

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                if detect:
                    # Sniff the delimiter on the header line, not on any skipped preamble.
                    for _ in range(leading_rows_to_skip):
                        handle.readline()
                    header_line = handle.readline()
                    handle.seek(0)
                    if len(next(csv.reader([header_line], delimiter=delimiter), [])) <= 1:
                        detected = detect_delimiter(header_line, delimiter)
                        if detected != delimiter:
                            delimiter = detected
                            self.delimiter_input.setText(self._delimiter_for_input(detected))
                reader = csv.reader(handle, delimiter=delimiter)
                for _ in range(leading_rows_to_skip):
                    next(reader)
                first_row = next(reader)
                remaining_rows = list(reader) if detect else []
        except StopIteration:
            QMessageBox.critical(
                self,
                "CSV Error",
                "Leading rows to skip removes all rows from this CSV. "
                "Reduce the leading rows to skip.",
            )
            self.status_label.setText("CSV load failed")
            return
        except (OSError, csv.Error) as exc:
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
        if not detect:
            self.status_label.setText(source_path.name)
            return

        # Footer rows (totals, disclaimers) would spoil date/amount detection.
        trailing_rows_to_skip = self.trailing_rows_spin.value()
        if trailing_rows_to_skip:
            remaining_rows = remaining_rows[:-trailing_rows_to_skip]
        sample_rows = remaining_rows[:FORMAT_SAMPLE_ROWS]

        if has_header:
            self._guess_default_fields(headers)
            data_rows = sample_rows
        else:
            data_rows = [first_row, *sample_rows]
        self._detect_value_formats(headers, data_rows)
        metadata = self._refresh_filename_metadata(source_path)
        account_numbers = self._csv_account_numbers(headers, data_rows) if has_header else set()
        self._detect_saved_profile(
            headers,
            metadata,
            prompt=prompt_profile,
            account_numbers=account_numbers,
            source_path=source_path,
        )
        self.status_label.setText(source_path.name)

    def _csv_account_numbers(self, headers: list[str], rows: list[list[str]]) -> set[str]:
        """Values from columns like "Account Number" or "IBAN", used to tell same-bank accounts apart."""
        values: set[str] = set()
        for header in headers:
            normalized = normalize_header(header)
            if any(hint in normalized for hint in ACCOUNT_NUMBER_HEADER_HINTS):
                values.update(sample.strip() for sample in self._column_samples(headers, rows, header))
        return values

    def _column_samples(self, headers: list[str], rows: list[list[str]], column: str) -> list[str]:
        if not column or column not in headers:
            return []
        idx = headers.index(column)
        return [row[idx] for row in rows if idx < len(row) and row[idx].strip()]

    def _combo_column(self, combo) -> str:
        return str(combo.currentData() or combo.currentText()).strip()

    def _detect_value_formats(self, headers: list[str], rows: list[list[str]]) -> None:
        """Set date format and decimal separator from the CSV's own values when they are unambiguous.

        A saved profile applied afterwards still takes precedence.
        """
        amount_samples: list[str] = []
        for combo in (
            self.mapping_combos["amount"],
            self.mapping_combos["balance"],
            self.debit_col,
            self.credit_col,
        ):
            amount_samples.extend(self._column_samples(headers, rows, self._combo_column(combo)))
        separator = detect_decimal_separator(amount_samples)
        if separator:
            self._set_decimal_separator(separator)

        # Ambiguous dates like 03/04/2026 are day-first in nearly every country that
        # writes decimal commas, so let the amounts break the tie.
        date_samples = self._column_samples(headers, rows, self._combo_column(self.mapping_combos["date"]))
        prefer_dayfirst = separator == "," or self.dayfirst_check.isChecked()
        date_format = detect_date_format(date_samples, prefer_dayfirst=prefer_dayfirst)
        if date_format:
            self.date_format_input.setText(date_format)

        currency_samples = list(amount_samples)
        for header in headers:
            if any(hint in normalize_header(header) for hint in CURRENCY_HEADER_HINTS):
                currency_samples.extend(self._column_samples(headers, rows, header))
        currency = detect_currency(currency_samples)
        if currency:
            self.currency_input.setText(currency)

    def _on_filename_metadata_settings_changed(self, *_args) -> None:
        source = self.csv_path_input.text().strip()
        if not source:
            return
        self._refresh_filename_metadata(Path(source))

    def _refresh_filename_metadata(self, source_path: Path, update_identity: bool = True) -> FilenameMetadata | None:
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
        if update_identity:
            self.bank_name_input.setText(result.metadata.account_name)
            self.account_id_input.setText(result.metadata.account_id)
        return result.metadata

    def _guess_default_fields(self, headers: list[str]) -> None:
        guesses = {
            "date": ["date", "posted", "transaction date", "datum", "buchungstag"],
            "amount": ["amount", "total", "value", "betrag"],
            "payee": ["payee", "merchant", "description", "name"],
            "desc": ["description", "details", "merchant"],
            "notes": ["memo", "note", "notes"],
            "check_num": ["check", "check num", "reference"],
            "id": ["id", "transaction id", "fitid"],
            "balance": ["balance", "running balance", "saldo", "kontostand"],
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

    def _read_csv_view(
        self, source_path: Path, delimiter: str, leading_rows: int, trailing_rows: int
    ) -> tuple[list[str], set[str]] | None:
        """Header signature and account numbers of a CSV as a profile with these settings would read it."""
        try:
            with open(source_path, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle, delimiter=delimiter or ",")
                for _ in range(max(0, leading_rows)):
                    next(reader)
                header_row = [h.strip() for h in next(reader)]
                rows = list(reader)
        except (OSError, StopIteration, csv.Error):
            return None
        if trailing_rows > 0:
            rows = rows[:-trailing_rows]
        rows = rows[:FORMAT_SAMPLE_ROWS]
        return [normalize_header(h) for h in header_row], self._csv_account_numbers(header_row, rows)

    def _detect_saved_profile(
        self,
        headers: list[str],
        metadata: FilenameMetadata | None = None,
        prompt: bool = True,
        account_numbers: set[str] | None = None,
        source_path: Path | None = None,
    ) -> None:
        signature = [normalize_header(h) for h in headers]
        csv_has_header = self.csv_has_header_check.isChecked()
        ranked: list[tuple[int, int, int, str, object]] = []

        # Profiles may skip a bank preamble/footer or use another delimiter than the form currently does,
        # so compare each one against the file as *that profile* would read it.
        current_view = (
            self._effective_delimiter(self.delimiter_input.text()),
            self.leading_rows_spin.value(),
            self.trailing_rows_spin.value(),
        )
        views: dict[tuple[str, int, int], tuple[list[str], set[str]] | None] = {}

        for profile in self.profiles.values():
            score = 0
            metadata_score = 0
            header_score = 0
            reasons: list[str] = []

            profile_view = (profile.delimiter, profile.leading_rows_to_skip, profile.trailing_rows_to_skip)
            view_signature, view_accounts = signature, account_numbers
            view_has_header = csv_has_header
            if source_path is not None and profile.has_header and profile_view != current_view:
                if profile_view not in views:
                    views[profile_view] = self._read_csv_view(source_path, *profile_view)
                view = views[profile_view]
                view_signature, view_accounts = view if view else ([], set())
                view_has_header = True

            exact_header_match = view_has_header and profile.has_header and profile.headers == view_signature

            if exact_header_match:
                header_score += 25
                reasons.append("CSV headers")

            if metadata and metadata.account_id and account_ids_match(metadata.account_id, profile.account_id):
                metadata_score += 100
                reasons.append("filename account ID")

            if view_accounts and any(account_ids_match(value, profile.account_id) for value in view_accounts):
                metadata_score += 100
                reasons.append("account number in CSV")

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

        ranked.sort(key=lambda item: (-item[0], -item[1], -item[2], item[4].name.casefold()))
        top_score = ranked[0][0]
        top_matches = [item for item in ranked if item[0] == top_score]
        top_names = ", ".join(item[4].name for item in top_matches)

        _, metadata_score, header_score, match_reason, profile = ranked[0]
        exact_header_match = header_score > 0

        if len(top_matches) > 1:
            self.detected_label.setText(f"Found {len(top_matches)} matching profiles: {top_names}")
        elif metadata_score > 0 and exact_header_match:
            self.detected_label.setText(f"Found profile(s): {top_names} (matched by {match_reason})")
        elif exact_header_match:
            self.detected_label.setText(f"Found matching profile(s): {top_names}")
        else:
            self.detected_label.setText(f"Found likely profile(s): {top_names} (matched by {match_reason})")

        if not prompt:
            return

        if len(top_matches) > 1:
            chosen = self._choose_profile([item[4] for item in top_matches], top_matches[0][3])
        else:
            chosen = profile if self._confirm_profile(profile, metadata_score, exact_header_match, match_reason) else None

        if chosen is not None:
            self._load_profile_to_ui(chosen)

    def _confirm_profile(self, profile, metadata_score: int, exact_header_match: bool, match_reason: str) -> bool:
        if metadata_score > 0 and exact_header_match:
            prompt_text = (
                f"A bank profile was found: '{profile.name}'.\n"
                f"Matched by {match_reason}.\nApply it now?"
            )
        elif exact_header_match:
            prompt_text = f"A saved bank format was found: '{profile.name}'.\nApply it now?"
        else:
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
        return answer == QMessageBox.Yes

    def _choose_profile(self, profiles: list, match_reason: str):
        """Let the user pick between equally good matches (e.g. two accounts at the same bank)."""
        labels = {}
        for candidate in profiles:
            label = candidate.name
            if candidate.account_id:
                label = f"{candidate.name}  \u2014  account {candidate.account_id}"
            labels[label] = candidate

        choice, ok = QInputDialog.getItem(
            self,
            "Choose saved profile",
            f"Several saved profiles match this CSV ({match_reason}).\nChoose the one to apply:",
            list(labels),
            0,
            False,
        )
        if not ok:
            return None
        return labels.get(choice)

    def _normalize_match_name(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()
