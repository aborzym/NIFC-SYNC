#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="3.0.0-beta.2"
package_name="nifc-sync_${version}_amd64.deb"
package_root="${project_dir}/build/linux-package"
application_dir="${package_root}/opt/nifc-sync"

if [[ ! -x "${project_dir}/.venv/bin/pyinstaller" ]]; then
    echo "Brak PyInstaller w .venv."
    echo "Uruchom: python -m pip install -r requirements-build.txt"
    exit 1
fi

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "Brak programu dpkg-deb."
    exit 1
fi

rm -rf "${project_dir}/build" "${project_dir}/dist"

"${project_dir}/.venv/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --windowed \
    --name "NIFC-SYNC" \
    --add-data "${project_dir}/assets:assets" \
    --distpath "${project_dir}/dist" \
    --workpath "${project_dir}/build/pyinstaller" \
    --specpath "${project_dir}/build" \
    "${project_dir}/app.py"

install -d \
    "${application_dir}" \
    "${package_root}/DEBIAN" \
    "${package_root}/usr/share/applications" \
    "${package_root}/usr/share/icons/hicolor/scalable/apps"

cp -a "${project_dir}/dist/NIFC-SYNC/." "${application_dir}/"
install -m 644 \
    "${project_dir}/packaging/linux/control" \
    "${package_root}/DEBIAN/control"
install -m 755 \
    "${project_dir}/packaging/linux/postinst" \
    "${package_root}/DEBIAN/postinst"
install -m 755 \
    "${project_dir}/packaging/linux/postrm" \
    "${package_root}/DEBIAN/postrm"
install -m 644 \
    "${project_dir}/packaging/linux/nifc-sync.desktop" \
    "${package_root}/usr/share/applications/nifc-sync.desktop"
install -m 644 \
    "${project_dir}/assets/nifc-sync.svg" \
    "${package_root}/usr/share/icons/hicolor/scalable/apps/nifc-sync.svg"

dpkg-deb --root-owner-group --build \
    "${package_root}" \
    "${project_dir}/dist/${package_name}"

echo
echo "GOTOWE: ${project_dir}/dist/${package_name}"
