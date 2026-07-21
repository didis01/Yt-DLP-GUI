#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import io
import json
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import shutil
import requests
from PIL import Image, ImageTk

# Color Palette (Dark Theme / Sleek Indigo)
BG_MAIN = "#121214"
BG_CARD = "#1E1E24"
BG_INPUT = "#2A2A32"
BORDER_COLOR = "#374151"
BORDER_FOCUS = "#6366F1"
TEXT_MAIN = "#F9FAFB"
TEXT_MUTED = "#9CA3AF"
ACCENT_PRIMARY = "#4F46E5"
ACCENT_HOVER = "#6366F1"
ACCENT_SUCCESS = "#10B981"
ACCENT_SUCCESS_HOV = "#059669"
ACCENT_DANGER = "#EF4444"
ACCENT_DANGER_HOV = "#DC2626"
BG_CONSOLE = "#0A0A0C"

MODES = ("video", "playlist", "search")
MODE_LABELS = {"video": "Video", "playlist": "Playlist", "search": "Búsqueda"}


def get_app_data_dir():
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        base_dir = os.path.join(local_app_data, "YtDlpGui")
    else:
        base_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "yt-dlp-gui")

    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def format_duration(seconds):
    if not seconds:
        return "Desconocida"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_json_lines(text):
    entries = []
    for line in text.strip().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def entry_url(entry):
    return entry.get("webpage_url") or entry.get("url") or entry.get("original_url")


def get_thumbnail_url(entry):
    url = entry.get("thumbnail")
    if url:
        return url

    thumbnails = entry.get("thumbnails")
    if thumbnails:
        best = max(thumbnails, key=lambda t: t.get("height") or 0)
        if best.get("url"):
            return best["url"]

    video_id = entry.get("id")
    if video_id and re.fullmatch(r"[\w-]{11}", str(video_id)):
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return None


THUMBNAIL_EXTENSIONS = {".webp", ".jpg", ".jpeg", ".png", ".image"}


class CanvasProgressBar(tk.Canvas):
    def __init__(self, parent, height=12, bg=BG_INPUT, fill_color=ACCENT_PRIMARY, **kwargs):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0, **kwargs)
        self.fill_color = fill_color
        self.percentage = 0
        self.height = height
        self.rect_id = self.create_rectangle(0, 0, 0, height, fill=self.fill_color, width=0)
        self.bind("<Configure>", self._on_resize)

    def set_progress(self, percentage):
        self.percentage = max(0.0, min(100.0, percentage))
        self._update_progress()

    def set_color(self, color):
        self.fill_color = color
        self.itemconfig(self.rect_id, fill=color)

    def _update_progress(self):
        width = self.winfo_width()
        fill_width = (self.percentage / 100.0) * width
        self.coords(self.rect_id, 0, 0, fill_width, self.height)

    def _on_resize(self, event):
        self._update_progress()


class YtDlpGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Yt-Dlp GUI Media Downloader")
        self.geometry("920x780")
        self.configure(bg=BG_MAIN)
        self.minsize(800, 650)

        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        self.selected_output_dir = self.get_default_download_dir()
        self.app_mode = "video"
        self.current_video_info = None
        self.playlist_entries = []
        self.playlist_vars = []
        self.search_results = []
        self.playlist_source_url = ""
        self.active_process = None
        self.is_downloading = False
        self.is_analyzing = False
        self.cancel_requested = False
        self._video_thumb_photo = None
        self._search_thumb_photo = None
        self.files_before_download = set()
        self.mode_buttons = {}

        self.setup_styles()

        self.container = tk.Frame(self, bg=BG_MAIN)
        self.container.pack(fill="both", expand=True)

        self.show_disclaimer()

    def get_default_download_dir(self):
        home = os.path.expanduser("~")
        downloads = os.path.join(home, "Downloads")
        if os.path.exists(downloads):
            return downloads
        descargas = os.path.join(home, "Descargas")
        if os.path.exists(descargas):
            return descargas
        return home

    def get_ytdlp_path(self):
        ext = ".exe" if sys.platform == "win32" else ""
        local_path = os.path.join(get_app_data_dir(), f"yt-dlp{ext}")
        if os.path.exists(local_path) and (sys.platform == "win32" or os.access(local_path, os.X_OK)):
            return local_path

        sys_path = shutil.which(f"yt-dlp{ext}")
        if sys_path:
            return sys_path

        return f"yt-dlp{ext}"

    def check_ffmpeg(self):
        return shutil.which("ffmpeg") is not None

    def needs_ffmpeg(self):
        fmt_choice = self.fmt_combo.get()
        if fmt_choice.startswith("Solo Audio"):
            return True
        if self.subtitles_var.get():
            return True
        if self.metadata_var.get():
            return True
        return False

    def update_ytdlp(self):
        if self.is_downloading or self.is_analyzing:
            messagebox.showwarning(
                "Acción no disponible",
                "No puedes actualizar el motor de descarga mientras haya un análisis o descarga activa.",
            )
            return

        self.btn_update_engine.configure(state="disabled", text="🔄 Actualizando...")
        self.log_message("[System] Iniciando descarga manual de la última versión de yt-dlp...")

        def run_update():
            app_data_dir = get_app_data_dir()
            ext = ".exe" if sys.platform == "win32" else ""
            local_path = os.path.join(app_data_dir, f"yt-dlp{ext}")
            try:
                os.makedirs(app_data_dir, exist_ok=True)
                url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp{ext}"
                r = requests.get(url, stream=True, timeout=20)
                if r.status_code == 200:
                    with open(local_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    if sys.platform != "win32":
                        os.chmod(local_path, 0o755)
                    self.after(0, self.update_ytdlp_success, local_path)
                else:
                    self.after(0, self.update_ytdlp_fail, f"Error HTTP {r.status_code}")
            except Exception as e:
                self.after(0, self.update_ytdlp_fail, str(e))

        threading.Thread(target=run_update, daemon=True).start()

    def update_ytdlp_success(self, local_path):
        self.btn_update_engine.configure(state="normal", text="🔄 Actualizar Motor (yt-dlp)")
        self.log_message(f"[System] El motor yt-dlp se ha actualizado correctamente en: {local_path}")
        messagebox.showinfo("Motor Actualizado", "El motor yt-dlp se ha actualizado correctamente a la última versión de GitHub.")

    def update_ytdlp_fail(self, err_msg):
        self.btn_update_engine.configure(state="normal", text="🔄 Actualizar Motor (yt-dlp)")
        self.log_message(f"[Error] Falló la actualización de yt-dlp: {err_msg}")
        messagebox.showerror("Error de Actualización", f"No se pudo descargar la actualización de yt-dlp:\n{err_msg}")

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure("TFrame", background=BG_MAIN)
        self.style.configure("Card.TFrame", background=BG_CARD, relief="flat", borderwidth=0)

        self.style.configure("TLabel", background=BG_MAIN, foreground=TEXT_MAIN, font=("Helvetica", 10))
        self.style.configure("Header.TLabel", background=BG_MAIN, foreground=TEXT_MAIN, font=("Helvetica", 20, "bold"))
        self.style.configure("Subtitle.TLabel", background=BG_MAIN, foreground=TEXT_MUTED, font=("Helvetica", 10, "italic"))
        self.style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_MAIN, font=("Helvetica", 10))
        self.style.configure("CardTitle.TLabel", background=BG_CARD, foreground=TEXT_MAIN, font=("Helvetica", 12, "bold"))
        self.style.configure("Muted.TLabel", background=BG_CARD, foreground=TEXT_MUTED, font=("Helvetica", 9))
        self.style.configure("MutedBold.TLabel", background=BG_CARD, foreground=TEXT_MUTED, font=("Helvetica", 9, "bold"))

        self.style.configure(
            "Card.TCheckbutton",
            background=BG_CARD,
            foreground=TEXT_MAIN,
            activebackground=BG_CARD,
            activeforeground=TEXT_MAIN,
            font=("Helvetica", 10),
        )
        self.style.map(
            "Card.TCheckbutton",
            background=[("active", BG_CARD), ("selected", BG_CARD)],
            foreground=[("active", TEXT_MAIN), ("selected", TEXT_MAIN)],
        )

        self.style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_CARD,
            foreground=TEXT_MAIN,
            arrowcolor=TEXT_MAIN,
            bordercolor=BORDER_COLOR,
            lightcolor=BORDER_COLOR,
            darkcolor=BORDER_COLOR,
            font=("Helvetica", 10),
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", TEXT_MAIN)],
        )

        self.style.configure(
            "Results.Treeview",
            background=BG_INPUT,
            foreground=TEXT_MAIN,
            fieldbackground=BG_INPUT,
            bordercolor=BORDER_COLOR,
            font=("Helvetica", 9),
            rowheight=24,
        )
        self.style.configure(
            "Results.Treeview.Heading",
            background=BG_CARD,
            foreground=TEXT_MAIN,
            font=("Helvetica", 9, "bold"),
        )
        self.style.map("Results.Treeview", background=[("selected", ACCENT_PRIMARY)])

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def make_flat_button(self, parent, text, bg, fg, hover_bg, font, command, state="normal"):
        btn = tk.Button(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            activebackground=hover_bg,
            activeforeground=fg,
            font=font,
            bd=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2" if state == "normal" else "arrow",
            command=command,
            state=state,
        )

        def on_enter(e):
            if btn["state"] == "normal":
                btn.configure(bg=hover_bg)

        def on_leave(e):
            if btn["state"] == "normal":
                btn.configure(bg=bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def show_disclaimer(self):
        self.clear_container()

        disclaimer_card = tk.Frame(self.container, bg=BG_CARD, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1)
        disclaimer_card.place(relx=0.5, rely=0.5, anchor="center", width=680, height=480)

        warning_icon_label = tk.Label(disclaimer_card, text="⚠️", font=("Helvetica", 48), bg=BG_CARD, fg="#F59E0B")
        warning_icon_label.pack(pady=(30, 10))

        title_label = tk.Label(
            disclaimer_card,
            text="AVISO DE USO Y RESPONSABILIDAD",
            font=("Helvetica", 16, "bold"),
            bg=BG_CARD,
            fg=TEXT_MAIN,
        )
        title_label.pack(pady=5)

        divider = tk.Frame(disclaimer_card, height=1, bg=BORDER_COLOR)
        divider.pack(fill="x", padx=40, pady=10)

        text_content = (
            "Este software es una utilidad gráfica de uso privado para la herramienta de consola 'yt-dlp'.\n\n"
            "INFORMACIÓN IMPORTANTE SOBRE PIRATERÍA Y DERECHOS DE AUTOR:\n"
            "• Este programa NO ha sido diseñado para piratear o violar derechos de autor.\n"
            "• Solo debe usarse para descargar contenido propio, material libre de derechos (Creative Commons, "
            "Dominio Público) o contenido sobre el cual posea permisos explícitos de copia por parte de sus autores.\n"
            "• Queda terminantemente prohibido utilizar esta aplicación para infringir leyes de propiedad intelectual.\n\n"
            "Al hacer clic en 'Aceptar', usted se compromete a usar esta herramienta exclusivamente como utilidad "
            "de acuerdo con los términos de servicio de los sitios web de origen y las leyes vigentes en su jurisdicción. "
            "El autor del software no asume responsabilidad alguna por el mal uso que se le pueda dar."
        )

        text_widget = tk.Text(
            disclaimer_card,
            bg=BG_CARD,
            fg=TEXT_MAIN,
            font=("Helvetica", 10),
            wrap="word",
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=5,
            height=8,
        )
        text_widget.insert("1.0", text_content)
        text_widget.configure(state="disabled")

        btn_frame = tk.Frame(disclaimer_card, bg=BG_CARD)
        btn_frame.pack(side="bottom", fill="x", pady=(0, 30))

        btn_exit = self.make_flat_button(
            btn_frame,
            "Declinar y Salir",
            bg="#374151",
            fg=TEXT_MAIN,
            hover_bg="#4B5563",
            font=("Helvetica", 10, "bold"),
            command=self.quit,
        )
        btn_exit.pack(side="left", padx=(100, 10), expand=True, fill="x")

        btn_accept = self.make_flat_button(
            btn_frame,
            "Aceptar e Iniciar",
            bg=ACCENT_PRIMARY,
            fg="#FFFFFF",
            hover_bg=ACCENT_HOVER,
            font=("Helvetica", 10, "bold"),
            command=self.accept_disclaimer,
        )
        btn_accept.pack(side="right", padx=(10, 100), expand=True, fill="x")

        text_widget.pack(side="top", fill="both", expand=True, padx=40, pady=(5, 10))

    def accept_disclaimer(self):
        self.show_main_app()

    def show_main_app(self):
        self.clear_container()

        header_frame = tk.Frame(self.container, bg=BG_MAIN)
        header_frame.pack(fill="x", padx=25, pady=(20, 10))

        title_lbl = ttk.Label(header_frame, text="📥 Yt-Dlp GUI Media Downloader", style="Header.TLabel")
        title_lbl.pack(anchor="w")
        sub_lbl = ttk.Label(
            header_frame,
            text="Interfaz gráfica para descargar contenido personal mediante yt-dlp.",
            style="Subtitle.TLabel",
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        mode_frame = tk.Frame(self.container, bg=BG_MAIN)
        mode_frame.pack(fill="x", padx=25, pady=(0, 12))

        mode_lbl = ttk.Label(mode_frame, text="Modo de descarga", style="TLabel")
        mode_lbl.pack(anchor="w", pady=(0, 6))

        mode_btn_row = tk.Frame(mode_frame, bg=BG_MAIN)
        mode_btn_row.pack(fill="x")

        for mode in MODES:
            btn = self.make_flat_button(
                mode_btn_row,
                MODE_LABELS[mode],
                bg=ACCENT_PRIMARY if mode == self.app_mode else "#2D3748",
                fg="#FFFFFF" if mode == self.app_mode else TEXT_MAIN,
                hover_bg=ACCENT_HOVER if mode == self.app_mode else "#4A5568",
                font=("Helvetica", 10, "bold"),
                command=lambda m=mode: self.switch_mode(m),
            )
            btn.pack(side="left", padx=(0, 8), ipady=4, ipadx=16)
            self.mode_buttons[mode] = btn

        self.input_card = tk.Frame(self.container, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.input_card.pack(fill="x", padx=25, pady=(0, 15))

        self.input_title = ttk.Label(self.input_card, text="Dirección URL del Enlace", style="CardTitle.TLabel")
        self.input_title.pack(anchor="w", padx=20, pady=(15, 5))

        input_row = tk.Frame(self.input_card, bg=BG_CARD)
        input_row.pack(fill="x", padx=20, pady=(0, 15))

        self.entry_border = tk.Frame(
            input_row,
            bg=BORDER_COLOR,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=BORDER_FOCUS,
        )
        self.entry_border.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.url_entry = tk.Entry(
            self.entry_border,
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            relief="flat",
            bd=0,
            font=("Helvetica", 11),
        )
        self.url_entry.pack(fill="both", expand=True, padx=8, pady=8)
        self.url_entry.bind("<FocusIn>", lambda e: self.entry_border.configure(highlightbackground=BORDER_FOCUS))
        self.url_entry.bind("<FocusOut>", lambda e: self.entry_border.configure(highlightbackground=BORDER_COLOR))
        self.url_entry.bind("<Return>", lambda e: self.start_analyze())

        self.btn_paste = self.make_flat_button(
            input_row,
            "📋 Pegar",
            bg="#2D3748",
            fg=TEXT_MAIN,
            hover_bg="#4A5568",
            font=("Helvetica", 10, "bold"),
            command=self.paste_url,
        )
        self.btn_paste.pack(side="left", padx=(0, 5), ipady=4, ipadx=10)

        self.btn_analyze = self.make_flat_button(
            input_row,
            "🔍 Analizar",
            bg=ACCENT_PRIMARY,
            fg="#FFFFFF",
            hover_bg=ACCENT_HOVER,
            font=("Helvetica", 10, "bold"),
            command=self.start_analyze,
        )
        self.btn_analyze.pack(side="left", ipady=4, ipadx=15)

        self.status_lbl_analyze = ttk.Label(self.input_card, text="", style="Subtitle.TLabel", background=BG_CARD)
        self.status_lbl_analyze.pack(anchor="w", padx=20, pady=(0, 10))

        self.split_frame = tk.Frame(self.container, bg=BG_MAIN)
        self.split_frame.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        self.info_card = tk.Frame(self.split_frame, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.info_card.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.info_title = ttk.Label(self.info_card, text="Información del Video", style="CardTitle.TLabel")
        self.info_title.pack(anchor="w", padx=20, pady=15)

        self.video_info_frame = tk.Frame(self.info_card, bg=BG_CARD)
        self.playlist_info_frame = tk.Frame(self.info_card, bg=BG_CARD)
        self.search_info_frame = tk.Frame(self.info_card, bg=BG_CARD)

        self._build_video_info_panel()
        self._build_playlist_info_panel()
        self._build_search_info_panel()

        self.settings_card = tk.Frame(self.split_frame, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.settings_card.pack(side="right", fill="both", expand=True, padx=(10, 0))

        settings_title = ttk.Label(self.settings_card, text="Ajustes de Descarga", style="CardTitle.TLabel")
        settings_title.pack(anchor="w", padx=20, pady=15)

        self.settings_content_frame = tk.Frame(self.settings_card, bg=BG_CARD)
        self.settings_content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        fmt_lbl = ttk.Label(self.settings_content_frame, text="Formato y Calidad", style="Card.TLabel")
        fmt_lbl.pack(anchor="w", pady=(0, 5))

        self.format_options = [
            "Video + Audio (Mejor Calidad)",
            "Video MP4 (1080p Máx)",
            "Video MP4 (720p Máx)",
            "Video MP4 (480p Máx)",
            "Solo Audio MP3 (Alta Calidad 320k)",
            "Solo Audio M4A (Estándar)",
            "Solo Audio WAV (Sin Pérdida)",
        ]
        self.fmt_combo = ttk.Combobox(self.settings_content_frame, values=self.format_options, state="readonly", style="TCombobox")
        self.fmt_combo.set("Video + Audio (Mejor Calidad)")
        self.fmt_combo.pack(fill="x", pady=(0, 12))

        dest_lbl = ttk.Label(self.settings_content_frame, text="Carpeta de Guardado", style="Card.TLabel")
        dest_lbl.pack(anchor="w", pady=(0, 5))

        dest_row = tk.Frame(self.settings_content_frame, bg=BG_CARD)
        dest_row.pack(fill="x", pady=(0, 12))

        self.dest_entry_border = tk.Frame(dest_row, bg=BORDER_COLOR, bd=0, highlightthickness=1)
        self.dest_entry_border.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.dest_entry = tk.Entry(
            self.dest_entry_border,
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            relief="flat",
            bd=0,
            font=("Helvetica", 9),
        )
        self.dest_entry.pack(fill="both", expand=True, padx=6, pady=6)
        self.dest_entry.insert(0, self.selected_output_dir)
        self.dest_entry.configure(state="readonly")

        self.btn_browse = self.make_flat_button(
            dest_row,
            "📂",
            bg="#2D3748",
            fg=TEXT_MAIN,
            hover_bg="#4A5568",
            font=("Helvetica", 10, "bold"),
            command=self.browse_output_dir,
        )
        self.btn_browse.pack(side="right", ipady=3, ipadx=8)

        self.subtitles_var = tk.BooleanVar(value=False)
        self.subs_chk = ttk.Checkbutton(
            self.settings_content_frame,
            text="Descargar y acoplar subtítulos (es/en)",
            variable=self.subtitles_var,
            style="Card.TCheckbutton",
        )
        self.subs_chk.pack(anchor="w", pady=4)

        self.metadata_var = tk.BooleanVar(value=True)
        self.meta_chk = ttk.Checkbutton(
            self.settings_content_frame,
            text="Incrustar metadatos y miniatura en archivo",
            variable=self.metadata_var,
            style="Card.TCheckbutton",
        )
        self.meta_chk.pack(anchor="w", pady=4)

        self.btn_update_engine = self.make_flat_button(
            self.settings_content_frame,
            "🔄 Actualizar Motor (yt-dlp)",
            bg="#2D3748",
            fg=TEXT_MAIN,
            hover_bg="#4A5568",
            font=("Helvetica", 9, "bold"),
            command=self.update_ytdlp,
        )
        self.btn_update_engine.pack(anchor="w", pady=(10, 0), fill="x")

        progress_card = tk.Frame(self.container, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        progress_card.pack(fill="x", padx=25, pady=(0, 15))

        p_row = tk.Frame(progress_card, bg=BG_CARD)
        p_row.pack(fill="x", padx=20, pady=(15, 10))

        self.btn_download = self.make_flat_button(
            p_row,
            "📥 INICIAR DESCARGA",
            bg=ACCENT_SUCCESS,
            fg="#FFFFFF",
            hover_bg=ACCENT_SUCCESS_HOV,
            font=("Helvetica", 11, "bold"),
            command=self.start_download,
        )
        self.btn_download.pack(side="left", fill="both", expand=True, padx=(0, 10), ipady=6)

        self.btn_cancel = self.make_flat_button(
            p_row,
            "⏹ Cancelar",
            bg=ACCENT_DANGER,
            fg="#FFFFFF",
            hover_bg=ACCENT_DANGER_HOV,
            font=("Helvetica", 10, "bold"),
            command=self.cancel_download,
            state="disabled",
        )
        self.btn_cancel.pack(side="right", ipady=6, ipadx=20)
        self.btn_cancel.configure(bg="#374151")

        pbar_row = tk.Frame(progress_card, bg=BG_CARD)
        pbar_row.pack(fill="x", padx=20, pady=(0, 5))

        self.progress_bar = CanvasProgressBar(pbar_row, height=14)
        self.progress_bar.pack(fill="x")

        stats_row = tk.Frame(progress_card, bg=BG_CARD)
        stats_row.pack(fill="x", padx=20, pady=(0, 15))

        self.stat_status = ttk.Label(stats_row, text="Estado: Inactivo", style="MutedBold.TLabel")
        self.stat_status.pack(side="left")

        self.stat_speed = ttk.Label(stats_row, text="Velocidad: --", style="Muted.TLabel")
        self.stat_speed.pack(side="left", padx=20)

        self.stat_eta = ttk.Label(stats_row, text="Restante: --", style="Muted.TLabel")
        self.stat_eta.pack(side="left", padx=20)

        self.stat_size = ttk.Label(stats_row, text="Tamaño: --", style="Muted.TLabel")
        self.stat_size.pack(side="left", padx=20)

        self.console_btn = self.make_flat_button(
            self.container,
            "▶ Mostrar Consola de Salida (yt-dlp log)",
            bg="#1E1E24",
            fg=TEXT_MUTED,
            hover_bg="#2D3748",
            font=("Helvetica", 9),
            command=self.toggle_console,
        )
        self.console_btn.pack(fill="x", padx=25, pady=(0, 5))

        self.console_frame = tk.Frame(self.container, bg=BG_CONSOLE)

        self.console_text = tk.Text(
            self.console_frame,
            bg=BG_CONSOLE,
            fg="#10B981",
            font=("Courier", 9),
            relief="flat",
            bd=0,
            highlightthickness=0,
            state="disabled",
            wrap="word",
            height=8,
        )
        self.console_text.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        console_scroll = ttk.Scrollbar(self.console_frame, command=self.console_text.yview)
        console_scroll.pack(side="right", fill="y")
        self.console_text.configure(yscrollcommand=console_scroll.set)

        self.console_expanded = False
        self.update_mode_ui()

    def _build_video_info_panel(self):
        self.thumb_canvas = tk.Canvas(
            self.video_info_frame,
            width=200,
            height=112,
            bg=BG_INPUT,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        self.thumb_canvas.pack(anchor="w", pady=(0, 10))
        self.thumb_canvas.create_text(100, 56, text="Vista Previa", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))

        self.info_title_lbl = ttk.Label(
            self.video_info_frame,
            text="Título: (Esperando enlace...)",
            style="Card.TLabel",
            wraplength=220,
        )
        self.info_title_lbl.pack(anchor="w", pady=2)

        self.info_author_lbl = ttk.Label(self.video_info_frame, text="Canal: --", style="Muted.TLabel")
        self.info_author_lbl.pack(anchor="w", pady=2)

        self.info_duration_lbl = ttk.Label(self.video_info_frame, text="Duración: --", style="Muted.TLabel")
        self.info_duration_lbl.pack(anchor="w", pady=2)

    def _build_playlist_info_panel(self):
        playlist_controls = tk.Frame(self.playlist_info_frame, bg=BG_CARD)
        playlist_controls.pack(fill="x", padx=20, pady=(0, 8))

        self.playlist_count_lbl = ttk.Label(
            self.playlist_info_frame,
            text="0 vídeos encontrados",
            style="Muted.TLabel",
        )
        self.playlist_count_lbl.pack(anchor="w", padx=20, pady=(0, 6))

        self.btn_select_all = self.make_flat_button(
            playlist_controls,
            "Seleccionar todo",
            bg="#2D3748",
            fg=TEXT_MAIN,
            hover_bg="#4A5568",
            font=("Helvetica", 9, "bold"),
            command=lambda: self.set_all_playlist_selection(True),
        )
        self.btn_select_all.pack(side="left", padx=(0, 6), ipady=2, ipadx=8)

        self.btn_select_none = self.make_flat_button(
            playlist_controls,
            "Deseleccionar todo",
            bg="#2D3748",
            fg=TEXT_MAIN,
            hover_bg="#4A5568",
            font=("Helvetica", 9, "bold"),
            command=lambda: self.set_all_playlist_selection(False),
        )
        self.btn_select_none.pack(side="left", ipady=2, ipadx=8)

        list_container = tk.Frame(self.playlist_info_frame, bg=BG_CARD)
        list_container.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.playlist_canvas = tk.Canvas(list_container, bg=BG_INPUT, highlightthickness=1, highlightbackground=BORDER_COLOR)
        playlist_scroll = ttk.Scrollbar(list_container, orient="vertical", command=self.playlist_canvas.yview)
        self.playlist_inner = tk.Frame(self.playlist_canvas, bg=BG_INPUT)

        self.playlist_inner.bind(
            "<Configure>",
            lambda e: self.playlist_canvas.configure(scrollregion=self.playlist_canvas.bbox("all")),
        )
        self.playlist_canvas.create_window((0, 0), window=self.playlist_inner, anchor="nw")
        self.playlist_canvas.configure(yscrollcommand=playlist_scroll.set)

        self.playlist_canvas.pack(side="left", fill="both", expand=True)
        playlist_scroll.pack(side="right", fill="y")

        def _on_mousewheel(event):
            self.playlist_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.playlist_canvas.bind("<Enter>", lambda e: self.playlist_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.playlist_canvas.bind("<Leave>", lambda e: self.playlist_canvas.unbind_all("<MouseWheel>"))

    def _build_search_info_panel(self):
        search_hint = ttk.Label(
            self.search_info_frame,
            text="Selecciona un resultado para ver la vista previa.",
            style="Muted.TLabel",
        )
        search_hint.pack(anchor="w", padx=20, pady=(0, 8))

        search_container = tk.Frame(self.search_info_frame, bg=BG_CARD)
        search_container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.search_tree = ttk.Treeview(
            search_container,
            columns=("title", "duration", "channel"),
            show="headings",
            style="Results.Treeview",
            selectmode="browse",
            height=8,
        )
        self.search_tree.heading("title", text="Título")
        self.search_tree.heading("duration", text="Duración")
        self.search_tree.heading("channel", text="Canal")
        self.search_tree.column("title", width=220, stretch=True)
        self.search_tree.column("duration", width=70, stretch=False)
        self.search_tree.column("channel", width=120, stretch=True)
        self.search_tree.bind("<<TreeviewSelect>>", self.on_search_result_select)

        search_scroll = ttk.Scrollbar(search_container, orient="vertical", command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=search_scroll.set)
        self.search_tree.pack(side="left", fill="both", expand=True)
        search_scroll.pack(side="right", fill="y")

        preview_frame = tk.Frame(self.search_info_frame, bg=BG_CARD)
        preview_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.search_thumb_canvas = tk.Canvas(
            preview_frame,
            width=200,
            height=112,
            bg=BG_INPUT,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        self.search_thumb_canvas.pack(anchor="w", pady=(0, 8))
        self.search_thumb_canvas.create_text(100, 56, text="Vista Previa", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))

        self.search_preview_title = ttk.Label(preview_frame, text="Título: --", style="Card.TLabel", wraplength=280)
        self.search_preview_title.pack(anchor="w", pady=2)
        self.search_preview_channel = ttk.Label(preview_frame, text="Canal: --", style="Muted.TLabel")
        self.search_preview_channel.pack(anchor="w", pady=2)

    def switch_mode(self, mode):
        if mode == self.app_mode or self.is_analyzing or self.is_downloading:
            return

        self.app_mode = mode
        self.current_video_info = None
        self.playlist_entries = []
        self.playlist_vars = []
        self.search_results = []
        self.playlist_source_url = ""

        for m, btn in self.mode_buttons.items():
            active = m == mode
            btn.configure(
                bg=ACCENT_PRIMARY if active else "#2D3748",
                fg="#FFFFFF" if active else TEXT_MAIN,
            )

        self.url_entry.delete(0, tk.END)
        self.status_lbl_analyze.configure(text="")
        self.update_mode_ui()
        self.reset_video_preview()
        self.clear_playlist_list()
        self.clear_search_results()

    def update_mode_ui(self):
        labels = {
            "video": ("Dirección URL del Enlace", "🔍 Analizar", "Información del Video"),
            "playlist": ("URL de la Playlist", "🔍 Analizar", "Vídeos de la Playlist"),
            "search": ("Término de búsqueda", "🔎 Buscar", "Resultados de Búsqueda"),
        }
        input_label, action_label, info_label = labels[self.app_mode]
        self.input_title.configure(text=input_label)
        self.btn_analyze.configure(text=action_label)
        self.info_title.configure(text=info_label)

        self.video_info_frame.pack_forget()
        self.playlist_info_frame.pack_forget()
        self.search_info_frame.pack_forget()

        if self.app_mode == "video":
            self.video_info_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        elif self.app_mode == "playlist":
            self.playlist_info_frame.pack(fill="both", expand=True)
        else:
            self.search_info_frame.pack(fill="both", expand=True)

    def reset_video_preview(self):
        self.thumb_canvas.delete("all")
        self.thumb_canvas.create_text(100, 56, text="Vista Previa", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))
        self.info_title_lbl.configure(text="Título: (Esperando enlace...)")
        self.info_author_lbl.configure(text="Canal: --")
        self.info_duration_lbl.configure(text="Duración: --")

    def clear_playlist_list(self):
        for widget in self.playlist_inner.winfo_children():
            widget.destroy()
        self.playlist_vars = []
        self.playlist_count_lbl.configure(text="0 vídeos encontrados")

    def clear_search_results(self):
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        self.search_results = []
        self.search_thumb_canvas.delete("all")
        self.search_thumb_canvas.create_text(100, 56, text="Vista Previa", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))
        self.search_preview_title.configure(text="Título: --")
        self.search_preview_channel.configure(text="Canal: --")

    def set_all_playlist_selection(self, selected):
        for var in self.playlist_vars:
            var.set(selected)
        self.update_playlist_selection_count()

    def update_playlist_selection_count(self):
        if not self.playlist_vars:
            self.playlist_count_lbl.configure(text="0 vídeos encontrados")
            return
        total = len(self.playlist_vars)
        selected = sum(1 for var in self.playlist_vars if var.get())
        self.playlist_count_lbl.configure(text=f"{total} vídeos encontrados ({selected} seleccionados)")

    def toggle_console(self):
        if self.console_expanded:
            self.console_frame.pack_forget()
            self.console_btn.configure(text="▶ Mostrar Consola de Salida (yt-dlp log)")
            self.console_expanded = False
        else:
            self.console_frame.pack(fill="x", padx=25, pady=(0, 20))
            self.console_btn.configure(text="▼ Ocultar Consola de Salida (yt-dlp log)")
            self.console_expanded = True

    def paste_url(self):
        try:
            content = self.clipboard_get()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, content)
        except tk.TclError:
            pass

    def browse_output_dir(self):
        dir_path = filedialog.askdirectory(initialdir=self.selected_output_dir)
        if dir_path:
            self.selected_output_dir = dir_path
            self.dest_entry.configure(state="normal")
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, self.selected_output_dir)
            self.dest_entry.configure(state="readonly")

    def log_message(self, message):
        self.after(0, self._append_log, message)

    def _append_log(self, message):
        self.console_text.configure(state="normal")
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.configure(state="disabled")

    def run_ytdlp_command(self, cmd):
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr

    def start_analyze(self):
        query = self.url_entry.get().strip()
        if not query:
            prompts = {
                "video": "Por favor, introduce una dirección URL válida primero.",
                "playlist": "Por favor, introduce la URL de una playlist primero.",
                "search": "Por favor, introduce un término de búsqueda primero.",
            }
            messagebox.showwarning("Entrada requerida", prompts[self.app_mode])
            return

        if self.is_analyzing or self.is_downloading:
            return

        self.is_analyzing = True
        self.btn_analyze.configure(state="disabled", bg="#374151")
        status_text = {
            "video": "🔍 Analizando enlace con yt-dlp...",
            "playlist": "🔍 Analizando playlist con yt-dlp...",
            "search": "🔎 Buscando vídeos con yt-dlp...",
        }
        self.status_lbl_analyze.configure(text=status_text[self.app_mode])

        if self.app_mode == "video":
            self.reset_video_preview()
            self.thumb_canvas.delete("all")
            self.thumb_canvas.create_text(100, 56, text="Analizando...", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))
            self.info_title_lbl.configure(text="Título: Cargando datos...")
        elif self.app_mode == "playlist":
            self.clear_playlist_list()
        else:
            self.clear_search_results()

        threading.Thread(target=self.analyze_thread, args=(query,), daemon=True).start()

    def analyze_thread(self, query):
        if self.app_mode == "video":
            cmd = [self.get_ytdlp_path(), "--dump-json", "--no-playlist", query]
        elif self.app_mode == "playlist":
            cmd = [self.get_ytdlp_path(), "--dump-json", "--flat-playlist", query]
        else:
            cmd = [self.get_ytdlp_path(), "--dump-json", "--flat-playlist", f"ytsearch15:{query}"]

        self.log_message(f"[System] Ejecutando análisis: {' '.join(cmd)}")
        try:
            returncode, stdout, stderr = self.run_ytdlp_command(cmd)
            if returncode == 0 and stdout.strip():
                if self.app_mode == "video":
                    data = json.loads(stdout)
                    self.after(0, self.analyze_video_success, data)
                elif self.app_mode == "playlist":
                    entries = parse_json_lines(stdout)
                    self.after(0, self.analyze_playlist_success, query, entries)
                else:
                    entries = parse_json_lines(stdout)
                    self.after(0, self.analyze_search_success, entries)
            else:
                self.log_message(f"[Error] Falló la extracción:\n{stderr}")
                self.after(0, self.analyze_fail, "Error al analizar. Compruebe la consola de salida.")
        except json.JSONDecodeError:
            self.log_message("[Error] La respuesta de yt-dlp no es JSON válido.")
            self.after(0, self.analyze_fail, "La respuesta de yt-dlp no es válida.")
        except Exception as e:
            self.log_message(f"[Error] Excepción en análisis: {str(e)}")
            self.after(0, self.analyze_fail, f"Ocurrió un error inesperado: {str(e)}")

    def analyze_fail(self, error_msg):
        self.is_analyzing = False
        self.btn_analyze.configure(state="normal", bg=ACCENT_PRIMARY)
        self.status_lbl_analyze.configure(text=f"❌ Error: {error_msg}")

        if self.app_mode == "video":
            self.thumb_canvas.delete("all")
            self.thumb_canvas.create_text(100, 56, text="Error", fill=ACCENT_DANGER, font=("Helvetica", 10, "bold"))
            self.info_title_lbl.configure(text="Título: Error al obtener detalles")

        messagebox.showerror("Error de Análisis", error_msg)

    def analyze_video_success(self, data):
        self.is_analyzing = False
        self.btn_analyze.configure(state="normal", bg=ACCENT_PRIMARY)
        self.status_lbl_analyze.configure(text="✅ Análisis completado con éxito.")
        self.current_video_info = data

        title = data.get("title", "Desconocido")
        author = data.get("uploader", data.get("channel", "Desconocido"))
        duration_str = format_duration(data.get("duration"))

        self.info_title_lbl.configure(text=f"Título: {title}")
        self.info_author_lbl.configure(text=f"Canal: {author}")
        self.info_duration_lbl.configure(text=f"Duración: {duration_str}")

        thumb_url = get_thumbnail_url(data)
        if thumb_url:
            threading.Thread(target=self.load_thumbnail, args=(thumb_url, "video"), daemon=True).start()
        else:
            self.thumb_canvas.delete("all")
            self.thumb_canvas.create_text(100, 56, text="Sin Miniatura", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))

    def analyze_playlist_success(self, url, entries):
        self.is_analyzing = False
        self.btn_analyze.configure(state="normal", bg=ACCENT_PRIMARY)

        playable = [e for e in entries if e.get("title") or e.get("id")]
        if not playable:
            self.analyze_fail("No se encontraron vídeos en la playlist.")
            return

        self.playlist_source_url = url
        self.playlist_entries = playable
        self.clear_playlist_list()

        for idx, entry in enumerate(playable):
            title = entry.get("title") or f"Vídeo {idx + 1}"
            duration = format_duration(entry.get("duration"))
            var = tk.BooleanVar(value=True)
            var.trace_add("write", lambda *_args: self.update_playlist_selection_count())
            self.playlist_vars.append(var)

            row = tk.Frame(self.playlist_inner, bg=BG_INPUT)
            row.pack(fill="x", padx=6, pady=2)

            chk = ttk.Checkbutton(row, variable=var, style="Card.TCheckbutton")
            chk.pack(side="left", padx=(4, 6))

            lbl = tk.Label(
                row,
                text=f"{idx + 1}. {title}  ({duration})",
                bg=BG_INPUT,
                fg=TEXT_MAIN,
                font=("Helvetica", 9),
                anchor="w",
                justify="left",
            )
            lbl.pack(side="left", fill="x", expand=True)

        self.update_playlist_selection_count()
        self.status_lbl_analyze.configure(text=f"✅ Playlist analizada: {len(playable)} vídeos encontrados.")

    def analyze_search_success(self, entries):
        self.is_analyzing = False
        self.btn_analyze.configure(state="normal", bg=ACCENT_PRIMARY)

        results = [e for e in entries if e.get("title") or e.get("id")]
        if not results:
            self.analyze_fail("No se encontraron resultados para la búsqueda.")
            return

        self.clear_search_results()
        self.search_results = results

        for idx, entry in enumerate(results):
            title = entry.get("title", "Sin título")
            duration = format_duration(entry.get("duration"))
            channel = entry.get("uploader") or entry.get("channel") or "--"
            self.search_tree.insert("", "end", iid=str(idx), values=(title, duration, channel))

        self.status_lbl_analyze.configure(text=f"✅ Búsqueda completada: {len(results)} resultados encontrados.")

    def on_search_result_select(self, event):
        selection = self.search_tree.selection()
        if not selection:
            return

        idx = int(selection[0])
        if idx < 0 or idx >= len(self.search_results):
            return

        entry = self.search_results[idx]
        title = entry.get("title", "Desconocido")
        channel = entry.get("uploader") or entry.get("channel") or "Desconocido"

        self.search_preview_title.configure(text=f"Título: {title}")
        self.search_preview_channel.configure(text=f"Canal: {channel}")
        self.current_video_info = entry

        thumb_url = get_thumbnail_url(entry)
        if thumb_url:
            threading.Thread(target=self.load_thumbnail, args=(thumb_url, "search"), daemon=True).start()
        else:
            self.search_thumb_canvas.delete("all")
            self.search_thumb_canvas.create_text(100, 56, text="Sin Miniatura", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))

    def load_thumbnail(self, url, target="video"):
        try:
            self.log_message(f"[System] Cargando miniatura: {url}")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                img.thumbnail((200, 112), Image.Resampling.LANCZOS)
                self.after(0, self.display_thumbnail, img, target)
            else:
                self.after(0, self.display_thumbnail_error, target)
        except Exception as e:
            self.log_message(f"[Warning] No se pudo cargar miniatura: {str(e)}")
            self.after(0, self.display_thumbnail_error, target)

    def display_thumbnail(self, img, target="video"):
        photo = ImageTk.PhotoImage(img)
        if target == "video":
            self._video_thumb_photo = photo
            canvas = self.thumb_canvas
        else:
            self._search_thumb_photo = photo
            canvas = self.search_thumb_canvas
        canvas.delete("all")
        canvas.create_image(100, 56, image=photo, anchor="center")

    def display_thumbnail_error(self, target="video"):
        canvas = self.thumb_canvas if target == "video" else self.search_thumb_canvas
        canvas.delete("all")
        canvas.create_text(100, 56, text="Miniatura N/A", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))

    def build_format_args(self):
        fmt_choice = self.fmt_combo.get()
        args = []

        if fmt_choice == "Video + Audio (Mejor Calidad)":
            args += ["-f", "bestvideo+bestaudio/best"]
        elif fmt_choice == "Video MP4 (1080p Máx)":
            args += ["-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"]
        elif fmt_choice == "Video MP4 (720p Máx)":
            args += ["-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]"]
        elif fmt_choice == "Video MP4 (480p Máx)":
            args += ["-f", "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]"]
        elif fmt_choice == "Solo Audio MP3 (Alta Calidad 320k)":
            args += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        elif fmt_choice == "Solo Audio M4A (Estándar)":
            args += ["-x", "--audio-format", "m4a"]
        elif fmt_choice == "Solo Audio WAV (Sin Pérdida)":
            args += ["-x", "--audio-format", "wav"]

        if self.subtitles_var.get():
            args += ["--write-subs", "--write-auto-subs", "--sub-langs", "es,en", "--embed-subs"]

        if self.metadata_var.get():
            args += ["--embed-metadata", "--embed-thumbnail"]

        return args

    def get_selected_playlist_indices(self):
        return [str(i + 1) for i, var in enumerate(self.playlist_vars) if var.get()]

    def start_download(self):
        if self.is_downloading:
            return

        if self.needs_ffmpeg() and not self.check_ffmpeg():
            messagebox.showerror(
                "FFmpeg no encontrado",
                "Esta descarga requiere FFmpeg (audio, subtítulos o metadatos).\n\n"
                "Instala FFmpeg y asegúrate de que esté disponible en el PATH del sistema.",
            )
            return

        if self.app_mode == "video":
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showwarning("Falta Enlace", "Por favor, introduce una dirección URL del vídeo primero.")
                return
            cmd = self.build_download_command(url)
        elif self.app_mode == "playlist":
            if not self.playlist_entries:
                messagebox.showwarning("Sin playlist", "Analiza una playlist y selecciona al menos un vídeo.")
                return
            selected = self.get_selected_playlist_indices()
            if not selected:
                messagebox.showwarning("Sin selección", "Selecciona al menos un vídeo de la playlist.")
                return
            cmd = self.build_download_command(
                self.playlist_source_url,
                playlist_items=",".join(selected),
            )
        else:
            selection = self.search_tree.selection()
            if not selection:
                messagebox.showwarning("Sin selección", "Selecciona un vídeo de los resultados de búsqueda.")
                return
            idx = int(selection[0])
            entry = self.search_results[idx]
            url = entry_url(entry)
            if not url:
                messagebox.showerror("Error", "No se pudo obtener la URL del vídeo seleccionado.")
                return
            cmd = self.build_download_command(url)

        self.begin_download(cmd)

    def build_download_command(self, url, playlist_items=None):
        out_template = os.path.join(self.selected_output_dir, "%(title)s.%(ext)s")
        cmd = [self.get_ytdlp_path(), "--newline", "-o", out_template]
        cmd += self.build_format_args()

        if playlist_items:
            cmd += ["--playlist-items", playlist_items]

        cmd.append(url)
        return cmd

    def snapshot_output_dir(self):
        output_dir = self.selected_output_dir
        if os.path.isdir(output_dir):
            self.files_before_download = set(os.listdir(output_dir))
        else:
            self.files_before_download = set()

    def cleanup_download_thumbnails(self):
        output_dir = self.selected_output_dir
        if not os.path.isdir(output_dir):
            return

        for name in os.listdir(output_dir):
            if name in self.files_before_download:
                continue

            path = os.path.join(output_dir, name)
            if not os.path.isfile(path):
                continue

            ext = os.path.splitext(name)[1].lower()
            if ext not in THUMBNAIL_EXTENSIONS:
                continue

            try:
                os.remove(path)
                self.log_message(f"[System] Miniatura residual eliminada: {name}")
            except OSError as e:
                self.log_message(f"[Warning] No se pudo eliminar miniatura {name}: {e}")

    def begin_download(self, cmd):
        self.snapshot_output_dir()
        self.is_downloading = True
        self.cancel_requested = False
        self.progress_bar.set_progress(0)
        self.progress_bar.set_color(ACCENT_PRIMARY)
        self.stat_status.configure(text="Estado: Preparando...")
        self.stat_speed.configure(text="Velocidad: --")
        self.stat_eta.configure(text="Restante: --")
        self.stat_size.configure(text="Tamaño: --")

        self.btn_download.configure(state="disabled", text="📥 DESCARGANDO...", bg="#374151")
        self.btn_cancel.configure(state="normal", bg=ACCENT_DANGER)

        self.log_message(f"[System] Iniciando descarga con el comando:\n{' '.join(cmd)}")
        threading.Thread(target=self.download_thread, args=(cmd,), daemon=True).start()

    def download_thread(self, cmd):
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.active_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
            )

            for line in self.active_process.stdout:
                line_str = line.strip()
                if line_str:
                    self.log_message(line_str)
                    self.after(0, self.parse_progress, line_str)

            self.active_process.wait()
            ret_code = self.active_process.returncode
            self.after(0, self.download_finished, ret_code)
        except Exception as e:
            self.log_message(f"[Error] Excepción en descarga: {str(e)}")
            self.after(0, self.download_finished, -1, str(e))

    def parse_progress(self, line):
        if "[download]" in line and "%" in line:
            match = re.search(
                r"\[download\]\s+(\d+(?:\.\d+)?)%\s+of\s+(\S+)\s+at\s+(\S+)\s+ETA\s+(\S+)",
                line,
            )
            if match:
                percentage = float(match.group(1))
                size = match.group(2)
                speed = match.group(3)
                eta = match.group(4)

                self.progress_bar.set_progress(percentage)
                self.stat_status.configure(text="Estado: Descargando...")
                self.stat_speed.configure(text=f"Velocidad: {speed}")
                self.stat_eta.configure(text=f"Restante: {eta}")
                self.stat_size.configure(text=f"Tamaño: {size}")
            elif "100%" in line or "has already been downloaded" in line:
                self.progress_bar.set_progress(100)
                self.stat_status.configure(text="Estado: Finalizando...")
        elif "[ExtractAudio]" in line:
            self.stat_status.configure(text="Estado: Extrayendo Audio (FFmpeg)...")
            self.progress_bar.set_color(ACCENT_HOVER)
        elif "[ffmpeg]" in line and "Merging formats" in line:
            self.stat_status.configure(text="Estado: Uniendo Video y Audio...")
            self.progress_bar.set_color(ACCENT_HOVER)
        elif "[Metadata]" in line:
            self.stat_status.configure(text="Estado: Escribiendo metadatos...")
        elif "[ThumbnailsConvertor]" in line or "EmbedThumbnail" in line:
            self.stat_status.configure(text="Estado: Incrustando miniatura...")

    def cancel_download(self):
        if self.active_process and self.is_downloading:
            self.cancel_requested = True
            self.log_message("[System] Cancelación solicitada por el usuario.")
            try:
                self.active_process.terminate()
                self.stat_status.configure(text="Estado: Cancelado")
            except Exception as e:
                self.log_message(f"[Warning] Error al finalizar proceso: {str(e)}")

    def download_finished(self, return_code, err_msg=""):
        self.is_downloading = False
        self.active_process = None

        self.btn_download.configure(state="normal", text="📥 INICIAR DESCARGA", bg=ACCENT_SUCCESS)
        self.btn_cancel.configure(state="disabled", bg="#374151")

        if self.cancel_requested:
            self.cancel_requested = False
            self.progress_bar.set_progress(0)
            self.stat_status.configure(text="Estado: Cancelado por el usuario ⏹")
            messagebox.showwarning("Descarga Cancelada", "La descarga ha sido interrumpida.")
        elif return_code == 0:
            self.cleanup_download_thumbnails()
            self.progress_bar.set_progress(100)
            self.progress_bar.set_color(ACCENT_SUCCESS)
            self.stat_status.configure(text="Estado: Completado ✅")
            self.stat_speed.configure(text="Velocidad: --")
            self.stat_eta.configure(text="Restante: 00:00")
            messagebox.showinfo("Descarga Exitosa", "El archivo se ha descargado correctamente en la carpeta de destino.")
        else:
            self.progress_bar.set_color(ACCENT_DANGER)
            self.stat_status.configure(text="Estado: Error ❌")
            error_desc = err_msg or "Ocurrió un error durante la descarga. Por favor, revise el log de la consola para más detalles."
            messagebox.showerror("Error de Descarga", error_desc)


if __name__ == "__main__":
    ext = ".exe" if sys.platform == "win32" else ""
    local_path = os.path.join(get_app_data_dir(), f"yt-dlp{ext}")
    has_local = os.path.exists(local_path) and (sys.platform == "win32" or os.access(local_path, os.X_OK))
    has_system = shutil.which(f"yt-dlp{ext}") is not None

    if not has_local and not has_system:
        root = tk.Tk()
        root.withdraw()
        ans = messagebox.askyesno(
            "Falta Motor de Descarga",
            "No se ha encontrado 'yt-dlp' ni localmente ni en tu sistema.\n\n"
            "¿Deseas descargar automáticamente la última versión desde GitHub?",
        )
        if ans:
            download_win = tk.Tk()
            download_win.title("Descargando yt-dlp...")
            download_win.geometry("420x130")
            download_win.configure(bg=BG_MAIN)

            download_win.update_idletasks()
            w = download_win.winfo_width()
            h = download_win.winfo_height()
            x = (download_win.winfo_screenwidth() // 2) - (w // 2)
            y = (download_win.winfo_screenheight() // 2) - (h // 2)
            download_win.geometry(f"+{x}+{y}")

            lbl = tk.Label(
                download_win,
                text="Descargando la última versión de yt-dlp...",
                bg=BG_MAIN,
                fg=TEXT_MAIN,
                font=("Helvetica", 11, "bold"),
            )
            lbl.pack(pady=20)

            progress_lbl = tk.Label(
                download_win,
                text="Conectando con GitHub y descargando archivo...",
                bg=BG_MAIN,
                fg=TEXT_MUTED,
                font=("Helvetica", 9),
            )
            progress_lbl.pack()

            error_occurred = [None]

            def do_download():
                try:
                    app_data_dir = get_app_data_dir()
                    os.makedirs(app_data_dir, exist_ok=True)
                    url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp{ext}"
                    r = requests.get(url, stream=True, timeout=20)
                    if r.status_code == 200:
                        with open(local_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                        if sys.platform != "win32":
                            os.chmod(local_path, 0o755)
                    else:
                        error_occurred[0] = f"HTTP Error {r.status_code}"
                except Exception as e:
                    error_occurred[0] = str(e)
                download_win.quit()

            download_win.update()
            threading.Thread(target=do_download, daemon=True).start()
            download_win.mainloop()
            download_win.destroy()

            if error_occurred[0]:
                messagebox.showerror("Error", f"No se pudo descargar el motor:\n{error_occurred[0]}")
                sys.exit(1)
        else:
            sys.exit(1)

    app = YtDlpGUI()
    app.mainloop()
