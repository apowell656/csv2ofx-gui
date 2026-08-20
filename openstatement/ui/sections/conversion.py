from pathlib import Path

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout

from ...models.profile import BankProfile
from ...services.conversion import (
    OfxMetadataOverrides,
    build_ofx_preview,
    find_csv2ofx_binary,
    mapped_columns_missing,
    run_conversion,
    suggested_export_filename,
)
from ...services.filename_metadata import normalize_balance, normalize_statement_date


class ConversionSectionMixin:
    def convert_to_ofx(self) -> None:
        prep = self._prepare_conversion_inputs()
        if prep is None:
            return
        csv2ofx_bin, source_path, profile = prep

        default_name = self._suggested_export_filename(source_path, profile)
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Save OFX file",
            str(source_path.with_name(default_name)),
            "OFX Files (*.ofx)",
        )

        if not destination:
            return

        try:
            overrides = self._resolve_metadata_overrides(profile)
            run_conversion(csv2ofx_bin, source_path, Path(destination), profile, overrides=overrides)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Conversion Error", str(exc))
            return

        QMessageBox.information(self, "Success", f"OFX file written to:\n{destination}")

    def preview_ofx(self) -> None:
        prep = self._prepare_conversion_inputs()
        if prep is None:
            return
        csv2ofx_bin, source_path, profile = prep

        try:
            preview_text = build_ofx_preview(csv2ofx_bin, source_path, profile)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Preview Error", str(exc))
            return

        self._show_preview_dialog(preview_text)

    def _suggested_export_filename(self, source_path: Path, profile: BankProfile) -> str:
        try:
            return suggested_export_filename(source_path, profile)
        except Exception:  # noqa: BLE001
            return f"{source_path.stem}.ofx"

    def _resolve_source_csv_path(self) -> Path | None:
        csv_source = self.csv_path_input.text().strip()
        if not csv_source:
            QMessageBox.warning(self, "Missing CSV", "Choose a CSV file first.")
            return None

        source_path = Path(csv_source)
        if not source_path.exists():
            QMessageBox.warning(self, "Missing CSV", "The selected CSV file does not exist.")
            return None
        return source_path

    def _build_valid_profile(self) -> BankProfile | None:
        profile = self._build_profile_from_ui()
        if not self._validate_required_fields(profile):
            return None
        return profile

    def _validate_mapped_columns(self, source_path: Path, profile: BankProfile) -> bool:
        missing_cols = mapped_columns_missing(source_path, profile)
        if not missing_cols:
            return True

        QMessageBox.warning(
            self,
            "Missing Columns",
            "These mapped columns are not present in the CSV:\n" + "\n".join(missing_cols),
        )
        return False

    def _find_csv2ofx_binary(self) -> str | None:
        csv2ofx_bin = find_csv2ofx_binary()
        if csv2ofx_bin:
            return csv2ofx_bin

        QMessageBox.critical(
            self,
            "csv2ofx Not Found",
            "The `csv2ofx` command is not installed or not in PATH.\n\n"
            "Install it with:\n"
            "pip install csv2ofx",
        )
        return None

    def _prepare_conversion_inputs(self) -> tuple[str, Path, BankProfile] | None:
        source_path = self._resolve_source_csv_path()
        if source_path is None:
            return None

        profile = self._build_valid_profile()
        if profile is None:
            return None

        if not self._validate_mapped_columns(source_path, profile):
            return None

        csv2ofx_bin = self._find_csv2ofx_binary()
        if csv2ofx_bin is None:
            return None

        return csv2ofx_bin, source_path, profile

    def _resolve_metadata_overrides(self, profile: BankProfile) -> OfxMetadataOverrides | None:
        account_id = self.filename_account_input.text().strip()
        date_text = normalize_statement_date(self.filename_date_input.text())
        balance_text = normalize_balance(self.filename_balance_input.text())

        if self.filename_date_input.text().strip() and not date_text:
            self.filename_metadata_label.setText(
                "Filename metadata date is invalid. Expected YYYY-MM-DD. Ignoring statement date override."
            )

        if self.filename_balance_input.text().strip() and not balance_text:
            self.filename_metadata_label.setText(
                "Filename metadata balance is invalid. Expected decimal value. Ignoring balance override."
            )

        if not account_id and not date_text and not balance_text:
            return None

        if account_id and not profile.field_map.get("account"):
            profile.account_id = account_id

        if balance_text:
            self.filename_balance_input.setText(balance_text)
        if date_text:
            self.filename_date_input.setText(date_text)

        return OfxMetadataOverrides(
            account_id=account_id,
            statement_date=date_text,
            ending_balance=balance_text,
        )

    def _show_preview_dialog(self, preview_text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("OFX Preview")
        dialog.resize(920, 520)

        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(preview_text)
        layout.addWidget(text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()
