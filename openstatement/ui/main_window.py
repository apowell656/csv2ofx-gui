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
        self.resize(1040, 760)

        self.profile_store = ProfileStore()
        self.profiles = self.profile_store.load()
        self.current_headers: list[str] = []
        self.mapping_combos: dict[str, QComboBox] = {}

        self._build_ui()
        self._refresh_profile_combo()
