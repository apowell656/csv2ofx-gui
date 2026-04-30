#!/usr/bin/env bash
set -euo pipefail

APP_ID="openstatement"
APP_NAME="OpenStatement"
MAINTAINER="OpenStatement Maintainers"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name"
    echo "Install it with: $install_hint"
    exit 1
  fi
}

read_project_version() {
  python3 - <<'PY'
from pathlib import Path

for line in Path("pyproject.toml").read_text(encoding="utf-8").splitlines():
    if line.strip().startswith("version"):
        print(line.split("=", 1)[1].strip().strip('"'))
        break
PY
}

deb_to_appimage_arch() {
  case "$1" in
    amd64) echo "x86_64" ;;
    arm64) echo "aarch64" ;;
    *) echo "$1" ;;
  esac
}

VERSION="${1:-$(read_project_version)}"
if [[ -z "$VERSION" ]]; then
  echo "Could not read project version from pyproject.toml"
  exit 1
fi
DEB_ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
APPIMAGE_ARCH="$(deb_to_appimage_arch "$DEB_ARCH")"
PACKAGE_DIR="$ROOT_DIR/dist/packages"
TOOLS_DIR="$ROOT_DIR/packaging/tools"
DEB_ROOT="$ROOT_DIR/packaging/deb/${APP_ID}_${VERSION}_${DEB_ARCH}"
APPDIR="$ROOT_DIR/packaging/AppDir"
APPIMAGETOOL="$TOOLS_DIR/appimagetool-x86_64.AppImage"

require_command python3 "sudo apt install -y python3 python3-venv python3-pip"
require_command dpkg-deb "sudo apt install -y dpkg"
require_command fakeroot "sudo apt install -y fakeroot"
require_command desktop-file-validate "sudo apt install -y desktop-file-utils"

echo "Using version: $VERSION"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

echo "Building PyInstaller bundle..."
rm -rf build dist
.venv/bin/pyinstaller --clean OpenStatement.spec

if [[ ! -x dist/OpenStatement/OpenStatement ]]; then
  echo "PyInstaller output was not found at dist/OpenStatement/OpenStatement"
  exit 1
fi

mkdir -p "$PACKAGE_DIR"

echo "Building .deb package..."
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/opt/$APP_NAME"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps"

cp -a dist/OpenStatement/. "$DEB_ROOT/opt/$APP_NAME/"
cp openstatement/build_assets/icons/icon.iconset/icon_512x512.png \
  "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps/$APP_ID.png"

cat > "$DEB_ROOT/usr/bin/$APP_ID" <<EOF
#!/usr/bin/env sh
exec /opt/$APP_NAME/$APP_NAME "\$@"
EOF
chmod 0755 "$DEB_ROOT/usr/bin/$APP_ID"

cat > "$DEB_ROOT/usr/share/applications/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Convert bank CSV exports to OFX files
Exec=$APP_ID
Icon=$APP_ID
Terminal=false
Categories=Office;Finance;
StartupWMClass=$APP_NAME
EOF

cat > "$DEB_ROOT/DEBIAN/control" <<EOF
Package: $APP_ID
Version: $VERSION
Section: utils
Priority: optional
Architecture: $DEB_ARCH
Maintainer: $MAINTAINER
Depends: libc6, libglib2.0-0, libgl1, libegl1, libxkbcommon-x11-0, libxcb-cursor0, libxcb-xinerama0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0
Description: Desktop app to convert bank CSV exports to OFX files
 $APP_NAME helps map messy bank CSV exports and convert them into OFX files for personal finance tools.
EOF

fakeroot dpkg-deb --build "$DEB_ROOT" "$PACKAGE_DIR/${APP_ID}_${VERSION}_${DEB_ARCH}.deb"

echo "Building AppImage..."
mkdir -p "$TOOLS_DIR"
if [[ ! -x "$APPIMAGETOOL" ]]; then
  if command -v wget >/dev/null 2>&1; then
    wget -O "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
  elif command -v curl >/dev/null 2>&1; then
    curl -L "$APPIMAGETOOL_URL" -o "$APPIMAGETOOL"
  else
    echo "Missing wget or curl to download appimagetool."
    echo "Install one with: sudo apt install -y wget"
    exit 1
  fi
  chmod +x "$APPIMAGETOOL"
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/opt/$APP_NAME"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/512x512/apps"

cp -a dist/OpenStatement/. "$APPDIR/opt/$APP_NAME/"
cp openstatement/build_assets/icons/icon.iconset/icon_512x512.png \
  "$APPDIR/usr/share/icons/hicolor/512x512/apps/$APP_ID.png"
cp "$APPDIR/usr/share/icons/hicolor/512x512/apps/$APP_ID.png" "$APPDIR/$APP_ID.png"

cat > "$APPDIR/AppRun" <<EOF
#!/usr/bin/env sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/opt/$APP_NAME/$APP_NAME" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Convert bank CSV exports to OFX files
Exec=$APP_NAME
Icon=$APP_ID
Terminal=false
Categories=Office;Finance;
StartupWMClass=$APP_NAME
EOF

cp "$APPDIR/$APP_ID.desktop" "$APPDIR/usr/share/applications/$APP_ID.desktop"
desktop-file-validate "$APPDIR/$APP_ID.desktop"

APPIMAGE_OUTPUT="$PACKAGE_DIR/${APP_NAME}-${VERSION}-${APPIMAGE_ARCH}.AppImage"
ARCH="$APPIMAGE_ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_OUTPUT"
chmod +x "$APPIMAGE_OUTPUT"

echo
echo "Release artifacts:"
echo "  $PACKAGE_DIR/${APP_ID}_${VERSION}_${DEB_ARCH}.deb"
echo "  $APPIMAGE_OUTPUT"
echo
echo "Test AppImage:"
echo "  $APPIMAGE_OUTPUT"
echo
echo "If the AppImage reports a FUSE error, install libfuse2 or libfuse2t64."
echo "Fallback without FUSE:"
echo "  APPIMAGE_EXTRACT_AND_RUN=1 $APPIMAGE_OUTPUT"
