import sys

from PyQt6.QtWidgets import QApplication

from transformer import XmlTransformer
from ui import XmlVisualizerApp


def main() -> None:
    app = QApplication(sys.argv)
    transformer = XmlTransformer()
    _window = XmlVisualizerApp(transformer)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
