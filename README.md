# OpenStatement

Desktop app to map bank CSV exports into OFX files (via `csv2ofx`).

## Run

From the repo root:

```bash
python3 openstatement_app.py
```

Or:

```bash
python3 -m openstatement
```

From the parent directory of the repo:

```bash
python3 -m openstatement
```

After install (`pip install -e .`):

```bash
openstatement
```

## Development Setup

For contributors who want to modify the repo:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

Install development/test dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest -q
```

## Troubleshooting

If you see:

`qt.qpa.plugin: Could not find the Qt platform plugin "cocoa"...`

reinstall PySide in your active venv:

```bash
python -m pip uninstall -y PySide6 PySide6_Addons PySide6_Essentials shiboken6
python -m pip install --no-cache-dir "PySide6==6.11.0"
```

Quick check:

```bash
python -c "from PySide6.QtWidgets import QApplication; app=QApplication([]); print('qapp ok')"
```

## Project Layout

```text
openstatement/
  app.py                     # Application entry function
  config/
    constants.py             # App/UI constants
  models/
    profile.py               # BankProfile + profile persistence
  services/
    conversion.py            # csv2ofx conversion + preview formatting
  ui/
    main_window.py           # Main window composition
    sections/
      layout.py              # UI widgets/layout assembly
      csv.py                 # CSV loading + auto mapping
      profile.py             # Profile load/save/validation
      conversion.py          # Convert/preview UI flow
openstatement_app.py         # Thin launcher script
```
