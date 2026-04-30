import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / relative_path


def app_icon_path() -> Path | None:
    candidates = (
        "openstatement/build_assets/icons/openstatement_logo.ico",
        "openstatement/build_assets/icons/icon.iconset/icon_512x512.png",
    )
    for candidate in candidates:
        path = resource_path(candidate)
        if path.exists():
            return path
    return None
