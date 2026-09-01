import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ICON_SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Użycie: render_macos_icon.py SOURCE.svg OUTPUT.iconset")

    application = QGuiApplication([])
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    destination.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(source))

    if not renderer.isValid():
        raise SystemExit(f"Nie można odczytać ikony SVG: {source}")

    for filename, size in ICON_SIZES.items():
        image = QImage(
            size,
            size,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()

        if not image.save(str(destination / filename)):
            raise SystemExit(f"Nie można zapisać: {filename}")

    application.quit()


if __name__ == "__main__":
    main()
