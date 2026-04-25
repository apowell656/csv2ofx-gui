APP_NAME = "OpenStatement CSV to OFX"

CSV2OFX_FIELD_LABELS = [
    ("date", "Date column (required)"),
    ("amount", "Amount column (required unless split)"),
    ("payee", "Payee column"),
    ("desc", "Description column"),
    ("notes", "Notes/Memo column"),
    ("check_num", "Check number column"),
    ("id", "Transaction ID column"),
    ("balance", "Balance column"),
    ("class", "Class column"),
    ("account", "Account column (optional override)"),
    ("bank", "Bank column (optional override)"),
]
