import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...config.constants import CSV2OFX_FIELD_LABELS


class UiSectionMixin:
    REQUIRED_FIELDS = {"date", "amount", "payee", "desc", "notes", "check_num"}
    ADVANCED_FIELDS = {"id", "balance", "class", "account", "bank"}

    def _asset_path(self, name: str) -> str:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return (Path(sys._MEIPASS) / "openstatement" / "ui" / "assets" / name).as_posix()
        return (Path(__file__).resolve().parent.parent / "assets" / name).as_posix()

    def _platform_layout_metrics(self) -> tuple[tuple[int, int, int, int], int]:
        if sys.platform == "darwin":
            return (16, 16, 16, 16), 12
        if sys.platform.startswith("win"):
            return (14, 14, 14, 14), 10
        return (14, 14, 14, 14), 11

    def _build_ui(self) -> None:
        chevron_path = self._asset_path("chevron_down.svg")
        stylesheet = """
            QMainWindow {
                background: #f5f7fb;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QWidget#page {
                background: #f5f7fb;
            }
            QFrame#sectionCard {
                background: white;
                border: 1px solid #dfe5ee;
                border-radius: 14px;
            }
            QLabel#sectionTitle {
                font-size: 15px;
                font-weight: 600;
                color: #14213d;
            }
            QLabel#sectionHint {
                font-size: 12px;
                color: #667085;
            }
            QLabel#stepBadge {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 15px;
                background: #1f6fe5;
                color: white;
                font-weight: 700;
                padding-bottom: 1px;
            }
            QLabel#subsectionTitle {
                font-size: 12px;
                font-weight: 600;
                color: #14213d;
                border-left: 3px solid #1f6fe5;
                padding-left: 10px;
            }
            QLabel#footerStatus {
                font-size: 12px;
                color: #344054;
            }
            QLabel#inlineHint {
                font-size: 12px;
                color: #667085;
            }
            QLabel#tipLabel {
                color: #475467;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                min-height: 36px;
                padding: 0 10px;
                border: 1px solid #d0d5dd;
                border-radius: 8px;
                background: white;
                color: #14213d;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #1f6fe5;
            }
            QComboBox {
                padding-right: 34px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border: none;
                border-left: 1px solid #eaecf0;
                background: #fcfcfd;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
                image: url(__CHEVRON_PATH__);
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d0d5dd;
                background: white;
                selection-background-color: #eff6ff;
                selection-color: #14213d;
                outline: 0;
                padding: 4px;
            }
            QCheckBox {
                color: #14213d;
            }
            QPushButton, QToolButton {
                min-height: 36px;
                padding: 0 14px;
                border: 1px solid #d0d5dd;
                border-radius: 8px;
                background: white;
                color: #14213d;
            }
            QPushButton:hover, QToolButton:hover {
                background: #f8fafc;
            }
            QPushButton#primaryButton {
                background: #1f6fe5;
                border-color: #1f6fe5;
                color: white;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background: #185ec3;
            }
            QFrame#divider {
                background: #e4e7ec;
                min-height: 1px;
                max-height: 1px;
            }
            QFrame#tipCard {
                background: #f8fbff;
                border: 1px solid #dbeafe;
                border-radius: 10px;
            }
            """
        self.setStyleSheet(stylesheet.replace("__CHEVRON_PATH__", chevron_path))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(scroll)

        container = QWidget()
        container.setObjectName("page")
        scroll.setWidget(container)

        margins, spacing = self._platform_layout_metrics()
        root = QVBoxLayout(container)
        root.setContentsMargins(*margins)
        root.setSpacing(spacing)
        root.setAlignment(Qt.AlignTop)

        root.addWidget(self._build_csv_section())
        root.addWidget(self._build_mapping_section())
        root.addWidget(self._build_profile_section())
        root.addWidget(self._build_convert_section())
        root.addLayout(self._build_footer())
        root.addStretch(1)

        self._update_amount_mode(self.use_split_amounts.isChecked())
        self._toggle_filename_metadata_panel(self.auto_parse_filename_check.isChecked())
        self._toggle_advanced_fields(False)

    def _build_csv_section(self) -> QWidget:
        card, body = self._create_section_card(
            1,
            "Load CSV File",
            "Select your CSV statement and configure how it's parsed.",
        )

        self.csv_path_input = QLineEdit()
        self.csv_path_input.setMinimumWidth(420)
        self.csv_path_input.setPlaceholderText("Choose a CSV file...")

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.choose_csv)
        browse_btn.setMinimumWidth(132)

        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        path_row.addWidget(self._field_label("CSV file"), 0)
        path_row.addWidget(self.csv_path_input, 1)
        path_row.addWidget(browse_btn, 0)
        body.addLayout(path_row)

        self.delimiter_input = QLineEdit(",")
        self.delimiter_input.setMaxLength(1)
        self.delimiter_input.setMaximumWidth(56)

        delimiter_label = self._field_label("Delimiter")
        delimiter_hint = QLabel("Usually ',' or '\\t' (tab)")
        delimiter_hint.setObjectName("inlineHint")

        self.detected_label = QLabel("No CSV loaded")
        self.detected_label.setObjectName("sectionHint")
        self.detected_label.setAlignment(Qt.AlignCenter)
        self.detected_label.setMinimumHeight(36)
        self.detected_label.setStyleSheet(
            "padding: 0 10px; border: 1px solid #eaecf0; border-radius: 8px; background: #f8fafc;"
        )

        meta_row = QGridLayout()
        meta_row.setHorizontalSpacing(12)
        meta_row.setVerticalSpacing(8)
        meta_row.setColumnStretch(4, 1)
        meta_row.addWidget(delimiter_label, 0, 0)
        meta_row.addWidget(self.delimiter_input, 0, 1)
        meta_row.addWidget(delimiter_hint, 0, 2)
        meta_row.addWidget(self._field_label("Detection"), 0, 3)
        meta_row.addWidget(self.detected_label, 0, 4)
        body.addLayout(meta_row)

        self.auto_parse_filename_check = QCheckBox("Auto-parse filename metadata")
        self.auto_parse_filename_check.toggled.connect(self._on_filename_metadata_settings_changed)
        self.auto_parse_filename_check.toggled.connect(self._toggle_filename_metadata_panel)
        body.addWidget(self.auto_parse_filename_check)

        self.filename_metadata_panel = QWidget()
        filename_layout = QGridLayout(self.filename_metadata_panel)
        filename_layout.setContentsMargins(0, 0, 0, 0)
        filename_layout.setHorizontalSpacing(12)
        filename_layout.setVerticalSpacing(10)
        filename_layout.setColumnStretch(1, 1)

        self.filename_pattern_input = QLineEdit("{account_name}_{account_id}_{statement_date}_{ending_balance}.csv")
        self.filename_pattern_input.textChanged.connect(self._on_filename_metadata_settings_changed)
        self.filename_pattern_input.setPlaceholderText("Filename parsing pattern")

        self.filename_metadata_label = QLabel("Filename metadata parsing is off.")
        self.filename_metadata_label.setObjectName("sectionHint")
        self.filename_metadata_label.setWordWrap(True)

        self.filename_account_input = QLineEdit()
        self.filename_account_input.setPlaceholderText("Account ID, example 54674009 or CHK-54674009")
        self.filename_date_input = QLineEdit()
        self.filename_date_input.setPlaceholderText("YYYY-MM-DD, YYYYMMDD, MM-DD-YYYY...")
        self.filename_balance_input = QLineEdit()
        self.filename_balance_input.setPlaceholderText("1520.44 or -120.55")

        filename_layout.addWidget(self._field_label("Filename pattern"), 0, 0)
        filename_layout.addWidget(self.filename_pattern_input, 0, 1, 1, 3)
        filename_layout.addWidget(self._field_label("Metadata status"), 1, 0)
        filename_layout.addWidget(self.filename_metadata_label, 1, 1, 1, 3)
        filename_layout.addWidget(self._field_label("Metadata account ID"), 2, 0)
        filename_layout.addWidget(self.filename_account_input, 2, 1)
        filename_layout.addWidget(self._field_label("Metadata statement date"), 2, 2)
        filename_layout.addWidget(self.filename_date_input, 2, 3)
        filename_layout.addWidget(self._field_label("Metadata ending balance"), 3, 0)
        filename_layout.addWidget(self.filename_balance_input, 3, 1)

        body.addWidget(self.filename_metadata_panel)
        return card

    def _build_mapping_section(self) -> QWidget:
        advanced_toggle = QToolButton()
        advanced_toggle.setCheckable(True)
        advanced_toggle.setChecked(True)
        advanced_toggle.setText("Hide advanced fields")
        advanced_toggle.clicked.connect(self._toggle_advanced_fields)
        self.advanced_toggle = advanced_toggle

        card, body = self._create_section_card(
            2,
            "Map Fields",
            "Match each OFX field to a column in your CSV.",
            header_action=advanced_toggle,
        )

        body.addWidget(self._subsection_title("Required Fields"))

        required_grid = QGridLayout()
        required_grid.setHorizontalSpacing(18)
        required_grid.setVerticalSpacing(12)
        required_grid.setColumnStretch(1, 1)
        required_grid.setColumnStretch(3, 1)

        self.mapping_combos = {}
        required_fields = [item for item in CSV2OFX_FIELD_LABELS if item[0] in self.REQUIRED_FIELDS]
        self._populate_mapping_grid(required_grid, required_fields)
        body.addLayout(required_grid)

        divider = QFrame()
        divider.setObjectName("divider")
        body.addWidget(divider)

        advanced_header_row = QHBoxLayout()
        advanced_header_row.setContentsMargins(0, 0, 0, 0)
        advanced_header_row.addWidget(self._subsection_title("Advanced / Optional Fields"))
        advanced_header_row.addStretch(1)
        body.addLayout(advanced_header_row)

        self.advanced_fields_panel = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_fields_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(12)

        advanced_grid = QGridLayout()
        advanced_grid.setHorizontalSpacing(18)
        advanced_grid.setVerticalSpacing(12)
        advanced_grid.setColumnStretch(1, 1)
        advanced_grid.setColumnStretch(3, 1)

        advanced_fields = [item for item in CSV2OFX_FIELD_LABELS if item[0] in self.ADVANCED_FIELDS]
        self._populate_mapping_grid(advanced_grid, advanced_fields)
        advanced_layout.addLayout(advanced_grid)

        self.use_split_amounts = QCheckBox("Use separate debit/credit columns for amount")
        self.use_split_amounts.toggled.connect(self._update_amount_mode)
        advanced_layout.addWidget(self.use_split_amounts)

        split_grid = QGridLayout()
        split_grid.setHorizontalSpacing(18)
        split_grid.setVerticalSpacing(12)
        split_grid.setColumnStretch(1, 1)
        split_grid.setColumnStretch(3, 1)

        self.debit_col = QComboBox()
        self.credit_col = QComboBox()
        self.debit_col.addItem("")
        self.credit_col.addItem("")
        split_grid.addWidget(self._field_label("Debit column"), 0, 0)
        split_grid.addWidget(self.debit_col, 0, 1)
        split_grid.addWidget(self._field_label("Credit column"), 0, 2)
        split_grid.addWidget(self.credit_col, 0, 3)
        advanced_layout.addLayout(split_grid)

        tip_card = QFrame()
        tip_card.setObjectName("tipCard")
        tip_layout = QHBoxLayout(tip_card)
        tip_layout.setContentsMargins(14, 12, 14, 12)
        tip_layout.setSpacing(10)
        tip_icon = QLabel("i")
        tip_icon.setAlignment(Qt.AlignCenter)
        tip_icon.setObjectName("stepBadge")
        tip_icon.setStyleSheet(
            "min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; border-radius: 9px; font-size: 11px;"
        )
        tip_text = QLabel(
            "Tip: Map the required fields first (Date and Amount). Others are optional and can be added for more accurate OFX data."
        )
        tip_text.setObjectName("tipLabel")
        tip_text.setWordWrap(True)
        tip_layout.addWidget(tip_icon, 0, Qt.AlignTop)
        tip_layout.addWidget(tip_text, 1)
        advanced_layout.addWidget(tip_card)

        body.addWidget(self.advanced_fields_panel)
        return card

    def _build_profile_section(self) -> QWidget:
        card, body = self._create_section_card(
            3,
            "Bank Profile",
            "Define or load the bank profile for your OFX file.",
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.bank_name_input = QLineEdit()
        self.bank_name_input.setPlaceholderText("e.g., My Checking Account")

        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._apply_selected_profile)

        self.date_format_input = QLineEdit("%m/%d/%Y")
        self.date_format_input.setMaximumWidth(180)
        date_format_help = (
            "Enter the CSV transaction date format passed to csv2ofx, using strftime-style tokens such as "
            "%m/%d/%Y, %d/%m/%Y, or %Y-%m-%d. If your CSV dates are ambiguous, use Day-first dates as needed."
        )
        self.date_format_input.setToolTip(date_format_help)
        date_hint = QLabel("Example: %m/%d/%Y")
        date_hint.setObjectName("inlineHint")
        date_hint.setToolTip(date_format_help)
        date_hint_row = QHBoxLayout()
        date_hint_row.setContentsMargins(0, 0, 0, 0)
        date_hint_row.setSpacing(10)
        date_hint_row.addWidget(self.date_format_input)
        date_hint_row.addWidget(date_hint)
        date_hint_row.addStretch(1)
        date_hint_widget = QWidget()
        date_hint_widget.setLayout(date_hint_row)

        self.dayfirst_check = QCheckBox("Day-first dates")
        dayfirst_hint = QLabel("(dd/mm/yyyy)")
        dayfirst_hint.setObjectName("inlineHint")
        dayfirst_row = QHBoxLayout()
        dayfirst_row.setContentsMargins(0, 0, 0, 0)
        dayfirst_row.setSpacing(10)
        dayfirst_row.addWidget(self.dayfirst_check)
        dayfirst_row.addWidget(dayfirst_hint)
        dayfirst_row.addStretch(1)
        dayfirst_widget = QWidget()
        dayfirst_widget.setLayout(dayfirst_row)

        self.account_type_combo = QComboBox()
        self.account_type_combo.addItems(["CHECKING", "SAVINGS", "CREDITLINE"])

        self.account_id_input = QLineEdit()
        self.account_id_input.setPlaceholderText("e.g., 123456789")

        self.currency_input = QLineEdit("USD")
        self.currency_input.setMaximumWidth(120)

        open_profiles_btn = QPushButton("Manage Profiles")
        open_profiles_btn.clicked.connect(self.manage_profiles)
        open_profiles_btn.setMinimumWidth(190)

        save_profile_btn = QPushButton("Save/Update Profile")
        save_profile_btn.setObjectName("primaryButton")
        save_profile_btn.clicked.connect(self.save_profile)
        save_profile_btn.setMinimumWidth(210)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)
        button_row.addStretch(1)
        button_row.addWidget(open_profiles_btn)
        button_row.addWidget(save_profile_btn)
        button_widget = QWidget()
        button_widget.setLayout(button_row)

        grid.addWidget(self._field_label("Load saved profile"), 0, 0)
        grid.addWidget(self.profile_combo, 0, 1)
        grid.addWidget(self._field_label("Account type"), 0, 2)
        grid.addWidget(self.account_type_combo, 0, 3)
        grid.addWidget(self._field_label("Profile name"), 1, 0)
        grid.addWidget(self.bank_name_input, 1, 1)
        grid.addWidget(self._field_label("Account ID"), 1, 2)
        grid.addWidget(self.account_id_input, 1, 3)
        date_parse_label = self._field_label("Date parse format")
        date_parse_label.setToolTip(date_format_help)
        grid.addWidget(date_parse_label, 2, 0)
        grid.addWidget(date_hint_widget, 2, 1)
        grid.addWidget(self._field_label("Currency"), 2, 2)
        grid.addWidget(self.currency_input, 2, 3, alignment=Qt.AlignLeft)
        grid.addWidget(dayfirst_widget, 3, 0, 1, 2)
        grid.addWidget(button_widget, 3, 2, 1, 2)

        body.addLayout(grid)
        return card

    def _build_convert_section(self) -> QWidget:
        card, body = self._create_section_card(
            4,
            "Convert",
            "Preview your OFX data or convert the CSV to OFX.",
        )

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addStretch(1)

        preview_btn = QPushButton("Preview OFX")
        preview_btn.clicked.connect(self.preview_ofx)
        preview_btn.setMinimumWidth(150)

        convert_btn = QPushButton("Convert CSV -> OFX")
        convert_btn.setObjectName("primaryButton")
        convert_btn.clicked.connect(self.convert_to_ofx)
        convert_btn.setMinimumWidth(200)

        row.addWidget(preview_btn)
        row.addWidget(convert_btn)
        body.addLayout(row)
        return card

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 0, 4, 0)
        footer.setSpacing(10)

        self.status_label = QLabel("No CSV loaded")
        self.status_label.setObjectName("footerStatus")

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_form)
        reset_btn.setMinimumWidth(100)

        footer.addWidget(self.status_label)
        footer.addStretch(1)
        footer.addWidget(reset_btn)
        return footer

    def _create_section_card(
        self,
        step_number: int,
        title: str,
        subtitle: str,
        header_action: QWidget | None = None,
    ) -> tuple[QWidget, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("sectionCard")

        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        badge = QLabel(str(step_number))
        badge.setObjectName("stepBadge")
        badge.setAlignment(Qt.AlignCenter)
        header.addWidget(badge, 0, Qt.AlignTop)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("sectionHint")

        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        header.addLayout(title_col, 1)

        if header_action is not None:
            header.addWidget(header_action, 0, Qt.AlignTop)

        outer.addLayout(header)

        body = QVBoxLayout()
        body.setContentsMargins(6, 6, 6, 0)
        body.setSpacing(12)
        outer.addLayout(body)
        return card, body

    def _populate_mapping_grid(self, grid: QGridLayout, fields: list[tuple[str, str]]) -> None:
        left_fields = fields[::2]
        right_fields = fields[1::2]
        max_rows = max(len(left_fields), len(right_fields))

        for row_idx in range(max_rows):
            if row_idx < len(left_fields):
                field_name, label = left_fields[row_idx]
                combo = self._mapping_combo()
                self.mapping_combos[field_name] = combo
                grid.addWidget(self._field_label(label), row_idx, 0)
                grid.addWidget(combo, row_idx, 1)

            if row_idx < len(right_fields):
                field_name, label = right_fields[row_idx]
                combo = self._mapping_combo()
                self.mapping_combos[field_name] = combo
                grid.addWidget(self._field_label(label), row_idx, 2)
                grid.addWidget(combo, row_idx, 3)

    def _mapping_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem("")
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return combo

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label.setWordWrap(True)
        return label

    def _subsection_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("subsectionTitle")
        return label

    def _set_combo_headers(self, combo: QComboBox, headers: list[str], include_empty: bool = True) -> None:
        current = combo.currentText()
        combo.clear()
        if include_empty:
            combo.addItem("")
        combo.addItems(headers)
        if current:
            idx = combo.findText(current, Qt.MatchFixedString)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _set_headers(self, headers: list[str]) -> None:
        self.current_headers = headers
        for combo in self.mapping_combos.values():
            self._set_combo_headers(combo, headers, include_empty=True)
        self._set_combo_headers(self.debit_col, headers, include_empty=True)
        self._set_combo_headers(self.credit_col, headers, include_empty=True)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        idx = combo.findText(value, Qt.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _update_amount_mode(self, split_enabled: bool) -> None:
        self.mapping_combos["amount"].setEnabled(not split_enabled)
        self.debit_col.setEnabled(split_enabled)
        self.credit_col.setEnabled(split_enabled)

    def _toggle_filename_metadata_panel(self, enabled: bool) -> None:
        self.filename_metadata_panel.setVisible(enabled)

    def _toggle_advanced_fields(self, checked: bool) -> None:
        self.advanced_fields_panel.setVisible(checked)
        self.advanced_toggle.setText("Hide advanced fields" if checked else "Show advanced fields")

    def reset_form(self) -> None:
        self.csv_path_input.clear()
        self.delimiter_input.setText(",")
        self.detected_label.setText("No CSV loaded")
        self.status_label.setText("No CSV loaded")
        self.current_headers = []

        for combo in self.mapping_combos.values():
            combo.clear()
            combo.addItem("")

        self.use_split_amounts.setChecked(False)
        self.debit_col.clear()
        self.debit_col.addItem("")
        self.credit_col.clear()
        self.credit_col.addItem("")

        self.auto_parse_filename_check.setChecked(False)
        self.filename_pattern_input.setText("{account_name}_{account_id}_{statement_date}_{ending_balance}.csv")
        self.filename_metadata_label.setText("Filename metadata parsing is off.")
        self.filename_account_input.clear()
        self.filename_date_input.clear()
        self.filename_balance_input.clear()

        self.bank_name_input.clear()
        self.profile_combo.setCurrentIndex(0)
        self.date_format_input.setText("%m/%d/%Y")
        self.dayfirst_check.setChecked(False)
        self.account_type_combo.setCurrentText("CHECKING")
        self.account_id_input.clear()
        self.currency_input.setText("USD")
