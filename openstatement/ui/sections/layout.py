import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...config.constants import CSV2OFX_FIELD_LABELS


class UiSectionMixin:
    def _platform_layout_metrics(self) -> tuple[tuple[int, int, int, int], int]:
        if sys.platform == "darwin":
            return (14, 14, 14, 14), 10
        if sys.platform.startswith("win"):
            return (12, 12, 12, 12), 9
        return (12, 12, 12, 12), 10

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QLabel#section_hint {
                font-size: 12px;
                color: #666;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
            }
            """
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        margins, spacing = self._platform_layout_metrics()
        root = QVBoxLayout(container)
        root.setContentsMargins(*margins)
        root.setSpacing(spacing)
        root.setAlignment(Qt.AlignTop)

        file_box = QGroupBox("Source CSV")
        file_form = QFormLayout(file_box)
        file_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        file_form.setHorizontalSpacing(12)
        file_form.setVerticalSpacing(10)

        self.csv_path_input = QLineEdit()
        self.csv_path_input.setMinimumWidth(360)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.choose_csv)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.csv_path_input)
        row.addWidget(browse_btn)

        self.delimiter_input = QLineEdit(",")
        self.delimiter_input.setMaxLength(1)
        self.delimiter_input.setMaximumWidth(60)

        self.detected_label = QLabel("No CSV loaded")
        self.detected_label.setWordWrap(False)
        self.detected_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.detected_label.setMinimumWidth(320)
        self.detected_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.detected_label.setObjectName("section_hint")

        file_form.addRow("CSV file", row)
        file_form.addRow("Delimiter", self.delimiter_input)
        file_form.addRow("Detection", self.detected_label)

        mapping_box = QGroupBox("Field Mapping")
        mapping_layout = QVBoxLayout(mapping_box)
        mapping_layout.setContentsMargins(12, 12, 12, 12)
        mapping_layout.setSpacing(10)

        info = QLabel("Map each csv2ofx field to a source CSV column. Different banks can use different mappings.")
        info.setWordWrap(True)
        info.setObjectName("section_hint")
        mapping_layout.addWidget(info)

        mapping_grid = QGridLayout()
        mapping_grid.setHorizontalSpacing(18)
        mapping_grid.setVerticalSpacing(8)
        mapping_grid.setColumnStretch(1, 1)
        mapping_grid.setColumnStretch(3, 1)

        left_column_fields = CSV2OFX_FIELD_LABELS[:6]
        right_column_fields = CSV2OFX_FIELD_LABELS[6:]
        max_rows = max(len(left_column_fields), len(right_column_fields))

        for row_idx in range(max_rows):
            if row_idx < len(left_column_fields):
                field_name, label = left_column_fields[row_idx]
                combo = QComboBox()
                combo.addItem("")
                combo.setMinimumWidth(180)
                combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.mapping_combos[field_name] = combo
                mapping_grid.addWidget(QLabel(label), row_idx, 0)
                mapping_grid.addWidget(combo, row_idx, 1)

            if row_idx < len(right_column_fields):
                field_name, label = right_column_fields[row_idx]
                combo = QComboBox()
                combo.addItem("")
                combo.setMinimumWidth(180)
                combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.mapping_combos[field_name] = combo
                mapping_grid.addWidget(QLabel(label), row_idx, 2)
                mapping_grid.addWidget(combo, row_idx, 3)

        mapping_layout.addLayout(mapping_grid)

        for field_name, label in CSV2OFX_FIELD_LABELS:
            combo = self.mapping_combos[field_name]
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

        self.use_split_amounts = QCheckBox("Use separate debit/credit columns for amount")
        self.use_split_amounts.toggled.connect(self._update_amount_mode)
        self.debit_col = QComboBox()
        self.credit_col = QComboBox()
        self.debit_col.setMinimumWidth(180)
        self.credit_col.setMinimumWidth(180)
        self.debit_col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.credit_col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        split_toggle_row = QHBoxLayout()
        split_toggle_row.addWidget(self.use_split_amounts)
        split_toggle_row.addStretch(1)
        mapping_layout.addLayout(split_toggle_row)

        split_form = QFormLayout()
        split_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        split_form.setHorizontalSpacing(12)
        split_form.setVerticalSpacing(8)
        split_form.addRow("Debit column", self.debit_col)
        split_form.addRow("Credit column", self.credit_col)
        mapping_layout.addLayout(split_form)

        profile_box = QGroupBox("Bank Profile")
        profile_form = QFormLayout(profile_box)
        profile_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        profile_form.setHorizontalSpacing(12)
        profile_form.setVerticalSpacing(10)

        self.bank_name_input = QLineEdit()
        self.bank_name_input.setMinimumWidth(300)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(300)
        self.profile_combo.currentIndexChanged.connect(self._apply_selected_profile)

        self.date_format_input = QLineEdit("%m/%d/%Y")
        self.date_format_input.setMaximumWidth(180)
        self.dayfirst_check = QCheckBox("Day-first dates")

        self.account_type_combo = QComboBox()
        self.account_type_combo.addItems(["CHECKING", "SAVINGS", "CREDITLINE"])
        self.account_type_combo.setMaximumWidth(180)

        self.account_id_input = QLineEdit()
        self.account_id_input.setMaximumWidth(220)
        self.currency_input = QLineEdit("USD")
        self.currency_input.setMaximumWidth(100)

        save_profile_btn = QPushButton("Save/Update Profile")
        save_profile_btn.clicked.connect(self.save_profile)
        save_profile_btn.setMinimumWidth(220)
        save_profile_btn.setMaximumWidth(260)
        save_profile_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        open_profiles_btn = QPushButton("Open Profiles File")
        open_profiles_btn.clicked.connect(self.open_profiles_file)
        open_profiles_btn.setMinimumWidth(180)
        open_profiles_btn.setMaximumWidth(220)
        open_profiles_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        profile_form.addRow("Profile name", self.bank_name_input)
        profile_form.addRow("Load saved profile", self.profile_combo)
        profile_form.addRow("Date parse format", self.date_format_input)
        profile_form.addRow(self.dayfirst_check)
        profile_form.addRow("Account type", self.account_type_combo)
        profile_form.addRow("Account ID", self.account_id_input)
        profile_form.addRow("Currency", self.currency_input)
        save_btn_row = QHBoxLayout()
        save_btn_row.addStretch(1)
        save_btn_row.addWidget(open_profiles_btn)
        save_btn_row.addSpacing(8)
        save_btn_row.addWidget(save_profile_btn)
        save_btn_row.addStretch(1)
        profile_form.addRow(save_btn_row)

        action_box = QGroupBox("Convert")
        action_layout = QHBoxLayout(action_box)
        action_layout.setSpacing(10)
        preview_btn = QPushButton("Preview OFX")
        preview_btn.clicked.connect(self.preview_ofx)
        convert_btn = QPushButton("Convert CSV -> OFX")
        convert_btn.clicked.connect(self.convert_to_ofx)
        action_layout.addStretch(1)
        action_layout.addWidget(preview_btn)
        action_layout.addWidget(convert_btn)
        action_layout.addStretch(1)

        root.addWidget(file_box)
        root.addWidget(mapping_box)
        root.addWidget(profile_box)
        root.addWidget(action_box)
        root.addStretch(1)

        self._update_amount_mode(self.use_split_amounts.isChecked())

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
