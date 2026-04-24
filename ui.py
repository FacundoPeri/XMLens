from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

from transformer import DEFAULT_OUTPUT_DIR, XmlTransformer

# ── Palette ───────────────────────────────────────────────────────────────────
_BG      = "#f4f6f9"
_SURFACE = "#ffffff"
_BORDER  = "#dde1e7"
_ACCENT  = "#374151"
_ACCENTH = "#1f2937"
_TEXT    = "#1c2331"
_MUTED   = "#6b7280"
_LOG_BG  = "#f9fafb"
_LOG_FG  = "#374151"
_BTN2    = "#e5e7eb"
_BTN2H   = "#d1d5db"

_SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


def _open_path(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class _TransformWorker(QThread):
    finished = pyqtSignal(object)
    failed   = pyqtSignal(Exception)

    def __init__(self, transformer: XmlTransformer, xml_path: Path, output_dir: Path) -> None:
        super().__init__()
        self._transformer = transformer
        self._xml_path    = xml_path
        self._output_dir  = output_dir

    def run(self) -> None:
        try:
            result = self._transformer.transform(self._xml_path, output_dir=self._output_dir)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section_lbl(text: str) -> QLabel:
    lbl = QLabel(f"▸  {text}")
    lbl.setStyleSheet(f"color:{_MUTED}; font-size:8pt; font-weight:bold; background:transparent;")
    return lbl


def _primary_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(f"""
        QPushButton          {{ background:{_ACCENT};  color:#fff; border:none; padding:8px 16px; font-size:10pt; }}
        QPushButton:hover    {{ background:{_ACCENTH}; }}
        QPushButton:disabled {{ background:{_BTN2};    color:{_MUTED}; }}
    """)
    return btn


def _secondary_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(f"""
        QPushButton          {{ background:{_BTN2};  color:{_TEXT}; border:none; padding:8px 16px; font-size:10pt; }}
        QPushButton:hover    {{ background:{_BTN2H}; }}
        QPushButton:disabled {{ background:{_BTN2};  color:{_MUTED}; }}
    """)
    return btn


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setStyleSheet(f"QFrame#card {{ background:{_SURFACE}; border:1px solid {_BORDER}; }}")
    return f


# ── Main window ───────────────────────────────────────────────────────────────

class XmlVisualizerApp(QMainWindow):
    def __init__(self, transformer: XmlTransformer) -> None:
        super().__init__()
        self.transformer    = transformer
        self.selected_file: Optional[Path] = None
        self.output_dir: Path = DEFAULT_OUTPUT_DIR
        self._worker: Optional[_TransformWorker] = None
        self._spin_idx = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._advance_spinner)

        self.setWindowTitle("Visualizador de XMLS")
        self.resize(1200, 700)
        self.setMinimumSize(800, 500)
        self.setStyleSheet(f"background:{_BG};")
        self._build_interface()
        self.showMaximized()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_interface(self) -> None:
        self._build_menu()

        root = QWidget()
        root.setStyleSheet(f"background:{_BG};")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        accent_line = QFrame()
        accent_line.setFixedHeight(2)
        accent_line.setStyleSheet(f"background:{_ACCENT}; border:none;")
        layout.addWidget(accent_line)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(f"""
            QSplitter         {{ background:{_BG}; }}
            QSplitter::handle {{ background:{_BORDER}; }}
        """)

        controls = self._build_controls()
        controls.setMinimumWidth(320)
        self._splitter.addWidget(controls)

        self._viewer = QWebEngineView()
        self._viewer.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._viewer.setStyleSheet("border:none;")
        self._viewer.setVisible(False)
        self._viewer.setMinimumWidth(300)
        self._splitter.addWidget(self._viewer)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 2)

        layout.addWidget(self._splitter, stretch=1)
        self.setCentralWidget(root)

    def _build_menu(self) -> None:
        bar = self.menuBar()
        bar.setStyleSheet(f"""
            QMenuBar                {{ background:{_SURFACE}; color:{_TEXT}; padding:2px 0; }}
            QMenuBar::item          {{ padding:4px 10px; }}
            QMenuBar::item:selected {{ background:{_ACCENT}; color:#fff; }}
            QMenu                   {{ background:{_SURFACE}; color:{_TEXT}; border:1px solid {_BORDER}; }}
            QMenu::item             {{ padding:6px 20px; }}
            QMenu::item:selected    {{ background:{_ACCENT}; color:#fff; }}
        """)
        file_menu = bar.addMenu("Archivo")
        open_act  = QAction("Abrir XML…", self)
        open_act.triggered.connect(self._select_file)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        quit_act = QAction("Salir", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        help_menu = bar.addMenu("Ayuda")
        about_act = QAction("Acerca de", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{_SURFACE};")
        row = QHBoxLayout(hdr)
        row.setContentsMargins(20, 0, 20, 0)

        title = QLabel("Visualizador de XMLS")
        title.setStyleSheet(f"color:{_TEXT}; font-size:14pt; font-weight:bold;")
        row.addWidget(title)

        sub = QLabel("XML  ·  XSLT  ·  HTML")
        sub.setStyleSheet(f"color:{_MUTED}; font-size:10pt;")
        row.addWidget(sub)
        row.addStretch()
        return hdr

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background:{_BG};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(0)

        layout.addWidget(_section_lbl("ARCHIVO XML"))
        layout.addSpacing(4)
        layout.addWidget(self._build_file_row())
        layout.addSpacing(12)

        layout.addWidget(_section_lbl("URL DE XSLT"))
        layout.addSpacing(4)
        layout.addWidget(self._build_xslt_row())
        layout.addSpacing(12)

        layout.addWidget(_section_lbl("CARPETA DE SALIDA"))
        layout.addSpacing(4)
        layout.addWidget(self._build_output_row())
        layout.addSpacing(16)

        layout.addWidget(self._build_actions())
        layout.addSpacing(16)

        layout.addWidget(self._build_log(), stretch=1)
        return panel

    def _build_file_row(self) -> QFrame:
        card = _card()
        row  = QHBoxLayout(card)
        row.setContentsMargins(12, 6, 6, 6)

        self._file_label = QLabel("Ningún archivo seleccionado.")
        self._file_label.setStyleSheet(f"color:{_MUTED}; font-size:10pt; border:none; background:transparent;")
        row.addWidget(self._file_label, stretch=1)

        open_btn = _secondary_btn("⧉  Abrir")
        open_btn.clicked.connect(self._open_selected_file)
        row.addWidget(open_btn)

        sel_btn = _primary_btn("＋  Seleccionar")
        sel_btn.clicked.connect(self._select_file)
        row.addWidget(sel_btn)
        return card

    def _build_xslt_row(self) -> QFrame:
        card = _card()
        row  = QHBoxLayout(card)
        row.setContentsMargins(12, 2, 12, 2)

        self._xslt_entry = QLineEdit()
        self._xslt_entry.setStyleSheet(f"""
            QLineEdit {{ background:transparent; border:none; color:{_TEXT}; font-size:10pt; padding:9px 0; }}
        """)
        row.addWidget(self._xslt_entry)
        return card

    def _build_output_row(self) -> QFrame:
        card = _card()
        row  = QHBoxLayout(card)
        row.setContentsMargins(12, 6, 6, 6)

        self._output_label = QLabel(str(self.output_dir))
        self._output_label.setStyleSheet(f"color:{_MUTED}; font-size:10pt; border:none; background:transparent;")
        row.addWidget(self._output_label, stretch=1)

        change_btn = _secondary_btn("📁  Cambiar")
        change_btn.clicked.connect(self._select_output_folder)
        row.addWidget(change_btn)
        return card

    def _build_actions(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background:{_BG};")
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self._convert_btn = _primary_btn("▶   Transformar")
        self._convert_btn.clicked.connect(self._convert_and_open)
        row.addWidget(self._convert_btn, stretch=1)

        folder_btn = _secondary_btn("📂  Abrir carpeta de salida")
        folder_btn.clicked.connect(self._open_output_folder)
        row.addWidget(folder_btn, stretch=1)
        return widget

    def _build_log(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet(f"background:{_BG};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hdr = QWidget()
        hdr.setStyleSheet(f"background:{_BG};")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(0, 0, 0, 0)

        hdr_row.addWidget(_section_lbl("REGISTRO DE ACTIVIDAD"))
        hdr_row.addStretch()

        clear_btn = _secondary_btn("🗑  Limpiar")
        clear_btn.clicked.connect(self._clear_log)
        hdr_row.addWidget(clear_btn)
        layout.addWidget(hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.document().setDocumentMargin(10)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background:{_LOG_BG}; color:{_LOG_FG};
                border:1px solid {_BORDER};
                font-family:Consolas; font-size:9pt;
            }}
        """)
        layout.addWidget(self._log, stretch=1)
        return container

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar XML", "", "Archivos XML (*.xml)")
        if not path:
            return
        self.selected_file = Path(path)
        self._file_label.setText(self.selected_file.name)
        self._file_label.setStyleSheet(f"color:{_TEXT}; font-size:10pt; border:none; background:transparent;")
        self._log_append(f"Seleccionado: {self.selected_file}")
        self._refresh_xslt_url()

    def _refresh_xslt_url(self) -> None:
        url = XmlTransformer.extract_xslt_url(self.selected_file) or ""
        self.transformer.xslt_url = url
        self._xslt_entry.setText(url)
        if url:
            self._log_append(f"XSLT detectado: {url}")
        else:
            self._log_append("No se encontró una URL de XSLT en el archivo.")

    def _open_selected_file(self) -> None:
        if not self.selected_file or not self.selected_file.exists():
            QMessageBox.warning(self, "Atención", "No hay un archivo XML válido seleccionado.")
            return
        _open_path(self.selected_file)
        self._log_append(f"Abriendo: {self.selected_file}")

    def _select_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de salida", str(self.output_dir))
        if not folder:
            return
        self.output_dir = Path(folder)
        self._output_label.setText(str(self.output_dir))
        self._log_append(f"Carpeta de salida: {self.output_dir}")

    def _convert_and_open(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if not self.selected_file:
            QMessageBox.warning(self, "Atención", "Selecciona un archivo XML primero.")
            return
        self.transformer.xslt_url = self._xslt_entry.text().strip() or self.transformer.xslt_url
        if not self.transformer.xslt_url:
            QMessageBox.warning(self, "Atención", "Ingresa una URL de XSLT válida.")
            return

        self._convert_btn.setEnabled(False)
        self._log_append("Iniciando transformación…")
        self._spin_idx = 0
        self._spin_timer.start(80)

        self._worker = _TransformWorker(self.transformer, self.selected_file, self.output_dir)
        self._worker.finished.connect(self._on_transform_done)
        self._worker.failed.connect(self._on_transform_error)
        self._worker.start()

    def _advance_spinner(self) -> None:
        self._convert_btn.setText(f"{_SPINNER[self._spin_idx]}   Transformando…")
        self._spin_idx = (self._spin_idx + 1) % len(_SPINNER)

    def _on_transform_done(self, result_path: Path) -> None:
        self._spin_timer.stop()
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("▶   Transformar")
        self._log_append(f"Generado: {result_path}")
        self._show_in_viewer(result_path)

    def _on_transform_error(self, error: Exception) -> None:
        self._spin_timer.stop()
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("▶   Transformar")
        QMessageBox.critical(self, "Error", str(error))
        self._log_append(f"Error: {error}")

    def _show_in_viewer(self, path: Path) -> None:
        if not self._viewer.isVisible():
            self._viewer.setVisible(True)
            w = self._splitter.width()
            self._splitter.setSizes([w // 3, 2 * w // 3])
        self._viewer.load(QUrl.fromLocalFile(str(path)))
        self._log_append("Resultado cargado en el visor.")

    def _open_output_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        _open_path(self.output_dir)
        self._log_append(f"Carpeta de salida abierta: {self.output_dir}")

    def _clear_log(self) -> None:
        self._log.clear()
        self._log_append("Registro limpiado.")

    def _log_append(self, message: str) -> None:
        self._log.append(f"›  {message}")

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "Acerca de",
            "Visualizador de XMLS\n\nUna aplicación ligera para transformar XML con XSLT"
            " y revisar el resultado HTML.\n\nDesarrollado como un ejemplo profesional de interfaz minimalista.",
        )
