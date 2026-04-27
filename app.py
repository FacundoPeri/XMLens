import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from transformer import XmlTransformer
from ui import XmlVisualizerApp


def _base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


_ICON = _base_dir() / "assets" / "icon.png"


def main() -> None:
    app = QApplication(sys.argv)
    if _ICON.exists():
        app.setWindowIcon(QIcon(str(_ICON)))
    transformer = XmlTransformer()
    _window = XmlVisualizerApp(transformer)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
