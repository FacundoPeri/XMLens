from transformer import XmlTransformer
from ui import XmlVisualizerApp


def main() -> None:
    transformer = XmlTransformer()
    app = XmlVisualizerApp(transformer)
    app.mainloop()


if __name__ == "__main__":
    main()
