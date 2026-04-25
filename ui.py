from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QSettings, QTimer, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSplitter,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from transformer import DEFAULT_OUTPUT_DIR, XmlTransformer

_SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


# ── Themes ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Theme:
    bg: str; surface: str; border: str
    accent: str; accent_h: str
    text: str; muted: str
    log_bg: str; log_fg: str
    btn2: str; btn2h: str


LIGHT = _Theme(
    bg="#f4f6f9",  surface="#ffffff",  border="#dde1e7",
    accent="#374151", accent_h="#1f2937",
    text="#1c2331",  muted="#6b7280",
    log_bg="#f9fafb", log_fg="#374151",
    btn2="#e5e7eb",  btn2h="#d1d5db",
)

DARK = _Theme(
    bg="#1a1d23",  surface="#22262f",  border="#383d49",
    accent="#4a5568", accent_h="#5a6478",
    text="#e2e8f0",  muted="#94a3b8",
    log_bg="#1e2128", log_fg="#cbd5e1",
    btn2="#2d3240",  btn2h="#363c4e",
)


def _make_qss(t: _Theme) -> str:
    return f"""
        QMainWindow               {{ background: {t.bg}; }}
        QWidget#bg                {{ background: {t.bg}; }}
        QWidget#surface           {{ background: {t.surface}; }}
        QStackedWidget            {{ background: {t.bg}; }}

        QFrame#card               {{ background: {t.surface}; border: 1px solid {t.border}; }}
        QFrame#line               {{ background: {t.border};  border: none; }}
        QFrame#accent             {{ background: {t.accent};  border: none; }}

        QLabel#header-title       {{ color: {t.text};    font-size: 14pt; font-weight: bold; background: transparent; }}
        QLabel#header-sub         {{ color: {t.muted};   font-size: 10pt; background: transparent; }}
        QLabel#section            {{ color: {t.muted};   font-size: 8pt;  font-weight: bold; background: transparent; }}
        QLabel#muted              {{ color: {t.muted};   font-size: 10pt; background: transparent; }}
        QLabel#text               {{ color: {t.text};    font-size: 10pt; background: transparent; }}
        QLabel#viewer-filename    {{ color: {t.muted};   font-size: 9pt;  background: transparent; border: none; }}
        QLabel#placeholder-icon   {{ color: {t.border};  font-size: 28pt; font-weight: bold; background: transparent; }}
        QLabel#placeholder-text   {{ color: {t.muted};   font-size: 10pt; background: transparent; }}

        QLineEdit                 {{ background: transparent; border: none; color: {t.text}; font-size: 10pt; padding: 9px 0; }}

        QTextEdit#log             {{ background: {t.log_bg}; color: {t.log_fg}; border: 1px solid {t.border}; font-family: Consolas; font-size: 9pt; }}

        QPushButton#primary            {{ background: {t.accent};   color: #ffffff; border: none; padding: 8px 16px; font-size: 10pt; }}
        QPushButton#primary:hover      {{ background: {t.accent_h}; color: #ffffff; }}
        QPushButton#primary:disabled   {{ background: {t.btn2};     color: {t.muted}; }}
        QPushButton#secondary          {{ background: {t.btn2};  color: {t.text}; border: none; padding: 8px 16px; font-size: 10pt; }}
        QPushButton#secondary:hover    {{ background: {t.btn2h}; color: {t.text}; }}
        QPushButton#secondary:disabled {{ background: {t.btn2};  color: {t.muted}; }}
        QPushButton#theme-toggle       {{ background: transparent; border: none; color: {t.muted}; font-size: 14pt; padding: 4px 8px; }}
        QPushButton#theme-toggle:hover {{ color: {t.text}; background: transparent; }}

        QSplitter#main            {{ background: {t.bg}; }}
        QSplitter#main::handle    {{ background: {t.border}; }}

        QMenuBar                  {{ background: {t.surface}; color: {t.text}; padding: 2px 0; }}
        QMenuBar::item            {{ padding: 4px 10px; }}
        QMenuBar::item:selected   {{ background: {t.accent}; color: #ffffff; }}
        QMenu                     {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border}; }}
        QMenu::item               {{ padding: 6px 20px; }}
        QMenu::item:selected      {{ background: {t.accent}; color: #ffffff; }}

        QScrollBar:vertical                              {{ background: {t.surface}; width: 8px; border: none; }}
        QScrollBar::handle:vertical                      {{ background: {t.border}; border-radius: 4px; min-height: 20px; }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical                    {{ height: 0; }}
        QScrollBar:horizontal                            {{ background: {t.surface}; height: 8px; border: none; }}
        QScrollBar::handle:horizontal                    {{ background: {t.border}; border-radius: 4px; min-width: 20px; }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal                  {{ width: 0; }}
    """


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_path(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _section_lbl(text: str) -> QLabel:
    lbl = QLabel(f"▸  {text}")
    lbl.setObjectName("section")
    return lbl


def _primary_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("primary")
    return btn


def _secondary_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("secondary")
    return btn


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


# ── Worker ────────────────────────────────────────────────────────────────────

class _TransformWorker(QThread):
    finished = pyqtSignal(object, object)  # (Path, list[str] warnings)
    failed   = pyqtSignal(Exception)

    def __init__(self, transformer: XmlTransformer, xml_path: Path, output_dir: Path) -> None:
        super().__init__()
        self._transformer = transformer
        self._xml_path    = xml_path
        self._output_dir  = output_dir

    def run(self) -> None:
        try:
            result_path, warnings = self._transformer.transform(self._xml_path, output_dir=self._output_dir)
            self.finished.emit(result_path, warnings)
        except Exception as exc:
            self.failed.emit(exc)


# ── Main window ───────────────────────────────────────────────────────────────

class XmlVisualizerApp(QMainWindow):
    def __init__(self, transformer: XmlTransformer) -> None:
        super().__init__()
        self.transformer   = transformer
        self.selected_file: Optional[Path] = None
        self.output_dir: Path = DEFAULT_OUTPUT_DIR
        self._worker: Optional[_TransformWorker] = None
        self._spin_idx = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._advance_spinner)
        self._theme = LIGHT

        self.setWindowTitle("Visualizador de XMLS")
        self.resize(1200, 700)
        self.setMinimumSize(800, 500)
        self.setAcceptDrops(True)
        self._build_interface()
        self._apply_theme(LIGHT)
        self._restore_settings()
        self.showMaximized()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_interface(self) -> None:
        self._build_menu()

        root = QWidget()
        root.setObjectName("bg")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        accent_line = QFrame()
        accent_line.setObjectName("accent")
        accent_line.setFixedHeight(2)
        layout.addWidget(accent_line)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("main")
        self._splitter.setHandleWidth(1)

        controls = self._build_controls()
        controls.setMinimumWidth(320)
        self._splitter.addWidget(controls)

        right_panel = self._build_viewer_panel()
        right_panel.setMinimumWidth(300)
        self._splitter.addWidget(right_panel)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 2)

        layout.addWidget(self._splitter, stretch=1)
        self.setCentralWidget(root)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Archivo")
        open_act  = QAction("Abrir XML…", self)
        open_act.triggered.connect(self._select_file)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        quit_act = QAction("Salir", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        help_menu = self.menuBar().addMenu("Ayuda")
        about_act = QAction("Acerca de", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setObjectName("surface")
        hdr.setFixedHeight(52)
        row = QHBoxLayout(hdr)
        row.setContentsMargins(20, 0, 12, 0)

        title = QLabel("Visualizador de XMLS")
        title.setObjectName("header-title")
        row.addWidget(title)

        sub = QLabel("XML  ·  XSLT  ·  HTML")
        sub.setObjectName("header-sub")
        row.addWidget(sub)
        row.addStretch()

        self._theme_btn = QPushButton("🌙")
        self._theme_btn.setObjectName("theme-toggle")
        self._theme_btn.setFixedSize(36, 36)
        self._theme_btn.clicked.connect(self._toggle_theme)
        row.addWidget(self._theme_btn)

        return hdr

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("bg")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(0)

        layout.addWidget(_section_lbl("ARCHIVO XML"))
        layout.addSpacing(4)
        layout.addWidget(self._build_file_row())
        layout.addSpacing(12)

        layout.addWidget(_section_lbl("URL / RUTA DE XSLT"))
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

    def _build_viewer_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("bg")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._viewer_header = QWidget()
        self._viewer_header.setObjectName("bg")
        hdr_inner = QWidget()
        hdr_inner.setObjectName("surface")
        hdr_row = QHBoxLayout(hdr_inner)
        hdr_row.setContentsMargins(16, 8, 8, 8)

        self._viewer_filename = QLabel("")
        self._viewer_filename.setObjectName("viewer-filename")
        hdr_row.addWidget(self._viewer_filename, stretch=1)

        close_btn = _secondary_btn("✕  Cerrar visor")
        close_btn.clicked.connect(self._close_viewer)
        hdr_row.addWidget(close_btn)

        hdr_layout = QVBoxLayout(self._viewer_header)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(0)
        hdr_layout.addWidget(hdr_inner)

        sep = QFrame()
        sep.setObjectName("line")
        sep.setFixedHeight(1)
        hdr_layout.addWidget(sep)

        self._viewer_header.setVisible(False)
        layout.addWidget(self._viewer_header)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_placeholder())

        self._viewer = QWebEngineView()
        self._viewer.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._viewer.setStyleSheet("border:none;")
        self._viewer.load(QUrl("about:blank"))
        self._stack.addWidget(self._viewer)

        layout.addWidget(self._stack, stretch=1)
        return panel

    def _build_placeholder(self) -> QWidget:
        w = QWidget()
        w.setObjectName("bg")
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        icon = QLabel("XML → HTML")
        icon.setObjectName("placeholder-icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        text = QLabel("Seleccioná un XML y transformalo\npara ver el resultado aquí\n\nTambién podés arrastrar un archivo .xml")
        text.setObjectName("placeholder-text")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)

        return w

    def _build_file_row(self) -> QFrame:
        card = _card()
        row  = QHBoxLayout(card)
        row.setContentsMargins(12, 6, 6, 6)

        self._file_label = QLabel("Ningún archivo seleccionado.")
        self._file_label.setObjectName("muted")
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
        row.setContentsMargins(12, 2, 6, 2)
        self._xslt_entry = QLineEdit()
        row.addWidget(self._xslt_entry, stretch=1)
        local_btn = _secondary_btn("📁  Local")
        local_btn.clicked.connect(self._select_local_xslt)
        row.addWidget(local_btn)
        return card

    def _build_output_row(self) -> QFrame:
        card = _card()
        row  = QHBoxLayout(card)
        row.setContentsMargins(12, 6, 6, 6)

        self._output_label = QLabel(str(self.output_dir))
        self._output_label.setObjectName("muted")
        row.addWidget(self._output_label, stretch=1)

        change_btn = _secondary_btn("📁  Cambiar")
        change_btn.clicked.connect(self._select_output_folder)
        row.addWidget(change_btn)
        return card

    def _build_actions(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("bg")
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
        container.setObjectName("bg")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hdr = QWidget()
        hdr.setObjectName("bg")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(0, 0, 0, 0)
        hdr_row.addWidget(_section_lbl("REGISTRO DE ACTIVIDAD"))
        hdr_row.addStretch()
        clear_btn = _secondary_btn("🗑  Limpiar")
        clear_btn.clicked.connect(self._clear_log)
        hdr_row.addWidget(clear_btn)
        layout.addWidget(hdr)

        self._log = QTextEdit()
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.document().setDocumentMargin(10)
        layout.addWidget(self._log, stretch=1)
        return container

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self, theme: _Theme) -> None:
        self._theme = theme
        QApplication.instance().setStyleSheet(_make_qss(theme))

    def _toggle_theme(self) -> None:
        new = DARK if self._theme is LIGHT else LIGHT
        self._apply_theme(new)
        self._theme_btn.setText("☀" if new is DARK else "🌙")

    # ── Settings ──────────────────────────────────────────────────────────────

    def _save_settings(self) -> None:
        s = QSettings("XMLens", "XMLens")
        s.setValue("output_dir", str(self.output_dir))
        s.setValue("xslt_url", self._xslt_entry.text())
        s.setValue("splitter_state", self._splitter.saveState())
        s.setValue("theme", "dark" if self._theme is DARK else "light")

    def _restore_settings(self) -> None:
        s = QSettings("XMLens", "XMLens")

        output_dir = s.value("output_dir")
        if output_dir and Path(output_dir).exists():
            self.output_dir = Path(output_dir)
            self._output_label.setText(str(self.output_dir))

        xslt_url = s.value("xslt_url", "")
        if xslt_url:
            self._xslt_entry.setText(xslt_url)
            self.transformer.xslt_url = xslt_url

        state = s.value("splitter_state")
        if state:
            self._splitter.restoreState(state)

        if s.value("theme") == "dark":
            self._apply_theme(DARK)
            self._theme_btn.setText("☀")

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith(".xml") for u in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path_str = url.toLocalFile()
            if path_str.lower().endswith(".xml"):
                self._load_xml_file(Path(path_str))
                break

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar XML", "", "Archivos XML (*.xml)")
        if path:
            self._load_xml_file(Path(path))

    def _load_xml_file(self, path: Path) -> None:
        self.selected_file = path
        self._file_label.setText(path.name)
        self._file_label.setObjectName("text")
        self._file_label.style().unpolish(self._file_label)
        self._file_label.style().polish(self._file_label)
        self._log_append(f"Seleccionado: {path}")
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

    def _select_local_xslt(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar XSLT local", "", "Archivos XSLT (*.xsl *.xslt)"
        )
        if path:
            self._xslt_entry.setText(path)
            self.transformer.xslt_url = path
            self._log_append(f"XSLT local: {Path(path).name}")

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

    def _on_transform_done(self, result_path: Path, warnings: List[str]) -> None:
        self._spin_timer.stop()
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("▶   Transformar")
        self._log_append(f"Generado: {result_path}")
        for w in warnings:
            self._log_append(f"⚠  XSLT: {w}")
        self._show_in_viewer(result_path)

    def _on_transform_error(self, error: Exception) -> None:
        self._spin_timer.stop()
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("▶   Transformar")
        QMessageBox.critical(self, "Error", str(error))
        self._log_append(f"Error: {error}")

    def _show_in_viewer(self, path: Path) -> None:
        self._viewer_filename.setText(path.name)
        self._viewer_header.setVisible(True)
        self._viewer.load(QUrl.fromLocalFile(str(path)))
        self._stack.setCurrentIndex(1)
        self._log_append("Resultado cargado en el visor.")

    def _close_viewer(self) -> None:
        self._stack.setCurrentIndex(0)
        self._viewer_header.setVisible(False)
        self._viewer.setUrl(QUrl("about:blank"))
        self._log_append("Visor cerrado.")

    def _open_output_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        _open_path(self.output_dir)
        self._log_append(f"Carpeta de salida abierta: {self.output_dir}")

    def _clear_log(self) -> None:
        self._log.clear()
        self._log_append("Registro limpiado.")

    def _log_append(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}]  ›  {message}")

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "Acerca de",
            "Visualizador de XMLS\n\nUna aplicación ligera para transformar XML con XSLT"
            " y revisar el resultado HTML.\n\nDesarrollado como un ejemplo profesional de interfaz minimalista.",
        )

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
