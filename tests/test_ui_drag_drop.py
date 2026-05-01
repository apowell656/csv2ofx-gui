from pathlib import Path

from openstatement.ui.main_window import MainWindow


def test_load_dropped_file_loads_csv(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    csv_path = tmp_path / "dropped.csv"
    csv_path.write_text("Date,Amount\n2026-01-01,10\n", encoding="utf-8")

    loaded = window._load_dropped_file(str(csv_path))

    assert loaded is True
    assert window.csv_path_input.text() == str(csv_path)
    assert window.current_headers == ["Date", "Amount"]


def test_load_dropped_file_rejects_missing_path(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    missing = tmp_path / "missing.csv"

    loaded = window._load_dropped_file(str(missing))

    assert loaded is False
