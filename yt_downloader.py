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
from urllib.parse import urlparse
import requests
from PIL import Image, ImageTk

# Color Palette (Dark Theme / Sleek Indigo)
BG_MAIN = "#121214"         # Very dark gray/black background
BG_CARD = "#1E1E24"         # Dark card/panel background
BG_INPUT = "#2A2A32"        # Dark input background
BORDER_COLOR = "#374151"    # Gray border color
BORDER_FOCUS = "#6366F1"    # Indigo focus color
TEXT_MAIN = "#F9FAFB"       # Near white text
TEXT_MUTED = "#9CA3AF"      # Slate gray muted text
ACCENT_PRIMARY = "#4F46E5"  # Indigo primary button
ACCENT_HOVER = "#6366F1"    # Indigo hover
ACCENT_SUCCESS = "#10B981"  # Emerald success/download
ACCENT_SUCCESS_HOV = "#059669" # Emerald success hover
ACCENT_DANGER = "#EF4444"   # Red cancel
ACCENT_DANGER_HOV = "#DC2626" # Red cancel hover
BG_CONSOLE = "#0A0A0C"      # Monospaced console dark bg

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



class CanvasProgressBar(tk.Canvas):
    """A sleek, custom modern progress bar using Canvas for maximum styling control."""
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
        self.geometry("920x720")
        self.configure(bg=BG_MAIN)
        self.minsize(800, 600)
        
        # Center the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
        
        # State variables
        self.selected_output_dir = self.get_default_download_dir()
        self.current_video_info = None
        self.active_process = None
        self.is_downloading = False
        self.is_analyzing = False
        self.thumbnail_photo = None
        
        # Setup modern style
        self.setup_styles()
        
        # Container frame for switching screens
        self.container = tk.Frame(self, bg=BG_MAIN)
        self.container.pack(fill="both", expand=True)
        
        # Start with the Legal Disclaimer Screen
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
        
        import shutil
        sys_path = shutil.which(f"yt-dlp{ext}")
        if sys_path:
            return sys_path
            
        return f"yt-dlp{ext}"

    def update_ytdlp(self):
        if self.is_downloading or self.is_analyzing:
            messagebox.showwarning("Acción no disponible", "No puedes actualizar el motor de descarga mientras haya un análisis o descarga activa.")
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
                    self.after(0, self.update_ytdlp_success)
                else:
                    self.after(0, self.update_ytdlp_fail, f"Error HTTP {r.status_code}")
            except Exception as e:
                self.after(0, self.update_ytdlp_fail, str(e))
                
        threading.Thread(target=run_update, daemon=True).start()

    def update_ytdlp_success(self):
        self.btn_update_engine.configure(state="normal", text="🔄 Actualizar Motor (yt-dlp)")
        self.log_message("[System] El motor yt-dlp se ha actualizado correctamente en bin/yt-dlp.")
        messagebox.showinfo("Motor Actualizado", "El motor yt-dlp se ha actualizado correctamente a la última versión de GitHub.")

    def update_ytdlp_fail(self, err_msg):
        self.btn_update_engine.configure(state="normal", text="🔄 Actualizar Motor (yt-dlp)")
        self.log_message(f"[Error] Falló la actualización de yt-dlp: {err_msg}")
        messagebox.showerror("Error de Actualización", f"No se pudo descargar la actualización de yt-dlp:\n{err_msg}")

    def setup_styles(self):
        self.style = ttk.Style()
        # Use clam theme as base for customization
        self.style.theme_use("clam")
        
        # Configure TFrame
        self.style.configure("TFrame", background=BG_MAIN)
        self.style.configure("Card.TFrame", background=BG_CARD, relief="flat", borderwidth=0)
        
        # Configure TLabel
        self.style.configure("TLabel", background=BG_MAIN, foreground=TEXT_MAIN, font=("Helvetica", 10))
        self.style.configure("Header.TLabel", background=BG_MAIN, foreground=TEXT_MAIN, font=("Helvetica", 20, "bold"))
        self.style.configure("Subtitle.TLabel", background=BG_MAIN, foreground=TEXT_MUTED, font=("Helvetica", 10, "italic"))
        self.style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_MAIN, font=("Helvetica", 10))
        self.style.configure("CardTitle.TLabel", background=BG_CARD, foreground=TEXT_MAIN, font=("Helvetica", 12, "bold"))
        self.style.configure("Muted.TLabel", background=BG_CARD, foreground=TEXT_MUTED, font=("Helvetica", 9))
        self.style.configure("MutedBold.TLabel", background=BG_CARD, foreground=TEXT_MUTED, font=("Helvetica", 9, "bold"))
        
        # Configure TCheckbutton (styled for dark mode)
        self.style.configure("Card.TCheckbutton", 
                             background=BG_CARD, 
                             foreground=TEXT_MAIN, 
                             activebackground=BG_CARD, 
                             activeforeground=TEXT_MAIN,
                             font=("Helvetica", 10))
        self.style.map("Card.TCheckbutton",
                       background=[("active", BG_CARD), ("selected", BG_CARD)],
                       foreground=[("active", TEXT_MAIN), ("selected", TEXT_MAIN)])
        
        # Configure TCombobox
        self.style.configure("TCombobox", 
                             fieldbackground=BG_INPUT, 
                             background=BG_CARD, 
                             foreground=TEXT_MAIN, 
                             arrowcolor=TEXT_MAIN,
                             bordercolor=BORDER_COLOR, 
                             lightcolor=BORDER_COLOR, 
                             darkcolor=BORDER_COLOR,
                             font=("Helvetica", 10))
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", BG_INPUT)],
                       foreground=[("readonly", TEXT_MAIN)])

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def make_flat_button(self, parent, text, bg, fg, hover_bg, font, command, state="normal"):
        """Utility to create a highly styled flat button with hover micro-animations."""
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
            state=state
        )
        
        # Hover effect bindings
        def on_enter(e):
            if btn["state"] == "normal":
                btn.configure(bg=hover_bg)
        def on_leave(e):
            if btn["state"] == "normal":
                btn.configure(bg=bg)
                
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    # ==========================================
    # SCREEN 1: LEGAL DISCLAIMER SCREEN
    # ==========================================
    def show_disclaimer(self):
        self.clear_container()
        
        # Main overlay card
        disclaimer_card = tk.Frame(self.container, bg=BG_CARD, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1)
        disclaimer_card.place(relx=0.5, rely=0.5, anchor="center", width=680, height=480)
        
        # Title bar or warning indicator
        warning_icon_label = tk.Label(disclaimer_card, text="⚠️", font=("Helvetica", 48), bg=BG_CARD, fg="#F59E0B")
        warning_icon_label.pack(pady=(30, 10))
        
        title_label = tk.Label(disclaimer_card, text="AVISO DE USO Y RESPONSABILIDAD", font=("Helvetica", 16, "bold"), bg=BG_CARD, fg=TEXT_MAIN)
        title_label.pack(pady=5)
        
        divider = tk.Frame(disclaimer_card, height=1, bg=BORDER_COLOR)
        divider.pack(fill="x", padx=40, pady=10)
        
        # Disclaimer text
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
            height=8
        )
        text_widget.insert("1.0", text_content)
        text_widget.configure(state="disabled")
        
        # Buttons frame (packed first at the bottom to guarantee space/visibility)
        btn_frame = tk.Frame(disclaimer_card, bg=BG_CARD)
        btn_frame.pack(side="bottom", fill="x", pady=(0, 30))
        
        # Exit Button
        btn_exit = self.make_flat_button(
            btn_frame,
            "Declinar y Salir",
            bg="#374151",
            fg=TEXT_MAIN,
            hover_bg="#4B5563",
            font=("Helvetica", 10, "bold"),
            command=self.quit
        )
        btn_exit.pack(side="left", padx=(100, 10), expand=True, fill="x")
        
        # Accept Button
        btn_accept = self.make_flat_button(
            btn_frame,
            "Aceptar e Iniciar",
            bg=ACCENT_PRIMARY,
            fg="#FFFFFF",
            hover_bg=ACCENT_HOVER,
            font=("Helvetica", 10, "bold"),
            command=self.accept_disclaimer
        )
        btn_accept.pack(side="right", padx=(10, 100), expand=True, fill="x")

        # Text widget (packed to fill remaining center space)
        text_widget.pack(side="top", fill="both", expand=True, padx=40, pady=(5, 10))

    def accept_disclaimer(self):
        # Proceed to load the Main Application
        self.show_main_app()

    # ==========================================
    # SCREEN 2: MAIN APPLICATION SCREEN
    # ==========================================
    def show_main_app(self):
        self.clear_container()
        
        # Top Header Panel
        header_frame = tk.Frame(self.container, bg=BG_MAIN)
        header_frame.pack(fill="x", padx=25, pady=(20, 15))
        
        title_lbl = ttk.Label(header_frame, text="📥 Yt-Dlp GUI Media Downloader", style="Header.TLabel")
        title_lbl.pack(anchor="w")
        sub_lbl = ttk.Label(header_frame, text="Utility interface for downloading personal content through yt-dlp.", style="Subtitle.TLabel")
        sub_lbl.pack(anchor="w", pady=(2, 0))
        
        # Main Layout: 2 Columns or stacked sections. Let's stack them nicely with frames.
        # Section 1: URL input Card
        url_card = tk.Frame(self.container, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        url_card.pack(fill="x", padx=25, pady=(0, 15))
        
        url_title = ttk.Label(url_card, text="Dirección URL del Enlace", style="CardTitle.TLabel")
        url_title.pack(anchor="w", padx=20, pady=(15, 5))
        
        url_row = tk.Frame(url_card, bg=BG_CARD)
        url_row.pack(fill="x", padx=20, pady=(0, 15))
        
        # Modern entry field wrap
        self.entry_border = tk.Frame(url_row, bg=BORDER_COLOR, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=BORDER_FOCUS)
        self.entry_border.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.url_entry = tk.Entry(
            self.entry_border,
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            relief="flat",
            bd=0,
            font=("Helvetica", 11)
        )
        self.url_entry.pack(fill="both", expand=True, padx=8, pady=8)
        self.url_entry.bind("<FocusIn>", lambda e: self.entry_border.configure(highlightbackground=BORDER_FOCUS))
        self.url_entry.bind("<FocusOut>", lambda e: self.entry_border.configure(highlightbackground=BORDER_COLOR))
        self.url_entry.bind("<Return>", lambda e: self.start_analyze())
        self.url_entry.insert(0, "") # start empty
        
        # Action Buttons for URL
        self.btn_paste = self.make_flat_button(
            url_row,
            "📋 Pegar",
            bg="#2D3748",
            fg=TEXT_MAIN,
            hover_bg="#4A5568",
            font=("Helvetica", 10, "bold"),
            command=self.paste_url
        )
        self.btn_paste.pack(side="left", padx=(0, 5), ipady=4, ipadx=10)
        
        self.btn_analyze = self.make_flat_button(
            url_row,
            "🔍 Analizar",
            bg=ACCENT_PRIMARY,
            fg="#FFFFFF",
            hover_bg=ACCENT_HOVER,
            font=("Helvetica", 10, "bold"),
            command=self.start_analyze
        )
        self.btn_analyze.pack(side="left", ipady=4, ipadx=15)

        # Loading overlay / Label for analyzer
        self.status_lbl_analyze = ttk.Label(url_card, text="", style="Subtitle.TLabel", background=BG_CARD)
        self.status_lbl_analyze.pack(anchor="w", padx=20, pady=(0, 10))

        # Section 2: Info & Settings Split (Two cards side-by-side)
        self.split_frame = tk.Frame(self.container, bg=BG_MAIN)
        self.split_frame.pack(fill="both", expand=True, padx=25, pady=(0, 15))
        
        # Left Panel: Video Info Card
        self.info_card = tk.Frame(self.split_frame, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.info_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        info_title = ttk.Label(self.info_card, text="Información del Video", style="CardTitle.TLabel")
        info_title.pack(anchor="w", padx=20, pady=15)
        
        # Placeholders inside Info Card
        self.info_content_frame = tk.Frame(self.info_card, bg=BG_CARD)
        self.info_content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        # Visual thumbnail placeholder
        self.thumb_canvas = tk.Canvas(self.info_content_frame, width=200, height=112, bg=BG_INPUT, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.thumb_canvas.pack(anchor="w", pady=(0, 10))
        self.thumb_rect = self.thumb_canvas.create_text(100, 56, text="Vista Previa", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))
        
        self.info_title_lbl = ttk.Label(self.info_content_frame, text="Título: (Esperando enlace...)", style="Card.TLabel", wraplength=220)
        self.info_title_lbl.pack(anchor="w", pady=2)
        
        self.info_author_lbl = ttk.Label(self.info_content_frame, text="Canal: --", style="Muted.TLabel")
        self.info_author_lbl.pack(anchor="w", pady=2)
        
        self.info_duration_lbl = ttk.Label(self.info_content_frame, text="Duración: --", style="Muted.TLabel")
        self.info_duration_lbl.pack(anchor="w", pady=2)
        
        # Right Panel: Download Settings Card
        self.settings_card = tk.Frame(self.split_frame, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.settings_card.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        settings_title = ttk.Label(self.settings_card, text="Ajustes de Descarga", style="CardTitle.TLabel")
        settings_title.pack(anchor="w", padx=20, pady=15)
        
        self.settings_content_frame = tk.Frame(self.settings_card, bg=BG_CARD)
        self.settings_content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        # Format Dropdown
        fmt_lbl = ttk.Label(self.settings_content_frame, text="Formato y Calidad", style="Card.TLabel")
        fmt_lbl.pack(anchor="w", pady=(0, 5))
        
        self.format_options = [
            "Video + Audio (Mejor Calidad)",
            "Video MP4 (1080p Máx)",
            "Video MP4 (720p Máx)",
            "Video MP4 (480p Máx)",
            "Solo Audio MP3 (Alta Calidad 320k)",
            "Solo Audio M4A (Estándar)",
            "Solo Audio WAV (Sin Pérdida)"
        ]
        self.fmt_combo = ttk.Combobox(self.settings_content_frame, values=self.format_options, state="readonly", style="TCombobox")
        self.fmt_combo.set("Video + Audio (Mejor Calidad)")
        self.fmt_combo.pack(fill="x", pady=(0, 12))
        
        # Output Folder Selection
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
            font=("Helvetica", 9)
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
            command=self.browse_output_dir
        )
        self.btn_browse.pack(side="right", ipady=3, ipadx=8)
        
        # Additional Options
        self.subtitles_var = tk.BooleanVar(value=False)
        self.subs_chk = ttk.Checkbutton(
            self.settings_content_frame, 
            text="Descargar y acoplar subtítulos (es/en)", 
            variable=self.subtitles_var, 
            style="Card.TCheckbutton"
        )
        self.subs_chk.pack(anchor="w", pady=4)
        
        self.metadata_var = tk.BooleanVar(value=True)
        self.meta_chk = ttk.Checkbutton(
            self.settings_content_frame, 
            text="Incrustar metadatos y miniatura en archivo", 
            variable=self.metadata_var, 
            style="Card.TCheckbutton"
        )
        self.meta_chk.pack(anchor="w", pady=4)
        
        # Update engine button
        self.btn_update_engine = self.make_flat_button(
            self.settings_content_frame,
            "🔄 Actualizar Motor (yt-dlp)",
            bg="#2D3748",
            fg=TEXT_MAIN,
            hover_bg="#4A5568",
            font=("Helvetica", 9, "bold"),
            command=self.update_ytdlp
        )
        self.btn_update_engine.pack(anchor="w", pady=(10, 0), fill="x")
        
        # Section 3: Progress & Output Card
        progress_card = tk.Frame(self.container, bg=BG_CARD, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        progress_card.pack(fill="x", padx=25, pady=(0, 15))
        
        p_row = tk.Frame(progress_card, bg=BG_CARD)
        p_row.pack(fill="x", padx=20, pady=(15, 10))
        
        # Download Button
        self.btn_download = self.make_flat_button(
            p_row,
            "📥 INICIAR DESCARGA",
            bg=ACCENT_SUCCESS,
            fg="#FFFFFF",
            hover_bg=ACCENT_SUCCESS_HOV,
            font=("Helvetica", 11, "bold"),
            command=self.start_download
        )
        self.btn_download.pack(side="left", fill="both", expand=True, padx=(0, 10), ipady=6)
        
        # Cancel Download Button
        self.btn_cancel = self.make_flat_button(
            p_row,
            "⏹ Cancelar",
            bg=ACCENT_DANGER,
            fg="#FFFFFF",
            hover_bg=ACCENT_DANGER_HOV,
            font=("Helvetica", 10, "bold"),
            command=self.cancel_download,
            state="disabled"
        )
        self.btn_cancel.pack(side="right", ipady=6, ipadx=20)
        self.btn_cancel.configure(bg="#374151") # styled as disabled initially
        
        # Progress Bar Frame
        pbar_row = tk.Frame(progress_card, bg=BG_CARD)
        pbar_row.pack(fill="x", padx=20, pady=(0, 5))
        
        self.progress_bar = CanvasProgressBar(pbar_row, height=14)
        self.progress_bar.pack(fill="x")
        
        # Statistics Row
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
        
        # Section 4: Expandable Console Log
        self.console_btn = self.make_flat_button(
            self.container,
            "▶ Mostrar Consola de Salida (yt-dlp log)",
            bg="#1E1E24",
            fg=TEXT_MUTED,
            hover_bg="#2D3748",
            font=("Helvetica", 9),
            command=self.toggle_console
        )
        self.console_btn.pack(fill="x", padx=25, pady=(0, 5))
        
        self.console_frame = tk.Frame(self.container, bg=BG_CONSOLE)
        # Hidden initially
        
        self.console_text = tk.Text(
            self.console_frame,
            bg=BG_CONSOLE,
            fg="#10B981", # Matrix green text
            font=("Courier", 9),
            relief="flat",
            bd=0,
            highlightthickness=0,
            state="disabled",
            wrap="word",
            height=8
        )
        self.console_text.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        
        console_scroll = ttk.Scrollbar(self.console_frame, command=self.console_text.yview)
        console_scroll.pack(side="right", fill="y")
        self.console_text.configure(yscrollcommand=console_scroll.set)
        
        self.console_expanded = False

    def toggle_console(self):
        if self.console_expanded:
            self.console_frame.pack_forget()
            self.console_btn.configure(text="▶ Mostrar Consola de Salida (yt-dlp log)")
            self.console_expanded = False
        else:
            self.console_frame.pack(fill="x", padx=25, pady=(0, 20))
            self.console_btn.configure(text="▼ Ocultar Consola de Salida (yt-dlp log)")
            self.console_expanded = True

    # ==========================================
    # USER INTERACTIONS & LOGIC
    # ==========================================
    def paste_url(self):
        try:
            url = self.clipboard_get()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, url)
        except Exception:
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
        """Append messages to the custom log console in a thread-safe way."""
        self.console_text.configure(state="normal")
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.configure(state="disabled")

    # ==========================================
    # STAGE 1: METADATA EXTRACTION (ANALYSIS)
    # ==========================================
    def start_analyze(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Falta Enlace", "Por favor, introduce una dirección URL válida primero.")
            return
            
        if self.is_analyzing or self.is_downloading:
            return
            
        self.is_analyzing = True
        self.btn_analyze.configure(state="disabled", bg="#374151")
        self.status_lbl_analyze.configure(text="🔍 Analizando enlace con yt-dlp... (Espere por favor)")
        
        # Reset Thumbnail to preview placeholder
        self.thumb_canvas.delete("all")
        self.thumb_rect = self.thumb_canvas.create_text(100, 56, text="Analizando...", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))
        self.info_title_lbl.configure(text="Título: Cargando datos...")
        self.info_author_lbl.configure(text="Canal: --")
        self.info_duration_lbl.configure(text="Duración: --")
        
        # Spawn thread for analytical subprocess
        thread = threading.Thread(target=self.analyze_thread, args=(url,), daemon=True)
        thread.start()

    def analyze_thread(self, url):
        cmd = [self.get_ytdlp_path(), "--dump-json", "--no-playlist", "--flat-playlist", url]
        
        self.log_message(f"[System] Ejecutando análisis: {' '.join(cmd)}")
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout)
                self.after(0, self.analyze_success, data)
            else:
                self.log_message(f"[Error] Falló la extracción:\n{stderr}")
                self.after(0, self.analyze_fail, "Error al analizar el enlace. Compruebe la consola de salida.")
        except Exception as e:
            self.log_message(f"[Error] Excepción en análisis: {str(e)}")
            self.after(0, self.analyze_fail, f"Ocurrió un error inesperado: {str(e)}")

    def analyze_success(self, data):
        self.is_analyzing = False
        self.btn_analyze.configure(state="normal", bg=ACCENT_PRIMARY)
        self.status_lbl_analyze.configure(text="✅ Análisis completado con éxito.")
        
        self.current_video_info = data
        
        # Update Info fields
        title = data.get("title", "Desconocido")
        author = data.get("uploader", data.get("channel", "Desconocido"))
        
        # Calculate duration string
        duration_sec = data.get("duration")
        if duration_sec:
            hours = duration_sec // 3600
            minutes = (duration_sec % 3600) // 60
            seconds = duration_sec % 60
            if hours > 0:
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes:02d}:{seconds:02d}"
        else:
            duration_str = "Transmisión en vivo / Desconocida"
            
        self.info_title_lbl.configure(text=f"Título: {title}")
        self.info_author_lbl.configure(text=f"Canal: {author}")
        self.info_duration_lbl.configure(text=f"Duración: {duration_str}")
        
        # Load thumbnail in background
        thumb_url = data.get("thumbnail")
        if thumb_url:
            threading.Thread(target=self.load_thumbnail, args=(thumb_url,), daemon=True).start()
        else:
            self.thumb_canvas.delete("all")
            self.thumb_rect = self.thumb_canvas.create_text(100, 56, text="Sin Miniatura", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))

    def analyze_fail(self, error_msg):
        self.is_analyzing = False
        self.btn_analyze.configure(state="normal", bg=ACCENT_PRIMARY)
        self.status_lbl_analyze.configure(text=f"❌ Error: {error_msg}")
        
        self.thumb_canvas.delete("all")
        self.thumb_rect = self.thumb_canvas.create_text(100, 56, text="Error", fill=ACCENT_DANGER, font=("Helvetica", 10, "bold"))
        self.info_title_lbl.configure(text="Título: Error al obtener detalles")
        messagebox.showerror("Error de Análisis", error_msg)

    def load_thumbnail(self, url):
        try:
            self.log_message(f"[System] Cargando miniatura: {url}")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                img_data = response.content
                img = Image.open(io.BytesIO(img_data))
                
                # Resize keeping scale aspect
                img.thumbnail((200, 112), Image.Resampling.LANCZOS)
                
                # Render to screen on main thread
                self.after(0, self.display_thumbnail, img)
            else:
                self.after(0, self.display_thumbnail_error)
        except Exception as e:
            self.log_message(f"[Warning] No se pudo cargar miniatura: {str(e)}")
            self.after(0, self.display_thumbnail_error)

    def display_thumbnail(self, img):
        self.thumbnail_photo = ImageTk.PhotoImage(img)
        self.thumb_canvas.delete("all")
        # Canvas dimensions 200x112
        self.thumb_canvas.create_image(100, 56, image=self.thumbnail_photo, anchor="center")

    def display_thumbnail_error(self):
        self.thumb_canvas.delete("all")
        self.thumb_rect = self.thumb_canvas.create_text(100, 56, text="Miniatura N/A", fill=TEXT_MUTED, font=("Helvetica", 10, "bold"))

    # ==========================================
    # STAGE 2: DOWNLOAD EXECUTION
    # ==========================================
    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Falta Enlace", "Por favor, introduce una dirección URL del video primero.")
            return
            
        if self.is_downloading:
            return
            
        # UI updates to active download state
        self.is_downloading = True
        self.progress_bar.set_progress(0)
        self.progress_bar.set_color(ACCENT_PRIMARY)
        self.stat_status.configure(text="Estado: Preparando...")
        self.stat_speed.configure(text="Velocidad: --")
        self.stat_eta.configure(text="Restante: --")
        self.stat_size.configure(text="Tamaño: --")
        
        self.btn_download.configure(state="disabled", text="📥 DESCARGANDO...", bg="#374151")
        self.btn_cancel.configure(state="normal", bg=ACCENT_DANGER)
        
        # Build command based on dropdown options
        fmt_choice = self.fmt_combo.get()
        out_template = os.path.join(self.selected_output_dir, "%(title)s.%(ext)s")
        
        cmd = [self.get_ytdlp_path(), "--newline", "-o", out_template]
        
        # Apply Format filters
        if fmt_choice == "Video + Audio (Mejor Calidad)":
            cmd += ["-f", "bestvideo+bestaudio/best"]
        elif fmt_choice == "Video MP4 (1080p Máx)":
            cmd += ["-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"]
        elif fmt_choice == "Video MP4 (720p Máx)":
            cmd += ["-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]"]
        elif fmt_choice == "Video MP4 (480p Máx)":
            cmd += ["-f", "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]"]
        elif fmt_choice == "Solo Audio MP3 (Alta Calidad 320k)":
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        elif fmt_choice == "Solo Audio M4A (Estándar)":
            cmd += ["-x", "--audio-format", "m4a"]
        elif fmt_choice == "Solo Audio WAV (Sin Pérdida)":
            cmd += ["-x", "--audio-format", "wav"]
            
        # Apply subtitle flags
        if self.subtitles_var.get():
            cmd += ["--write-subs", "--write-auto-subs", "--sub-langs", "es,en", "--embed-subs"]
            
        # Apply metadata/thumbnail embedding flags
        if self.metadata_var.get():
            cmd += ["--embed-metadata"]
            # embedding thumbnail in audio needs ffmpeg and works well, same for videos (into MKV/MP4)
            cmd += ["--embed-thumbnail"]
            
        cmd.append(url)
        
        self.log_message(f"[System] Iniciando descarga con el comando:\n{' '.join(cmd)}")
        
        # Spawn download execution thread
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
                stderr=subprocess.STDOUT, # pipe stderr to stdout to catch all errors
                text=True,
                bufsize=1,
                startupinfo=startupinfo
            )
            
            # Read real-time output
            for line in self.active_process.stdout:
                line_str = line.strip()
                if line_str:
                    self.after(0, self.log_message, line_str)
                    self.after(0, self.parse_progress, line_str)
                    
            self.active_process.wait()
            ret_code = self.active_process.returncode
            self.after(0, self.download_finished, ret_code)
            
        except Exception as e:
            self.log_message(f"[Error] Excepción en descarga: {str(e)}")
            self.after(0, self.download_finished, -1, str(e))

    def parse_progress(self, line):
        """Parse yt-dlp console output line-by-line to extract downloading progress values."""
        # Standard progress format: [download]  45.2% of 82.35MiB at 4.21MiB/s ETA 00:09
        if "[download]" in line and "%" in line:
            # Clean spaces
            clean_line = re.sub(r'\s+', ' ', line)
            
            # Matches: percentage, total size, speed, ETA
            # Pattern: [download] <perc>% of <size> at <speed> ETA <eta>
            match = re.search(r'\[download\]\s+(\d+(?:\.\d+)?)%\s+of\s+(\S+)\s+at\s+(\S+)\s+ETA\s+(\S+)', line)
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
                
        # Parse post-processing / ffmpeg conversions
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
            self.log_message("[System] Cancelación solicitada por el usuario.")
            try:
                self.active_process.terminate()
                self.stat_status.configure(text="Estado: Cancelado")
            except Exception as e:
                self.log_message(f"[Warning] Error al finalizar proceso: {str(e)}")
            self.is_downloading = False

    def download_finished(self, return_code, err_msg=""):
        self.is_downloading = False
        self.active_process = None
        
        # Reset buttons state
        self.btn_download.configure(state="normal", text="📥 INICIAR DESCARGA", bg=ACCENT_SUCCESS)
        self.btn_cancel.configure(state="disabled", bg="#374151")
        
        if return_code == 0:
            self.progress_bar.set_progress(100)
            self.progress_bar.set_color(ACCENT_SUCCESS)
            self.stat_status.configure(text="Estado: Completado ✅")
            self.stat_speed.configure(text="Velocidad: --")
            self.stat_eta.configure(text="Restante: 00:00")
            messagebox.showinfo("Descarga Exitosa", "El archivo se ha descargado correctamente en la carpeta de destino.")
        elif return_code == -1 and not err_msg:
            # User cancellation
            self.progress_bar.set_progress(0)
            self.stat_status.configure(text="Estado: Cancelado por el usuario ⏹")
            messagebox.showwarning("Descarga Cancelada", "La descarga ha sido interrumpida.")
        else:
            # Error occurred
            self.progress_bar.set_color(ACCENT_DANGER)
            self.stat_status.configure(text="Estado: Error ❌")
            error_desc = err_msg if err_msg else "Ocurrió un error durante la descarga. Por favor, revise el log de la consola para más detalles."
            messagebox.showerror("Error de Descarga", error_desc)


if __name__ == "__main__":
    ext = ".exe" if sys.platform == "win32" else ""
    # Check if we have yt-dlp locally or on the system
    local_path = os.path.join(get_app_data_dir(), f"yt-dlp{ext}")
    has_local = os.path.exists(local_path) and (sys.platform == "win32" or os.access(local_path, os.X_OK))
    
    import shutil
    has_system = shutil.which(f"yt-dlp{ext}") is not None
    
    if not has_local and not has_system:
        # Prompt to download it automatically
        root = tk.Tk()
        root.withdraw()
        ans = messagebox.askyesno(
            "Falta Motor de Descarga",
            "No se ha encontrado 'yt-dlp' ni localmente ni en tu sistema.\n\n"
            "¿Deseas descargar automáticamente la última versión desde GitHub?"
        )
        if ans:
            # Show download visual window
            download_win = tk.Tk()
            download_win.title("Descargando yt-dlp...")
            download_win.geometry("420x130")
            download_win.configure(bg=BG_MAIN)
            
            # Center download window
            download_win.update_idletasks()
            w = download_win.winfo_width()
            h = download_win.winfo_height()
            x = (download_win.winfo_screenwidth() // 2) - (w // 2)
            y = (download_win.winfo_screenheight() // 2) - (h // 2)
            download_win.geometry(f"+{x}+{y}")
            
            lbl = tk.Label(download_win, text="Descargando la última versión de yt-dlp...", bg=BG_MAIN, fg=TEXT_MAIN, font=("Helvetica", 11, "bold"))
            lbl.pack(pady=20)
            
            progress_lbl = tk.Label(download_win, text="Conectando con GitHub y descargando archivo...", bg=BG_MAIN, fg=TEXT_MUTED, font=("Helvetica", 9))
            progress_lbl.pack()
            
            error_occured = [None]
            
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
                        error_occured[0] = f"HTTP Error {r.status_code}"
                except Exception as e:
                    error_occured[0] = str(e)
                download_win.quit()
                
            download_win.update()
            threading.Thread(target=do_download, daemon=True).start()
            download_win.mainloop()
            download_win.destroy()
            
            if error_occured[0]:
                messagebox.showerror("Error", f"No se pudo descargar el motor:\n{error_occured[0]}")
                sys.exit(1)
        else:
            sys.exit(1)
            
    app = YtDlpGUI()
    app.mainloop()
