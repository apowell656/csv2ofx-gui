from openstatement.ui.main_window import MainWindow


def test_main_window_constructs(qapp) -> None:
    window = MainWindow()
    assert "OpenStatement" in window.windowTitle()
    assert window.mapping_combos
