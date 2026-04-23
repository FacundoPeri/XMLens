import os
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from transformer import DEFAULT_OUTPUT_DIR, XmlTransformer, extract_xslt_url

# ── Palette ───────────────────────────────────────────────────────────────────
_BG      = "#f4f6f9"
_SURFACE = "#ffffff"
_CARD    = "#ffffff"
_BORDER  = "#dde1e7"
_ACCENT  = "#374151"
_ACCENTH = "#1f2937"
_TEXT    = "#1c2331"
_MUTED   = "#6b7280"
_LOG_BG  = "#f9fafb"
_LOG_FG  = "#374151"
_BTN2    = "#e5e7eb"
_BTN2H   = "#d1d5db"


_SPINNER   = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_ICON_FONT = ("Segoe MDL2 Assets", 12)

# Segoe MDL2 Assets codepoints (built-in Windows 10/11 icon font)
_ICO_ADD         = ""  # Add (+ en círculo)
_ICO_OPEN        = ""  # Launch / open external
_ICO_FOLDER      = ""  # Folder
_ICO_FOLDER_OPEN = ""  # FolderOpen
_ICO_DELETE      = ""  # Delete (trash)


def _icon_btn(parent, icon: str, text: str, command=None, primary: bool = False) -> tk.Frame:
    """Frame-based button: icon rendered in Segoe MDL2 Assets, label in Segoe UI."""
    norm  = _ACCENT if primary else _BTN2
    hover = _ACCENTH if primary else _BTN2H
    fg    = "#ffffff" if primary else _TEXT

    frame  = tk.Frame(parent, bg=norm, cursor="hand2")
    lbl_i  = tk.Label(frame, text=icon, bg=norm, fg=fg, font=_ICON_FONT)
    lbl_t  = tk.Label(frame, text=text,  bg=norm, fg=fg, font=("Segoe UI", 10))
    lbl_i.pack(side="left", padx=(12, 3),  pady=8)
    lbl_t.pack(side="left", padx=(0,  14), pady=8)

    def _enter(*_):
        for w in (frame, lbl_i, lbl_t):
            w.config(bg=hover)

    def _leave(*_):
        for w in (frame, lbl_i, lbl_t):
            w.config(bg=norm)

    for w in (frame, lbl_i, lbl_t):
        w.bind("<Button-1>", lambda *_: command() if command else None)
        w.bind("<Enter>", _enter)
        w.bind("<Leave>", _leave)

    return frame


def _btn(parent, text: str, command=None, primary: bool = False, **kw) -> tk.Button:
    norm  = _ACCENT if primary else _BTN2
    hover = _ACCENTH if primary else _BTN2H
    fg = "#ffffff" if primary else _TEXT
    b = tk.Button(
        parent, text=text, command=command,
        bg=norm, fg=fg,
        activebackground=hover, activeforeground=fg,
        relief="flat", bd=0, highlightthickness=0,
        cursor="hand2", font=("Segoe UI", 10),
        padx=14, pady=6,
        **kw,
    )
    b.bind("<Enter>", lambda *_: b.config(bg=hover) if b["state"] == "normal" else None)
    b.bind("<Leave>", lambda *_: b.config(bg=norm)  if b["state"] == "normal" else None)
    return b


def _gap(parent, h: int = 12) -> tk.Frame:
    f = tk.Frame(parent, bg=_BG, height=h)
    f.pack(fill="x")
    return f


def _section_lbl(parent, text: str) -> tk.Label:
    lbl = tk.Label(parent, text=f"▸  {text}", bg=_BG, fg=_MUTED, font=("Segoe UI", 8, "bold"))
    lbl.pack(anchor="w")
    return lbl



class XmlVisualizerApp(tk.Tk):
    def __init__(self, transformer: XmlTransformer) -> None:
        super().__init__()
        self.transformer = transformer
        self.selected_file: Optional[Path] = None
        self.output_dir: Path = DEFAULT_OUTPUT_DIR
        self._transforming = False

        self.title("Visualizador de XMLS")
        self.geometry("840x570")
        self.minsize(700, 480)
        self.resizable(True, True)
        self.configure(bg=_BG)

        self.state("zoomed")
        self._build_interface()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_interface(self) -> None:
        self._build_menu()
        self._build_header()

        body = tk.Frame(self, bg=_BG)
        body.pack(fill="both", expand=True, padx=24, pady=18)

        self._build_file_row(body)
        _gap(body)
        self._build_xslt_row(body)
        _gap(body)
        self._build_output_row(body)
        _gap(body, 16)
        self._build_actions(body)
        _gap(body, 16)
        self._build_log(body)

    def _build_menu(self) -> None:
        mk = dict(bg=_SURFACE, fg=_TEXT, activebackground=_ACCENT, activeforeground="#fff")
        menu_bar  = tk.Menu(self, **mk, bd=0, relief="flat")
        file_menu = tk.Menu(menu_bar, tearoff=0, **mk)
        file_menu.add_command(label="Abrir XML…", command=self._select_file)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.quit)
        menu_bar.add_cascade(label="Archivo", menu=file_menu)
        help_menu = tk.Menu(menu_bar, tearoff=0, **mk)
        help_menu.add_command(label="Acerca de", command=self._show_about)
        menu_bar.add_cascade(label="Ayuda", menu=help_menu)
        self.config(menu=menu_bar)

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg=_SURFACE, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="Visualizador de XMLS",
            bg=_SURFACE, fg=_TEXT, font=("Segoe UI", 14, "bold"),
        ).pack(side="left", padx=(20, 8), pady=12)
        tk.Label(
            hdr, text="XML  ·  XSLT  ·  HTML",
            bg=_SURFACE, fg=_MUTED, font=("Segoe UI", 10),
        ).pack(side="left")
        tk.Frame(self, bg=_ACCENT, height=2).pack(fill="x")

    def _build_file_row(self, parent: tk.Frame) -> None:
        _section_lbl(parent, "ARCHIVO XML")
        row = tk.Frame(parent, bg=_CARD, highlightbackground=_BORDER, highlightthickness=1)
        row.pack(fill="x", pady=(4, 0))
        self.file_label = tk.Label(
            row, text="Ningún archivo seleccionado.",
            bg=_CARD, fg=_MUTED, font=("Segoe UI", 10), anchor="w",
        )
        self.file_label.pack(side="left", padx=12, pady=10, fill="x", expand=True)
        _icon_btn(row, _ICO_OPEN,   "Abrir",       command=self._open_selected_file            ).pack(side="right", padx=(0, 6), pady=4)
        _icon_btn(row, _ICO_ADD,    "Seleccionar", command=self._select_file, primary=True      ).pack(side="right", padx=(6, 6), pady=4)

    def _build_xslt_row(self, parent: tk.Frame) -> None:
        _section_lbl(parent, "URL DE XSLT")
        wrap = tk.Frame(parent, bg=_CARD, highlightbackground=_BORDER, highlightthickness=1)
        wrap.pack(fill="x", pady=(4, 0))
        self.xslt_entry = tk.Entry(
            wrap, bg=_CARD, fg=_TEXT, insertbackground=_TEXT,
            relief="flat", bd=0, highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self.xslt_entry.pack(fill="x", padx=12, pady=9)

    def _build_output_row(self, parent: tk.Frame) -> None:
        _section_lbl(parent, "CARPETA DE SALIDA")
        row = tk.Frame(parent, bg=_CARD, highlightbackground=_BORDER, highlightthickness=1)
        row.pack(fill="x", pady=(4, 0))
        self.output_label = tk.Label(
            row, text=str(self.output_dir),
            bg=_CARD, fg=_MUTED, font=("Segoe UI", 10), anchor="w",
        )
        self.output_label.pack(side="left", padx=12, pady=10, fill="x", expand=True)
        _icon_btn(row, _ICO_FOLDER, "Cambiar", command=self._select_output_folder).pack(side="right", padx=6, pady=4)

    def _build_actions(self, parent: tk.Frame) -> None:
        act = tk.Frame(parent, bg=_BG)
        act.pack(fill="x")
        act.columnconfigure(0, weight=1)
        act.columnconfigure(1, weight=1)
        self._convert_btn = _btn(act, "▶   Transformar y abrir", command=self._convert_and_open, primary=True)
        self._convert_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6), ipady=5)
        _icon_btn(act, _ICO_FOLDER_OPEN, "Abrir carpeta de salida", command=self._open_output_folder).grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    def _build_log(self, parent: tk.Frame) -> None:
        hdr = tk.Frame(parent, bg=_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text="▸  REGISTRO DE ACTIVIDAD", bg=_BG, fg=_MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        _icon_btn(hdr, _ICO_DELETE, "Limpiar", command=self._clear_status).pack(side="right")

        log_frame = tk.Frame(parent, bg=_LOG_BG, highlightbackground=_BORDER, highlightthickness=1)
        log_frame.pack(fill="both", expand=True, pady=(6, 0))

        self.status_text = tk.Text(
            log_frame,
            bg=_LOG_BG, fg=_LOG_FG,
            insertbackground=_LOG_FG,
            state="disabled", relief="flat", bd=0,
            font=("Consolas", 9),
            padx=12, pady=10,
            wrap="word",
        )
        self.status_text.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(
            log_frame, command=self.status_text.yview,
            bg=_SURFACE, troughcolor=_SURFACE, relief="flat", bd=0,
        )
        sb.pack(side="right", fill="y")
        self.status_text.configure(yscrollcommand=sb.set)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _select_file(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Seleccionar XML",
            filetypes=[("Archivos XML", "*.xml")],
        )
        if not chosen:
            return
        self.selected_file = Path(chosen)
        self.file_label.config(text=self.selected_file.name, fg=_TEXT)
        self._append_status(f"Seleccionado: {self.selected_file}")
        self._refresh_xslt_url()

    def _refresh_xslt_url(self) -> None:
        url = extract_xslt_url(self.selected_file) or ""
        self.transformer.xslt_url = url
        self.xslt_entry.delete(0, "end")
        self.xslt_entry.insert(0, url)
        if url:
            self._append_status(f"XSLT detectado: {url}")
        else:
            self._append_status("No se encontró una URL de XSLT en el archivo.")

    def _open_selected_file(self) -> None:
        if not self.selected_file or not self.selected_file.exists():
            messagebox.showwarning("Atención", "No hay un archivo XML válido seleccionado.")
            return
        os.startfile(self.selected_file)
        self._append_status(f"Abriendo: {self.selected_file}")

    def _select_output_folder(self) -> None:
        folder = filedialog.askdirectory(title="Seleccionar carpeta de salida", initialdir=self.output_dir)
        if not folder:
            return
        self.output_dir = Path(folder)
        self.output_label.config(text=str(self.output_dir))
        self._append_status(f"Carpeta de salida: {self.output_dir}")

    def _convert_and_open(self) -> None:
        if self._transforming:
            return
        if not self.selected_file:
            messagebox.showwarning("Atención", "Selecciona un archivo XML primero.")
            return
        self.transformer.xslt_url = self.xslt_entry.get().strip() or self.transformer.xslt_url
        if not self.transformer.xslt_url:
            messagebox.showwarning("Atención", "Ingresa una URL de XSLT válida.")
            return

        self._transforming = True
        self._convert_btn.config(state="disabled", bg=_BTN2, cursor="arrow")
        self._append_status("Iniciando transformación…")
        self._spin()

        xml_path   = self.selected_file
        output_dir = self.output_dir

        def run() -> None:
            try:
                result = self.transformer.transform(xml_path, output_dir=output_dir)
                self.after(0, self._on_transform_done, result, None)
            except Exception as exc:
                self.after(0, self._on_transform_done, None, exc)

        threading.Thread(target=run, daemon=True).start()

    def _spin(self, frame: int = 0) -> None:
        if not self._transforming:
            return
        self._convert_btn.config(text=f"{_SPINNER[frame]}   Transformando…")
        self.after(80, self._spin, (frame + 1) % len(_SPINNER))

    def _on_transform_done(self, result_path: Optional[Path], error: Optional[Exception]) -> None:
        self._transforming = False
        self._convert_btn.config(state="normal", bg=_ACCENT, cursor="hand2", text="▶   Transformar y abrir")
        if error:
            messagebox.showerror("Error", str(error))
            self._append_status(f"Error: {error}")
        else:
            self._append_status(f"Generado: {result_path}")
            webbrowser.open_new_tab(result_path.as_uri())
            self._append_status("Resultado abierto en el navegador.")

    def _open_output_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.output_dir)
        self._append_status(f"Carpeta de salida abierta: {self.output_dir}")

    def _clear_status(self) -> None:
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.configure(state="disabled")
        self._append_status("Registro limpiado.")

    def _append_status(self, message: str) -> None:
        self.status_text.configure(state="normal")
        self.status_text.insert("end", f"›  {message}\n")
        self.status_text.configure(state="disabled")
        self.status_text.see("end")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "Acerca de",
            "Visualizador de XMLS\n\nUna aplicación ligera para transformar XML con XSLT"
            " y revisar el resultado HTML.\n\nDesarrollado como un ejemplo profesional de interfaz minimalista.",
        )
