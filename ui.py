import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QSettings, QTimer, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import (
    QAction, QColor, QDesktopServices, QFont,
    QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat,
)
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSplitter, QStackedWidget,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from transformer import DEFAULT_OUTPUT_DIR, XmlTransformer

_SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_MAX_RECENT = 10


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
        QDialog                   {{ background: {t.bg}; color: {t.text}; }}
        QLabel                    {{ color: {t.text}; background: transparent; }}
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

        QPushButton                    {{ color: {t.text}; }}
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

        QTabWidget::pane          {{ border: 1px solid {t.border}; background: {t.surface}; }}
        QTabBar                   {{ background: {t.bg}; }}
        QTabBar::tab              {{ background: {t.btn2}; color: {t.muted}; padding: 5px 16px; border: 1px solid {t.border}; border-bottom: none; margin-right: 2px; }}
        QTabBar::tab:selected     {{ background: {t.surface}; color: {t.text}; }}
        QTabBar::tab:hover        {{ background: {t.btn2h}; color: {t.text}; }}

        QListWidget               {{ background: {t.surface}; border: 1px solid {t.border}; color: {t.text}; }}
        QListWidget::item:selected {{ background: {t.accent}; color: #ffffff; }}
        QListWidget::item:hover   {{ background: {t.btn2}; }}

        QProgressBar              {{ background: {t.btn2}; border: 1px solid {t.border}; border-radius: 3px; height: 8px; color: transparent; }}
        QProgressBar::chunk       {{ background: {t.accent}; border-radius: 3px; }}

        QMenuBar                  {{ background: {t.surface}; color: {t.text}; padding: 2px 0; }}
        QMenuBar::item            {{ padding: 4px 10px; }}
        QMenuBar::item:selected   {{ background: {t.accent}; color: #ffffff; }}
        QMenu                     {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border}; }}
        QMenu::item               {{ padding: 6px 20px; }}
        QMenu::item:selected      {{ background: {t.accent}; color: #ffffff; }}
        QMenu::item:disabled      {{ color: {t.muted}; }}

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


def _separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("line")
    sep.setFixedHeight(1)
    return sep


# ── XML syntax highlighter ────────────────────────────────────────────────────

class _XmlHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)

        def _fmt(color: str, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            return f

        self._rules = [
            (re.compile(r'<!--.*?-->'),      _fmt("#6a9955")),
            (re.compile(r'<\?.*?\?>'),       _fmt("#c586c0")),
            (re.compile(r'</?\w[\w:.-]*'),   _fmt("#569cd6")),
            (re.compile(r'\b[\w:.-]+='),     _fmt("#9cdcfe")),
            (re.compile(r'"[^"]*"'),         _fmt("#ce9178")),
            (re.compile(r"'[^']*'"),         _fmt("#ce9178")),
        ]

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── Workers ───────────────────────────────────────────────────────────────────

class _TransformWorker(QThread):
    finished = pyqtSignal(object, object)
    failed   = pyqtSignal(Exception)

    def __init__(self, transformer: XmlTransformer, xml_path: Path,
                 output_dir: Path) -> None:
        super().__init__()
        self._transformer = transformer
        self._xml_path    = xml_path
        self._output_dir  = output_dir

    def run(self) -> None:
        try:
            result_path, warnings = self._transformer.transform(
                self._xml_path, output_dir=self._output_dir
            )
            self.finished.emit(result_path, warnings)
        except Exception as exc:
            self.failed.emit(exc)


class _BatchWorker(QThread):
    progress  = pyqtSignal(int, int, str)
    file_done = pyqtSignal(str, bool, str)
    all_done  = pyqtSignal()

    def __init__(self, transformer: XmlTransformer, files: List[Path],
                 output_dir: Path) -> None:
        super().__init__()
        self._transformer = transformer
        self._files       = files
        self._output_dir  = output_dir

    def run(self) -> None:
        total = len(self._files)
        for i, path in enumerate(self._files, 1):
            self.progress.emit(i, total, path.name)
            try:
                out, _ = self._transformer.transform(path, output_dir=self._output_dir)
                self.file_done.emit(path.name, True, str(out))
            except Exception as e:
                self.file_done.emit(path.name, False, str(e))
        self.all_done.emit()


# ── Batch dialog ──────────────────────────────────────────────────────────────

class _BatchDialog(QDialog):
    def __init__(self, transformer: XmlTransformer, output_dir: Path,
                 parent=None) -> None:
        super().__init__(parent)
        self._transformer = transformer
        self._output_dir  = output_dir
        self._worker: Optional[_BatchWorker] = None
        self.setWindowTitle("Transformación por lotes")
        self.setMinimumSize(580, 500)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        toolbar = QHBoxLayout()
        add_btn = _primary_btn("＋  Agregar XMLs")
        add_btn.clicked.connect(self._add_files)
        toolbar.addWidget(add_btn)
        rm_btn = _secondary_btn("✕  Quitar seleccionados")
        rm_btn.clicked.connect(self._remove_files)
        toolbar.addWidget(rm_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self._list, stretch=1)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("muted")
        layout.addWidget(self._status_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(140)
        self._log.setObjectName("log")
        layout.addWidget(self._log)

        btn_row = QHBoxLayout()
        self._run_btn = _primary_btn("▶   Transformar todo")
        self._run_btn.clicked.connect(self._run)
        btn_row.addWidget(self._run_btn, stretch=1)
        close_btn = _secondary_btn("Cerrar")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar XMLs", "", "Archivos XML (*.xml)"
        )
        existing = {self._list.item(i).text() for i in range(self._list.count())}
        for p in paths:
            if p not in existing:
                self._list.addItem(p)

    def _remove_files(self) -> None:
        for item in reversed(self._list.selectedItems()):
            self._list.takeItem(self._list.row(item))

    def _run(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        files = [Path(self._list.item(i).text()) for i in range(self._list.count())]
        if not files:
            return
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(files))
        self._progress.setValue(0)
        self._log.clear()
        self._worker = _BatchWorker(self._transformer, files, self._output_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_progress(self, current: int, total: int, name: str) -> None:
        self._progress.setValue(current)
        self._status_lbl.setText(f"Procesando {current}/{total}:  {name}")

    def _on_file_done(self, name: str, success: bool, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        icon = "✓" if success else "✗"
        self._log.append(f"[{ts}]  {icon}  {name}  —  {message}")

    def _on_all_done(self) -> None:
        self._run_btn.setEnabled(True)
        self._status_lbl.setText("¡Completado!")


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
        self._theme = LIGHT
        self._zoom  = 1.0
        self._recent_files: List[Path] = []

        self.setWindowTitle("XMLens")
        self.resize(1200, 700)
        self.setMinimumSize(800, 500)
        self.setAcceptDrops(True)
        self._build_interface()
        self._setup_shortcuts()
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
        controls.setMinimumWidth(340)
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

        open_act = QAction("Abrir XML…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._select_file)
        file_menu.addAction(open_act)

        batch_act = QAction("Transformación por lotes…", self)
        batch_act.triggered.connect(self._open_batch_dialog)
        file_menu.addAction(batch_act)

        file_menu.addSeparator()

        self._recent_menu = file_menu.addMenu("Archivos recientes")
        self._update_recent_files_menu()

        file_menu.addSeparator()

        quit_act = QAction("Salir", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        tools_menu = self.menuBar().addMenu("Herramientas")

        clear_cache_act = QAction("Limpiar caché de XSLT…", self)
        clear_cache_act.triggered.connect(self._clear_cache)
        tools_menu.addAction(clear_cache_act)

        help_menu = self.menuBar().addMenu("Ayuda")
        about_act = QAction("Acerca de", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("F5"),      self, self._convert_and_open)
        QShortcut(QKeySequence("Ctrl+W"),  self, self._close_viewer)
        QShortcut(QKeySequence("Ctrl+F"),  self, self._toggle_search)
        QShortcut(QKeySequence("Ctrl+="),  self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"),  self, self._zoom_out)
        QShortcut(QKeySequence("Escape"),  self, self._close_search)

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setObjectName("surface")
        hdr.setFixedHeight(52)
        row = QHBoxLayout(hdr)
        row.setContentsMargins(20, 0, 12, 0)

        title = QLabel("XMLens")
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

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # ── Tab 0: HTML viewer ───────────────────────────────────────────────
        html_tab = QWidget()
        html_tab.setObjectName("bg")
        html_layout = QVBoxLayout(html_tab)
        html_layout.setContentsMargins(0, 0, 0, 0)
        html_layout.setSpacing(0)

        # Viewer toolbar (compound: inner row + separator)
        self._viewer_toolbar = QWidget()
        self._viewer_toolbar.setObjectName("bg")
        toolbar_outer = QVBoxLayout(self._viewer_toolbar)
        toolbar_outer.setContentsMargins(0, 0, 0, 0)
        toolbar_outer.setSpacing(0)

        toolbar_inner = QWidget()
        toolbar_inner.setObjectName("surface")
        toolbar_row = QHBoxLayout(toolbar_inner)
        toolbar_row.setContentsMargins(12, 6, 6, 6)

        self._viewer_filename = QLabel("")
        self._viewer_filename.setObjectName("viewer-filename")
        toolbar_row.addWidget(self._viewer_filename, stretch=1)

        zoom_out_btn = _secondary_btn("−")
        zoom_out_btn.setFixedWidth(30)
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar_row.addWidget(zoom_out_btn)

        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setObjectName("muted")
        self._zoom_lbl.setFixedWidth(42)
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar_row.addWidget(self._zoom_lbl)

        zoom_in_btn = _secondary_btn("＋")
        zoom_in_btn.setFixedWidth(30)
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar_row.addWidget(zoom_in_btn)

        toolbar_row.addSpacing(6)

        find_btn = _secondary_btn("🔍")
        find_btn.setFixedWidth(34)
        find_btn.setToolTip("Buscar  (Ctrl+F)")
        find_btn.clicked.connect(self._toggle_search)
        toolbar_row.addWidget(find_btn)

        close_btn = _secondary_btn("✕  Cerrar")
        close_btn.clicked.connect(self._close_viewer)
        toolbar_row.addWidget(close_btn)

        toolbar_outer.addWidget(toolbar_inner)
        toolbar_outer.addWidget(_separator())
        self._viewer_toolbar.setVisible(False)
        html_layout.addWidget(self._viewer_toolbar)

        # Search bar
        self._search_bar = QWidget()
        self._search_bar.setObjectName("surface")
        search_outer = QVBoxLayout(self._search_bar)
        search_outer.setContentsMargins(0, 0, 0, 0)
        search_outer.setSpacing(0)

        search_inner = QWidget()
        search_inner.setObjectName("surface")
        search_row = QHBoxLayout(search_inner)
        search_row.setContentsMargins(12, 6, 6, 6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Buscar en el documento…")
        self._search_input.returnPressed.connect(self._find_next)
        search_row.addWidget(self._search_input, stretch=1)

        prev_btn = _secondary_btn("◀")
        prev_btn.setFixedWidth(32)
        prev_btn.clicked.connect(self._find_prev)
        search_row.addWidget(prev_btn)

        next_btn = _secondary_btn("▶")
        next_btn.setFixedWidth(32)
        next_btn.clicked.connect(self._find_next)
        search_row.addWidget(next_btn)

        close_search_btn = _secondary_btn("✕")
        close_search_btn.setFixedWidth(30)
        close_search_btn.clicked.connect(self._close_search)
        search_row.addWidget(close_search_btn)

        search_outer.addWidget(search_inner)
        search_outer.addWidget(_separator())
        self._search_bar.setVisible(False)
        html_layout.addWidget(self._search_bar)

        # Stack: placeholder / web viewer
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_placeholder())

        self._viewer = QWebEngineView()
        self._viewer.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._viewer.setStyleSheet("border:none;")
        self._viewer.load(QUrl("about:blank"))
        self._stack.addWidget(self._viewer)

        html_layout.addWidget(self._stack, stretch=1)
        self._tabs.addTab(html_tab, "Vista previa")

        # ── Tab 1: XML source ─────────────────────────────────────────────────
        xml_tab = QWidget()
        xml_tab.setObjectName("bg")
        xml_layout = QVBoxLayout(xml_tab)
        xml_layout.setContentsMargins(0, 0, 0, 0)

        self._xml_view = QTextEdit()
        self._xml_view.setObjectName("log")
        self._xml_view.setReadOnly(True)
        self._xml_view.setFont(QFont("Consolas", 9))
        self._xml_view.setPlaceholderText("Seleccioná un archivo XML para ver su contenido aquí.")
        self._highlighter = _XmlHighlighter(self._xml_view.document())
        xml_layout.addWidget(self._xml_view)

        self._tabs.addTab(xml_tab, "XML fuente")

        layout.addWidget(self._tabs, stretch=1)
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

        text = QLabel(
            "Seleccioná un XML y transformalo para ver el resultado aquí\n"
            "También podés arrastrar un archivo .xml a la ventana"
        )
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

        self._open_btn = _secondary_btn("⧉  Abrir")
        self._open_btn.clicked.connect(self._open_selected_file)
        self._open_btn.setVisible(False)
        row.addWidget(self._open_btn)

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

        self._convert_btn = _primary_btn("▶   Transformar  (F5)")
        self._convert_btn.clicked.connect(self._convert_and_open)
        row.addWidget(self._convert_btn, stretch=1)

        folder_btn = _secondary_btn("📂  Abrir carpeta")
        folder_btn.clicked.connect(self._open_output_folder)
        row.addWidget(folder_btn)
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

        export_btn = _secondary_btn("💾  Exportar")
        export_btn.clicked.connect(self._export_log)
        hdr_row.addWidget(export_btn)

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
        s.setValue("output_dir",     str(self.output_dir))
        s.setValue("xslt_url",       self._xslt_entry.text())
        s.setValue("splitter_state", self._splitter.saveState())
        s.setValue("theme",          "dark" if self._theme is DARK else "light")
        s.setValue("zoom",           self._zoom)
        s.setValue("recent_files",   [str(p) for p in self._recent_files])

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

        try:
            self._zoom = float(s.value("zoom", 1.0))
        except (TypeError, ValueError):
            self._zoom = 1.0

        recent = s.value("recent_files", [])
        if isinstance(recent, list):
            self._recent_files = [Path(p) for p in recent if Path(p).exists()]
        elif isinstance(recent, str):
            p = Path(recent)
            self._recent_files = [p] if p.exists() else []
        self._update_recent_files_menu()

    # ── Recent files ──────────────────────────────────────────────────────────

    def _update_recent_files_menu(self) -> None:
        self._recent_menu.clear()
        if not self._recent_files:
            empty = QAction("(vacío)", self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return
        for path in self._recent_files:
            act = QAction(str(path), self)
            act.triggered.connect(lambda checked, p=path: self._open_recent_file(p))
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        clear_act = QAction("Limpiar recientes", self)
        clear_act.triggered.connect(self._clear_recent_files)
        self._recent_menu.addAction(clear_act)

    def _add_recent_file(self, path: Path) -> None:
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:_MAX_RECENT]
        self._update_recent_files_menu()

    def _open_recent_file(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Archivo no encontrado",
                                f"El archivo ya no existe:\n{path}")
            self._recent_files.remove(path)
            self._update_recent_files_menu()
            return
        self._load_xml_file(path)

    def _clear_recent_files(self) -> None:
        self._recent_files.clear()
        self._update_recent_files_menu()

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def _zoom_in(self) -> None:
        self._zoom = min(round(self._zoom + 0.1, 1), 3.0)
        self._apply_zoom()

    def _zoom_out(self) -> None:
        self._zoom = max(round(self._zoom - 0.1, 1), 0.25)
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        self._viewer.setZoomFactor(self._zoom)
        self._zoom_lbl.setText(f"{int(self._zoom * 100)}%")

    # ── Search ────────────────────────────────────────────────────────────────

    def _toggle_search(self) -> None:
        if self._tabs.currentIndex() != 0:
            self._tabs.setCurrentIndex(0)
        visible = not self._search_bar.isVisible()
        self._search_bar.setVisible(visible)
        if visible:
            self._search_input.setFocus()
            self._search_input.selectAll()
        else:
            self._viewer.findText("")

    def _close_search(self) -> None:
        if self._search_bar.isVisible():
            self._search_bar.setVisible(False)
            self._viewer.findText("")

    def _find_next(self) -> None:
        text = self._search_input.text()
        if text:
            self._viewer.findText(text)

    def _find_prev(self) -> None:
        text = self._search_input.text()
        if text:
            self._viewer.findText(text, QWebEnginePage.FindFlag.FindBackward)

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
        self._open_btn.setVisible(True)
        self._log_append(f"Seleccionado: {path}")
        self._refresh_xslt_url()
        self._add_recent_file(path)
        self._load_xml_view(path)

    def _load_xml_view(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            self._xml_view.setPlainText(content)
        except Exception as e:
            self._xml_view.setPlainText(f"Error leyendo el archivo: {e}")

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
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de salida", str(self.output_dir)
        )
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
            QMessageBox.warning(self, "Atención", "Seleccioná un archivo XML primero.")
            return
        self.transformer.xslt_url = self._xslt_entry.text().strip() or self.transformer.xslt_url
        if not self.transformer.xslt_url:
            QMessageBox.warning(self, "Atención", "Ingresá una URL de XSLT válida.")
            return

        self._convert_btn.setEnabled(False)
        self._log_append("Iniciando transformación…")
        self._spin_idx = 0
        self._spin_timer.start(80)

        self._worker = _TransformWorker(
            self.transformer, self.selected_file, self.output_dir
        )
        self._worker.finished.connect(self._on_transform_done)
        self._worker.failed.connect(self._on_transform_error)
        self._worker.start()

    def _advance_spinner(self) -> None:
        self._convert_btn.setText(f"{_SPINNER[self._spin_idx]}   Transformando…")
        self._spin_idx = (self._spin_idx + 1) % len(_SPINNER)

    def _on_transform_done(self, result_path: Path, warnings: List[str]) -> None:
        self._spin_timer.stop()
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("▶   Transformar  (F5)")
        self._log_append(f"Generado: {result_path}")
        for w in warnings:
            self._log_append(f"⚠  XSLT: {w}")
        self._show_in_viewer(result_path)

    def _on_transform_error(self, error: Exception) -> None:
        self._spin_timer.stop()
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("▶   Transformar  (F5)")
        QMessageBox.critical(self, "Error", str(error))
        self._log_append(f"Error: {error}")

    def _show_in_viewer(self, path: Path) -> None:
        self._viewer_filename.setText(path.name)
        self._viewer_toolbar.setVisible(True)
        self._viewer.load(QUrl.fromLocalFile(str(path)))
        self._viewer.setZoomFactor(self._zoom)
        self._stack.setCurrentIndex(1)
        self._tabs.setCurrentIndex(0)
        self._log_append("Resultado cargado en el visor.")

    def _close_viewer(self) -> None:
        self._stack.setCurrentIndex(0)
        self._viewer_toolbar.setVisible(False)
        self._search_bar.setVisible(False)
        self._viewer.setUrl(QUrl("about:blank"))
        self._log_append("Visor cerrado.")

    def _open_output_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        _open_path(self.output_dir)
        self._log_append(f"Carpeta de salida abierta: {self.output_dir}")

    def _open_batch_dialog(self) -> None:
        if not self.transformer.xslt_url:
            QMessageBox.warning(self, "Atención",
                                "Configurá una URL de XSLT antes de usar el modo lotes.")
            return
        dlg = _BatchDialog(self.transformer, self.output_dir, self)
        dlg.exec()

    def _clear_cache(self) -> None:
        count = XmlTransformer.clear_disk_cache()
        self.transformer._cached_url   = None
        self.transformer._cached_xslt  = None
        self.transformer._cached_mtime = None
        self._log_append(f"Caché limpiada: {count} archivo(s) eliminado(s).")
        QMessageBox.information(self, "Caché limpiada",
                                f"Se eliminaron {count} archivo(s) del caché de XSLT.")

    def _export_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar registro", "registro.txt", "Archivos de texto (*.txt)"
        )
        if path:
            Path(path).write_text(self._log.toPlainText(), encoding="utf-8")
            self._log_append(f"Registro exportado: {path}")

    def _clear_log(self) -> None:
        self._log.clear()
        self._log_append("Registro limpiado.")

    def _log_append(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}]  ›  {message}")

    def _show_about(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Acerca de XMLens")
        dlg.setFixedWidth(420)
        dlg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        root = QVBoxLayout(dlg)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header band ──────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("aboutHeader")
        header.setStyleSheet(
            "#aboutHeader { background: #1a6fc4; border-radius: 0px; }"
        )
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(24, 20, 24, 20)
        h_layout.setSpacing(4)

        name_lbl = QLabel("XMLens")
        name_font = QFont()
        name_font.setPointSize(22)
        name_font.setBold(True)
        name_lbl.setFont(name_font)
        name_lbl.setStyleSheet("color: #ffffff;")

        ver_lbl = QLabel("Versión 0.3.0")
        ver_lbl.setStyleSheet("color: #c0d8f0; font-size: 11pt;")

        h_layout.addWidget(name_lbl)
        h_layout.addWidget(ver_lbl)
        root.addWidget(header)

        # ── Body ─────────────────────────────────────────────────────────────
        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 20, 24, 20)
        b_layout.setSpacing(12)

        desc = QLabel(
            "Herramienta de escritorio para transformar documentos XML\n"
            "mediante hojas de estilo XSLT y visualizar el resultado HTML\n"
            "directamente en la aplicación."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 10pt; line-height: 1.5;")
        b_layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #cccccc;")
        b_layout.addWidget(sep)

        def _row(label: str, value: str, link: str = "") -> QWidget:
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            lbl = QLabel(f"<b>{label}</b>")
            lbl.setFixedWidth(90)
            lbl.setStyleSheet("font-size: 9.5pt;")
            hl.addWidget(lbl)
            if link:
                val = QLabel(f'<a href="{link}" style="color:#1a6fc4;">{value}</a>')
                val.setOpenExternalLinks(True)
            else:
                val = QLabel(value)
            val.setStyleSheet("font-size: 9.5pt;")
            val.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            hl.addWidget(val, 1)
            return w

        b_layout.addWidget(_row("Autor", "Facundo Peri"))
        b_layout.addWidget(_row("Contacto", "facundoperi01@gmail.com",
                                "mailto:facundoperi01@gmail.com"))
        b_layout.addWidget(_row("Tecnología", "Python · PyQt6 · lxml"))
        b_layout.addWidget(_row("Plataforma", "Windows (x86-64)"))
        b_layout.addWidget(_row("Licencia", "Uso interno"))

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #cccccc;")
        b_layout.addWidget(sep2)

        copy_lbl = QLabel("© 2025 – 2026 Facundo Peri. Todos los derechos reservados.")
        copy_lbl.setStyleSheet("color: #888888; font-size: 8.5pt;")
        copy_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(copy_lbl)

        close_btn = QPushButton("Cerrar")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        b_layout.addLayout(btn_row)

        root.addWidget(body)
        dlg.exec()

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
