from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QComboBox, QMainWindow

from ..config.constants import APP_NAME
from ..models.profile import ProfileStore
from .sections.conversion import ConversionSectionMixin
from .sections.csv import CsvSectionMixin
from .sections.layout import UiSectionMixin
from .sections.profile import ProfileSectionMixin


class MainWindow(
    UiSectionMixin,
    CsvSectionMixin,
    ProfileSectionMixin,
    ConversionSectionMixin,
    QMainWindow,
):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1140, 900)
        self.setAcceptDrops(True)

        self.profile_store = ProfileStore()
        self.profiles = self.profile_store.load()
        self.current_headers: list[str] = []
        self.mapping_combos: dict[str, QComboBox] = {}

        self._build_ui()
        self._refresh_profile_combo()

    def _load_dropped_file(self, path: str) -> bool:
        candidate = Path(path)
        if not candidate.exists() or not candidate.is_file():
            return False
        self.csv_path_input.setText(str(candidate))
        self.status_label.setText(candidate.name)
        self.load_csv_headers(str(candidate))
        return True

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            event.ignore()
            return

        for url in mime.urls():
            if url.isLocalFile() and Path(url.toLocalFile()).is_file():
                event.acceptProposedAction()
                return

        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            event.ignore()
            return

        for url in mime.urls():
            if not url.isLocalFile():
                continue
            if self._load_dropped_file(url.toLocalFile()):
                event.setDropAction(Qt.CopyAction)
                event.accept()
                return

        event.ignore()
