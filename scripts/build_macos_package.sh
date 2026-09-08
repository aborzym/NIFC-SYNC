#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="4.0.0"
iconset_dir="${project_dir}/build/NIFC-SYNC.iconset"
icon_path="${project_dir}/build/NIFC-SYNC.icns"
application_path="${project_dir}/dist/macos/NIFC-SYNC.app"
dmg_path="${project_dir}/dist/NIFC-SYNC-${version}-arm64.dmg"

if [[ "$(uname -m)" != "arm64" ]]; then
    echo "Pakiet macOS musi być budowany na Apple Silicon (arm64)."
    exit 1
fi

if [[ ! -x "${project_dir}/.venv/bin/pyinstaller" ]]; then
    echo "Brak PyInstaller w .venv."
    exit 1
fi

rm -rf \
    "${project_dir}/build/macos" \
    "${project_dir}/dist/macos" \
    "${iconset_dir}" \
    "${icon_path}" \
    "${dmg_path}"

QT_QPA_PLATFORM=offscreen \
    "${project_dir}/.venv/bin/python" \
    "${project_dir}/scripts/render_macos_icon.py" \
    "${project_dir}/assets/nifc-sync.svg" \
    "${iconset_dir}"

iconutil -c icns "${iconset_dir}" -o "${icon_path}"

"${project_dir}/.venv/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --windowed \
    --name "NIFC-SYNC" \
    --icon "${icon_path}" \
    --osx-bundle-identifier "pl.andrzejborzym.nifc-sync" \
    --target-architecture arm64 \
    --add-data "${project_dir}/assets:assets" \
    --distpath "${project_dir}/dist/macos" \
    --workpath "${project_dir}/build/macos/pyinstaller" \
    --specpath "${project_dir}/build/macos" \
    "${project_dir}/app.py"

codesign --force --deep --sign - "${application_path}"

hdiutil create \
    -volname "NIFC-SYNC" \
    -srcfolder "${application_path}" \
    -ov \
    -format UDZO \
    "${dmg_path}"

echo
echo "GOTOWE: ${dmg_path}"
