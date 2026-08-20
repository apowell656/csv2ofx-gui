# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH)
ICON_DIR = SPEC_DIR / "openstatement" / "build_assets" / "icons"
WINDOWS_ICON = ICON_DIR / "openstatement_logo.ico"
MAC_ICON = ICON_DIR / "openstatement_logo.icns"
MAC_ICON_PNG = ICON_DIR / "icon.iconset" / "icon_512x512.png"
MAC_ICON_PATH = str(MAC_ICON) if MAC_ICON.exists() else (str(MAC_ICON_PNG) if MAC_ICON_PNG.exists() else None)


a = Analysis(
    ['openstatement_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        (str(SPEC_DIR / 'openstatement' / 'ui' / 'assets' / 'chevron_down.svg'), 'openstatement/ui/assets'),
        (str(SPEC_DIR / 'openstatement' / 'ui' / 'assets' / 'chevron_up.svg'), 'openstatement/ui/assets'),
        (str(WINDOWS_ICON), 'openstatement/build_assets/icons'),
        (str(MAC_ICON_PNG), 'openstatement/build_assets/icons/icon.iconset'),
    ],
    hiddenimports=collect_submodules('csv2ofx'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == "win32":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        exclude_binaries=False,
        name='OpenStatement',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        onefile=True,
        icon=str(WINDOWS_ICON) if WINDOWS_ICON.exists() else None,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='OpenStatement',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        icon=MAC_ICON_PATH,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='OpenStatement',
    )

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name='OpenStatement.app',
        icon=MAC_ICON_PATH,
        bundle_identifier=None,
    )
