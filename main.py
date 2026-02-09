"""
R-Converter - Convertitore di Immagini e Video con supporto Collage
Un'applicazione per adattare immagini e video a diverse risoluzioni e creare collage.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import math
from pathlib import Path
import uuid

try:
    import cv2
    import numpy as np
    VIDEO_SUPPORT = True
except ImportError:
    VIDEO_SUPPORT = False

# Costanti per i formati supportati
IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff']
VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']

# Preset di risoluzioni comuni
RESOLUTION_PRESETS = {
    "Personalizzato": None,
    "1920x1080 (Full HD 16:9)": (1920, 1080),
    "1280x720 (HD 16:9)": (1280, 720),
    "3840x2160 (4K 16:9)": (3840, 2160),
    "1080x1920 (Full HD 9:16 Verticale)": (1080, 1920),
    "1080x1080 (Quadrato 1:1)": (1080, 1080),
    "1200x400 (Banner 3:1)": (1200, 400),
    "1500x500 (Twitter Header 3:1)": (1500, 500),
    "820x312 (Facebook Cover)": (820, 312),
    "1280x720 (YouTube Thumbnail)": (1280, 720),
    "1080x608 (Instagram Landscape)": (1080, 608),
    "800x600 (4:3)": (800, 600),
    "1024x768 (4:3)": (1024, 768),
}

# Costanti per gli handle
HANDLE_SIZE = 8
HANDLE_COLOR = "#4a9eff"
ROTATION_HANDLE_DISTANCE = 25


class ImageLayer:
    """Rappresenta un'immagine nel collage con le sue proprietà"""
    __slots__ = ['id', 'original_image', 'name', 'offset_x', 'offset_y', 'zoom',
                 'rotation', 'flip_h', 'flip_v', 'is_video', 'video_path',
                 'video_fps', 'video_frames', 'bounds_in_canvas', '_cache', '_cache_key']

    def __init__(self, image, name="Immagine"):
        self.id = str(uuid.uuid4())[:8]
        self.original_image = image
        self.name = name

        # Trasformazioni
        self.offset_x = 0
        self.offset_y = 0
        self.zoom = 100  # percentuale
        self.rotation = 0  # gradi
        self.flip_h = False  # specchio orizzontale
        self.flip_v = False  # specchio verticale

        # Proprietà video (opzionali)
        self.is_video = False
        self.video_path = None
        self.video_fps = 30
        self.video_frames = 0

        # Bounds calcolati nel canvas
        self.bounds_in_canvas = None  # (x, y, w, h)

        # Cache per immagine trasformata
        self._cache = None
        self._cache_key = None

    def get_transformed_image(self, use_cache=True):
        """Restituisce l'immagine con trasformazioni applicate (con cache)"""
        cache_key = (self.rotation, self.flip_h, self.flip_v)

        if use_cache and self._cache is not None and self._cache_key == cache_key:
            return self._cache

        img = self.original_image.copy()
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # Applica flip
        if self.flip_h:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if self.flip_v:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        if self.rotation != 0:
            img = img.rotate(-self.rotation, resample=Image.Resampling.BILINEAR, expand=True)

        if use_cache:
            self._cache = img
            self._cache_key = cache_key

        return img

    def invalidate_cache(self):
        """Invalida la cache dell'immagine trasformata"""
        self._cache = None
        self._cache_key = None

    def cleanup(self):
        """Libera risorse associate al layer"""
        self.invalidate_cache()
        self.original_image = None
        self.bounds_in_canvas = None

    def get_display_name(self):
        return f"{self.name} ({self.id})"


class RConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("R-Converter  •  Image & Video Editor")
        self.root.state('zoomed')  # Fullscreen su Windows
        self.root.minsize(1100, 700)

        # Lista delle immagini (layers)
        self.layers = []
        self.selected_layer = None

        # Stato video (per il primo layer se è video)
        self.is_video = False
        self.video_file = None

        # Parametri output
        self.output_width = tk.IntVar(value=3840)
        self.output_height = tk.IntVar(value=1396)
        self.bg_color_var = tk.StringVar(value="#000000")

        # Parametri qualità (inizializzati qui, usati nel pannello export)
        self.img_quality = tk.IntVar(value=100)

        # Stato UI
        self.display_image = None
        self.canvas_bounds = None
        self.preview_scale = 1.0
        self.handles = {}

        # Stato trascinamento
        self.is_dragging = False
        self.active_handle = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_offset_x = 0
        self.drag_start_offset_y = 0
        self.resize_start_zoom = 100
        self.resize_start_pos = (0, 0)
        self.rotation_start_angle = 0
        self.rotation_start_value = 0
        self.rotation_center = (0, 0)

        # Debounce per redraw
        self._redraw_scheduled = False
        self._redraw_job = None

        # Parametri qualità export (default: Media)
        self.export_dpi = tk.IntVar(value=150)
        self.export_bit_depth = tk.IntVar(value=16)
        self.quality_preset = tk.StringVar(value="media")

        # Setup
        self.setup_style()
        self.create_widgets()
        self.setup_bindings()
        self.setup_drag_and_drop()

        # Inizializza canvas con preview vuoto (risoluzione default)
        self.root.after(100, self.init_canvas_preview)

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Palette Blu Moderna - Tech/Cyber style
        self.bg_color = "#0a1929"        # Sfondo blu notte profondo
        self.bg_secondary = "#132f4c"    # Sfondo secondario blu scuro
        self.bg_tertiary = "#1a3a5c"     # Terziario per hover
        self.fg_color = "#e3f2fd"        # Testo bianco-blu
        self.fg_secondary = "#90caf9"    # Testo secondario blu chiaro
        self.accent_color = "#29b6f6"    # Cyan/azzurro brillante
        self.accent_hover = "#4fc3f7"    # Hover più chiaro
        self.accent_glow = "#0288d1"     # Blu più scuro per contrasto
        self.success_color = "#66bb6a"   # Verde per export immagine
        self.video_color = "#7c4dff"     # Viola per export video
        self.border_color = "#1e4976"    # Bordi blu

        self.root.configure(bg=self.bg_color)

        # Stili base
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color,
                       font=('Segoe UI', 10))
        style.configure("Header.TLabel", background=self.bg_color, foreground=self.accent_color,
                       font=('Segoe UI', 11, 'bold'))

        # Pulsanti moderni
        style.configure("TButton", font=('Segoe UI', 10), padding=8,
                       background=self.bg_secondary, foreground=self.fg_color)
        style.map("TButton",
                 background=[('active', self.bg_tertiary), ('pressed', self.accent_color)])

        # Pulsante accent (esportazione)
        style.configure("Accent.TButton", font=('Segoe UI', 11, 'bold'), padding=10,
                       background=self.accent_color, foreground="#0a1929")
        style.map("Accent.TButton",
                 background=[('active', self.accent_hover), ('disabled', self.border_color)])

        # Pulsante verde (export immagine)
        style.configure("Green.TButton", font=('Segoe UI', 10, 'bold'), padding=8,
                       background=self.success_color, foreground="#0a1929")
        style.map("Green.TButton",
                 background=[('active', '#81c784'), ('disabled', self.border_color)])

        # Pulsante viola (export video)
        style.configure("Blue.TButton", font=('Segoe UI', 10, 'bold'), padding=8,
                       background=self.video_color, foreground="#ffffff")
        style.map("Blue.TButton",
                 background=[('active', '#9575cd'), ('disabled', self.border_color)])

        # Scale/Slider
        style.configure("TScale", background=self.bg_color, troughcolor=self.bg_secondary)
        style.configure("Horizontal.TScale", background=self.bg_color)

        # Combobox - colori leggibili
        style.configure("TCombobox",
                       font=('Segoe UI', 10),
                       fieldbackground=self.bg_secondary,
                       background=self.bg_secondary,
                       foreground=self.fg_color,
                       arrowcolor=self.fg_color,
                       selectbackground=self.accent_color,
                       selectforeground="#0a1929")
        style.map("TCombobox",
                 fieldbackground=[('readonly', self.bg_secondary), ('disabled', self.bg_color)],
                 foreground=[('readonly', self.fg_color), ('disabled', self.border_color)],
                 background=[('active', self.bg_tertiary), ('readonly', self.bg_secondary)])

        # Configura anche il dropdown del combobox
        self.root.option_add('*TCombobox*Listbox.background', self.bg_secondary)
        self.root.option_add('*TCombobox*Listbox.foreground', self.fg_color)
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.accent_color)
        self.root.option_add('*TCombobox*Listbox.selectForeground', '#0a1929')
        self.root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 10))

        # Radiobutton
        style.configure("TRadiobutton", background=self.bg_color, foreground=self.fg_color,
                       font=('Segoe UI', 10))
        style.map("TRadiobutton",
                 background=[('active', self.bg_color)])

        # LabelFrame con bordi blu luminosi
        style.configure("TLabelframe", background=self.bg_color, foreground=self.fg_color,
                       bordercolor=self.border_color)
        style.configure("TLabelframe.Label", background=self.bg_color, foreground="#ffffff",
                       font=('Segoe UI', 10, 'bold'))

        # LabelFrame stili per diverse sezioni (colori ben differenziati)
        self.section_colors = {
            'layers': '#1a365d',      # Layers - blu navy intenso
            'transform': '#0f2840',   # Trasformazioni - blu scuro base
            'size': '#1e4a3d',        # Dimensioni - verde-blu (teal scuro)
            'fit': '#2d1f47',         # Adattamento - viola scuro
            'mirror': '#3d2a1f',      # Specchio - marrone/arancio scuro
        }

        # Colori bordo per ogni sezione (più luminosi)
        self.section_borders = {
            'layers': '#3182ce',      # Blu brillante
            'transform': '#1e88e5',   # Blu
            'size': '#26a69a',        # Teal
            'fit': '#7c4dff',         # Viola
            'mirror': '#ff7043',      # Arancio
        }

        for name, color in self.section_colors.items():
            border = self.section_borders.get(name, self.border_color)
            style.configure(f"{name.capitalize()}.TLabelframe", background=color,
                           foreground=self.fg_color, bordercolor=border, borderwidth=2)
            # Titoli uniformi: bianco, bold, font 10
            style.configure(f"{name.capitalize()}.TLabelframe.Label",
                           background=color,
                           foreground="#ffffff",
                           font=('Segoe UI', 10, 'bold'))

        # Toggle Switch moderno per Blocca Proporzioni - bianco e bold
        style.configure("Toggle.TCheckbutton",
                       background=self.bg_color,
                       foreground="#ffffff",
                       font=('Segoe UI', 10, 'bold'),
                       padding=4)
        style.map("Toggle.TCheckbutton",
                 background=[('active', self.bg_tertiary), ('selected', self.accent_glow)],
                 foreground=[('active', '#ffffff'), ('selected', '#ffffff')])

        # Entry
        style.configure("TEntry", fieldbackground=self.bg_secondary, foreground=self.fg_color,
                       insertcolor=self.fg_color)

        # Progressbar
        style.configure("TProgressbar", background=self.accent_color, troughcolor=self.bg_secondary)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.create_left_panel(main_frame)
        self.create_canvas_panel(main_frame)
        self.create_right_panel(main_frame)

    def create_left_panel(self, parent):
        """Pannello sinistro - Layers e controlli immagine selezionata (scrollabile)"""
        # Container esterno
        left_container = ttk.Frame(parent, width=280)
        left_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_container.pack_propagate(False)

        # Canvas per scrolling
        self.left_canvas = tk.Canvas(left_container, bg=self.bg_color, highlightthickness=0, width=280)
        self.left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=self.left_canvas.yview)
        self.left_scrollable_frame = ttk.Frame(self.left_canvas)

        self.left_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        )

        self.left_canvas.create_window((0, 0), window=self.left_scrollable_frame, anchor="nw", width=265)
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)

        self.left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind scroll mouse sul pannello sinistro e tutti i suoi figli
        self.left_canvas.bind("<MouseWheel>", self.on_left_panel_scroll)
        self.left_scrollable_frame.bind("<MouseWheel>", self.on_left_panel_scroll)
        # Bind anche su Enter/Leave per propagare scroll a tutti i widget figli
        self.left_canvas.bind("<Enter>", lambda e: self._bind_scroll_to_children(self.left_scrollable_frame))

        left_frame = self.left_scrollable_frame

        # === LAYERS ===
        layers_frame = ttk.LabelFrame(left_frame, text="⭐ Layers", padding=10, style="Layers.TLabelframe")
        layers_frame.pack(fill=tk.X, pady=(0, 12))

        # Lista layers con stile moderno
        self.layers_listbox = tk.Listbox(layers_frame, height=8, bg=self.section_colors['layers'],
                                         fg=self.fg_color, selectbackground=self.accent_color,
                                         selectforeground="#0a1929", font=('Segoe UI', 9),
                                         bd=0, highlightthickness=1, highlightcolor=self.accent_color,
                                         highlightbackground=self.border_color)
        self.layers_listbox.pack(fill=tk.X, pady=(0, 5))
        self.layers_listbox.bind('<<ListboxSelect>>', self.on_layer_select)

        # Pulsanti layer
        btn_frame = ttk.Frame(layers_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="➕ Aggiungi", command=self.add_image).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(btn_frame, text="➖ Rimuovi", command=self.remove_selected_layer).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))

        btn_frame2 = ttk.Frame(layers_frame)
        btn_frame2.pack(fill=tk.X, pady=(3,0))

        ttk.Button(btn_frame2, text="▲", width=4, command=self.move_layer_up).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(btn_frame2, text="▼", width=4, command=self.move_layer_down).pack(side=tk.LEFT, padx=(2,2))
        ttk.Button(btn_frame2, text="⧉ Duplica", command=self.duplicate_layer).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))

        # === CONTROLLI LAYER SELEZIONATO ===
        self.layer_controls_frame = ttk.LabelFrame(left_frame, text="⚙️ Trasformazioni", padding=8, style="Transform.TLabelframe")
        self.layer_controls_frame.pack(fill=tk.X, pady=(0, 8))

        # Zoom
        zoom_header = ttk.Frame(self.layer_controls_frame)
        zoom_header.pack(fill=tk.X)
        ttk.Label(zoom_header, text="🔍 Scala:").pack(side=tk.LEFT)
        self.zoom_entry = ttk.Entry(zoom_header, width=6)
        self.zoom_entry.pack(side=tk.RIGHT)
        self.zoom_entry.insert(0, "100")
        self.zoom_entry.bind('<Return>', self.on_zoom_entry)
        ttk.Label(zoom_header, text="%").pack(side=tk.RIGHT)

        self.zoom_var = tk.IntVar(value=100)
        self.zoom_scale = ttk.Scale(self.layer_controls_frame, from_=1, to=1000, variable=self.zoom_var,
                                    orient=tk.HORIZONTAL, command=self.on_zoom_change)
        self.zoom_scale.pack(fill=tk.X, pady=(0,2))

        zoom_btns = ttk.Frame(self.layer_controls_frame)
        zoom_btns.pack(fill=tk.X, pady=(0,5))
        ttk.Button(zoom_btns, text="-", width=3, command=lambda: self.adjust_layer_zoom(-10)).pack(side=tk.LEFT)
        ttk.Button(zoom_btns, text="100%", command=self.reset_layer_zoom).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(zoom_btns, text="+", width=3, command=lambda: self.adjust_layer_zoom(10)).pack(side=tk.RIGHT)

        # Rotazione
        rot_header = ttk.Frame(self.layer_controls_frame)
        rot_header.pack(fill=tk.X)
        ttk.Label(rot_header, text="🔄 Rotazione:").pack(side=tk.LEFT)
        self.rotation_entry = ttk.Entry(rot_header, width=6)
        self.rotation_entry.pack(side=tk.RIGHT)
        self.rotation_entry.insert(0, "0")
        self.rotation_entry.bind('<Return>', self.on_rotation_entry)
        ttk.Label(rot_header, text="°").pack(side=tk.RIGHT)

        self.rotation_var = tk.IntVar(value=0)
        self.rotation_scale = ttk.Scale(self.layer_controls_frame, from_=-180, to=180, variable=self.rotation_var,
                                        orient=tk.HORIZONTAL, command=self.on_rotation_change)
        self.rotation_scale.pack(fill=tk.X, pady=(0,2))

        rot_btns = ttk.Frame(self.layer_controls_frame)
        rot_btns.pack(fill=tk.X, pady=(0,5))
        ttk.Button(rot_btns, text="-90°", width=5, command=lambda: self.set_layer_rotation(-90)).pack(side=tk.LEFT)
        ttk.Button(rot_btns, text="0°", command=lambda: self.set_layer_rotation(0)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(rot_btns, text="+90°", width=5, command=lambda: self.set_layer_rotation(90)).pack(side=tk.RIGHT)

        # Posizione X (Pan)
        pos_x_header = ttk.Frame(self.layer_controls_frame)
        pos_x_header.pack(fill=tk.X, pady=(5,0))
        ttk.Label(pos_x_header, text="↔️ Pan (X):").pack(side=tk.LEFT)
        self.offset_x_entry = ttk.Entry(pos_x_header, width=7)
        self.offset_x_entry.pack(side=tk.RIGHT)
        self.offset_x_entry.insert(0, "0")
        self.offset_x_entry.bind('<Return>', self.on_position_entry)

        self.offset_x_var = tk.IntVar(value=0)
        self.offset_x_scale = ttk.Scale(self.layer_controls_frame, from_=-1000, to=1000, variable=self.offset_x_var,
                                        orient=tk.HORIZONTAL, command=self.on_position_change)
        self.offset_x_scale.pack(fill=tk.X)

        # Posizione Y (Tilt)
        pos_y_header = ttk.Frame(self.layer_controls_frame)
        pos_y_header.pack(fill=tk.X)
        ttk.Label(pos_y_header, text="↕️ Tilt (Y):").pack(side=tk.LEFT)
        self.offset_y_entry = ttk.Entry(pos_y_header, width=7)
        self.offset_y_entry.pack(side=tk.RIGHT)
        self.offset_y_entry.insert(0, "0")
        self.offset_y_entry.bind('<Return>', self.on_position_entry)

        self.offset_y_var = tk.IntVar(value=0)
        self.offset_y_scale = ttk.Scale(self.layer_controls_frame, from_=-1000, to=1000, variable=self.offset_y_var,
                                        orient=tk.HORIZONTAL, command=self.on_position_change)
        self.offset_y_scale.pack(fill=tk.X)

        # === DIMENSIONI IMMAGINE IN PIXEL ===
        size_frame = ttk.LabelFrame(self.layer_controls_frame, text="📐 Dimensioni (px)", padding=5, style="Size.TLabelframe")
        size_frame.pack(fill=tk.X, pady=(10,0))

        size_row = ttk.Frame(size_frame)
        size_row.pack(fill=tk.X)

        ttk.Label(size_row, text="L:", font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.img_width_entry = ttk.Entry(size_row, width=6)
        self.img_width_entry.pack(side=tk.LEFT, padx=(2, 10))
        self.img_width_entry.insert(0, "0")
        self.img_width_entry.bind('<Return>', self.on_size_entry)

        ttk.Label(size_row, text="A:", font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.img_height_entry = ttk.Entry(size_row, width=6)
        self.img_height_entry.pack(side=tk.LEFT, padx=2)
        self.img_height_entry.insert(0, "0")
        self.img_height_entry.bind('<Return>', self.on_size_entry)

        self.img_size_label = ttk.Label(size_frame, text="Originale: -", font=('Segoe UI', 8))
        self.img_size_label.pack(anchor=tk.W, pady=(1,0))

        # Toggle blocca proporzioni - stile moderno
        lock_frame = ttk.Frame(self.layer_controls_frame)
        lock_frame.pack(fill=tk.X, pady=(5, 3))
        self.lock_aspect_ratio = tk.BooleanVar(value=True)
        self.lock_aspect_btn = ttk.Checkbutton(lock_frame, text="🔒 Proporzioni bloccate",
                                                variable=self.lock_aspect_ratio, style="Toggle.TCheckbutton",
                                                command=self.on_lock_toggle)
        self.lock_aspect_btn.pack(fill=tk.X)

        # === ADATTAMENTO LAYER ===
        fit_frame = ttk.LabelFrame(self.layer_controls_frame, text="⬛ Adattamento", padding=5, style="Fit.TLabelframe")
        fit_frame.pack(fill=tk.X, pady=(10,0))

        # Usa grid per allineare i 4 pulsanti uniformemente
        fit_row1 = ttk.Frame(fit_frame)
        fit_row1.pack(fill=tk.X, pady=(0,3))
        fit_row1.columnconfigure(0, weight=1, uniform="fitbtn")
        fit_row1.columnconfigure(1, weight=1, uniform="fitbtn")
        ttk.Button(fit_row1, text="📐 Adatta", command=self.fit_keep_aspect).grid(row=0, column=0, sticky="ew", padx=(0,2))
        ttk.Button(fit_row1, text="⬛ Riempi", command=self.fit_contain).grid(row=0, column=1, sticky="ew", padx=(2,0))

        fit_row2 = ttk.Frame(fit_frame)
        fit_row2.pack(fill=tk.X)
        fit_row2.columnconfigure(0, weight=1, uniform="fitbtn")
        fit_row2.columnconfigure(1, weight=1, uniform="fitbtn")
        ttk.Button(fit_row2, text="↔ Riempi H", command=self.fit_fill_horizontal).grid(row=0, column=0, sticky="ew", padx=(0,2))
        ttk.Button(fit_row2, text="↕ Riempi V", command=self.fit_fill_vertical).grid(row=0, column=1, sticky="ew", padx=(2,0))

        # Pulsanti azione
        action_btns = ttk.Frame(self.layer_controls_frame)
        action_btns.pack(fill=tk.X, pady=(10,0))
        ttk.Button(action_btns, text="◎ Centra", command=self.center_selected_layer).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))

        # Effetto Specchio
        mirror_frame = ttk.LabelFrame(self.layer_controls_frame, text="⟷ Specchio", padding=5, style="Mirror.TLabelframe")
        mirror_frame.pack(fill=tk.X, pady=(10,0))

        mirror_btns = ttk.Frame(mirror_frame)
        mirror_btns.pack(fill=tk.X)
        ttk.Button(mirror_btns, text="⇆ Orizzontale", command=self.flip_horizontal).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(mirror_btns, text="⇅ Verticale", command=self.flip_vertical).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))

    def create_canvas_panel(self, parent):
        """Pannello centrale - Canvas"""
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # Info con stile moderno
        self.file_label = ttk.Label(canvas_frame, text="⬚ Trascina qui le tue immagini",
                                    font=('Segoe UI', 13), style="Header.TLabel")
        self.file_label.pack(pady=(0, 5))

        self.instruction_label = ttk.Label(canvas_frame,
            text="Click = Seleziona  •  Canc = Elimina  •  Trascina = Sposta  •  Handle = Ridimensiona",
            font=('Segoe UI', 9), foreground=self.border_color)
        self.instruction_label.pack(pady=(0, 5))

        # Canvas con bordo moderno
        canvas_container = tk.Frame(canvas_frame, bg=self.border_color, bd=0)
        canvas_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_container, bg="#061422", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.draw_empty_canvas()

        # Pulsanti con stile
        btn_frame = ttk.Frame(canvas_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="⊕ Aggiungi File", command=self.add_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="⊗ Rimuovi Tutto", command=self.clear_all).pack(side=tk.LEFT, padx=5)

        self.info_label = ttk.Label(canvas_frame, text="", font=('Segoe UI', 9))
        self.info_label.pack()

    def create_right_panel(self, parent):
        """Pannello destro - Output e Export"""
        right_frame = ttk.Frame(parent, width=270)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_frame.pack_propagate(False)

        # === OUTPUT ===
        output_frame = ttk.LabelFrame(right_frame, text="⬡ Dimensioni Output", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(output_frame, text="Preset:").pack(anchor=tk.W)
        self.preset_combo = ttk.Combobox(output_frame, values=list(RESOLUTION_PRESETS.keys()), state="readonly")
        self.preset_combo.set("1920x1080 (Full HD 16:9)")
        self.preset_combo.pack(fill=tk.X, pady=(2, 10))
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_change)

        size_frame = ttk.Frame(output_frame)
        size_frame.pack(fill=tk.X)

        ttk.Label(size_frame, text="W:").grid(row=0, column=0)
        self.width_entry = ttk.Entry(size_frame, textvariable=self.output_width, width=7)
        self.width_entry.grid(row=0, column=1, padx=2)

        ttk.Label(size_frame, text="H:").grid(row=0, column=2, padx=(10,0))
        self.height_entry = ttk.Entry(size_frame, textvariable=self.output_height, width=7)
        self.height_entry.grid(row=0, column=3, padx=2)

        ttk.Button(output_frame, text="✓ Applica", command=self.apply_resolution).pack(pady=(10, 0))

        # === SFONDO ===
        bg_frame = ttk.LabelFrame(right_frame, text="◐ Sfondo", padding=10)
        bg_frame.pack(fill=tk.X, pady=(0, 10))

        color_grid = ttk.Frame(bg_frame)
        color_grid.pack()

        colors = [("#000000", "Nero"), ("#FFFFFF", "Bianco"), ("#808080", "Grigio"),
                  ("#FF0000", "Rosso"), ("#00FF00", "Verde"), ("#0000FF", "Blu"),
                  ("#FFFF00", "Giallo"), ("#FF00FF", "Magenta"), ("#00FFFF", "Ciano")]

        for i, (color, name) in enumerate(colors):
            btn = tk.Button(color_grid, bg=color, width=3, height=1, bd=0,
                           activebackground=color, relief=tk.FLAT,
                           command=lambda c=color: self.set_bg_color(c))
            btn.grid(row=i//3, column=i%3, padx=2, pady=2)

        ttk.Button(bg_frame, text="⊞ Personalizza", command=self.choose_custom_color).pack(pady=(10, 0))

        # === ESPORTAZIONE IMMAGINE ===
        self.image_export_frame = ttk.LabelFrame(right_frame, text="◳ Esporta Immagine", padding=12)
        self.image_export_frame.pack(fill=tk.X, pady=(0, 8))

        # Formati in una riga ordinata
        ttk.Label(self.image_export_frame, text="Formato:", font=('Segoe UI', 9)).pack(anchor=tk.W)
        self.output_format = tk.StringVar(value="png")
        img_fmt_frame = ttk.Frame(self.image_export_frame)
        img_fmt_frame.pack(fill=tk.X, pady=(2, 8))
        for i, fmt in enumerate(["PNG", "JPG", "WebP", "BMP"]):
            ttk.Radiobutton(img_fmt_frame, text=fmt, variable=self.output_format,
                           value=fmt.lower()).grid(row=0, column=i, sticky=tk.W, padx=2)

        # Preset Qualità (Bassa, Media, Alta)
        qual_preset_frame = ttk.Frame(self.image_export_frame)
        qual_preset_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(qual_preset_frame, text="Qualità:", font=('Segoe UI', 9)).pack(side=tk.LEFT)

        self.quality_preset = tk.StringVar(value="media")
        ttk.Radiobutton(qual_preset_frame, text="Bassa", variable=self.quality_preset,
                       value="bassa", command=self.on_quality_preset_change).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(qual_preset_frame, text="Media", variable=self.quality_preset,
                       value="media", command=self.on_quality_preset_change).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(qual_preset_frame, text="Alta", variable=self.quality_preset,
                       value="alta", command=self.on_quality_preset_change).pack(side=tk.LEFT, padx=3)

        # Info qualità (DPI, bit depth)
        self.quality_info_label = ttk.Label(self.image_export_frame,
                                            text="DPI: 150 | Bit: 16 | Compressione: 15%",
                                            font=('Segoe UI', 8))
        self.quality_info_label.pack(anchor=tk.W, pady=(0, 8))

        self.img_export_btn = ttk.Button(self.image_export_frame, text="▶ ESPORTA IMMAGINE",
                                         style="Green.TButton", command=self.export_image)
        self.img_export_btn.pack(fill=tk.X, ipady=4)

        # === ESPORTAZIONE VIDEO ===
        self.video_export_frame = ttk.LabelFrame(right_frame, text="▷ Esporta Video", padding=12)
        self.video_export_frame.pack(fill=tk.X, pady=(0, 8))

        # Formati video
        ttk.Label(self.video_export_frame, text="Formato:", font=('Segoe UI', 9)).pack(anchor=tk.W)
        self.video_format = tk.StringVar(value="mp4")
        vid_fmt_frame = ttk.Frame(self.video_export_frame)
        vid_fmt_frame.pack(fill=tk.X, pady=(2, 8))
        for i, fmt in enumerate(["MP4", "AVI", "WebM", "GIF"]):
            ttk.Radiobutton(vid_fmt_frame, text=fmt, variable=self.video_format,
                           value=fmt.lower()).grid(row=0, column=i, sticky=tk.W, padx=2)

        # FPS
        fps_frame = ttk.Frame(self.video_export_frame)
        fps_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(fps_frame, text="FPS:", font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.fps_var = tk.IntVar(value=30)
        fps_entry = ttk.Entry(fps_frame, textvariable=self.fps_var, width=4)
        fps_entry.pack(side=tk.LEFT, padx=(2, 15))

        # Preset Qualità Video (Bassa, Media, Alta)
        vid_qual_preset_frame = ttk.Frame(self.video_export_frame)
        vid_qual_preset_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(vid_qual_preset_frame, text="Qualità:", font=('Segoe UI', 9)).pack(side=tk.LEFT)

        self.vid_quality_preset = tk.StringVar(value="media")
        ttk.Radiobutton(vid_qual_preset_frame, text="Bassa", variable=self.vid_quality_preset,
                       value="bassa", command=self.on_vid_quality_preset_change).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(vid_qual_preset_frame, text="Media", variable=self.vid_quality_preset,
                       value="media", command=self.on_vid_quality_preset_change).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(vid_qual_preset_frame, text="Alta", variable=self.vid_quality_preset,
                       value="alta", command=self.on_vid_quality_preset_change).pack(side=tk.LEFT, padx=3)

        # Info qualità video
        self.vid_quality = tk.IntVar(value=75)
        self.vid_bitrate = tk.IntVar(value=5000)  # kbps
        self.vid_quality_info_label = ttk.Label(self.video_export_frame,
                                                text="Bitrate: 5000 kbps | CRF: 23",
                                                font=('Segoe UI', 8))
        self.vid_quality_info_label.pack(anchor=tk.W, pady=(0, 8))

        self.vid_export_btn = ttk.Button(self.video_export_frame, text="▶ ESPORTA VIDEO",
                                         style="Blue.TButton", command=self.export_video)
        self.vid_export_btn.pack(fill=tk.X, ipady=4)

        # Progress bar moderna
        self.progress = ttk.Progressbar(right_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(5, 10))

        # Stato iniziale: video disabilitato
        self.set_video_export_enabled(False)

    def draw_empty_canvas(self):
        """Disegna canvas vuoto con stile moderno"""
        self.canvas.delete("all")
        self.canvas.update_idletasks()

        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 400

        # Sfondo blu notte
        self.canvas.create_rectangle(0, 0, w, h, fill="#061422", outline="")

        # Area tratteggiata centrale con glow effect
        margin = 60
        self.canvas.create_rectangle(margin, margin, w-margin, h-margin,
                                     outline=self.accent_color, width=2, dash=(8, 4))

        # Icona e testo
        self.canvas.create_text(w//2, h//2 - 30, text="▢",
                               fill=self.accent_color, font=('Segoe UI', 52))
        self.canvas.create_text(w//2, h//2 + 30, text="Trascina qui immagini o video",
                               fill=self.fg_color, font=('Segoe UI', 13))
        self.canvas.create_text(w//2, h//2 + 55, text="oppure clicca 'Aggiungi File'",
                               fill=self.fg_secondary, font=('Segoe UI', 10))

    def setup_bindings(self):
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        self.root.bind("<Control-o>", lambda e: self.add_image())
        self.root.bind("<Control-s>", lambda e: self.export_file())
        self.root.bind("<Delete>", self.on_delete_key)
        self.root.bind("<Escape>", self.on_escape_key)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Motion>", self.on_mouse_hover)

    def setup_drag_and_drop(self):
        """Configura il drag and drop per file esterni"""
        try:
            # Prova a usare tkinterdnd2 se disponibile
            from tkinterdnd2 import DND_FILES  # type: ignore[import-not-found]
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind('<<Drop>>', self.on_drop_files)
            self.drag_drop_enabled = True
        except ImportError:
            try:
                # Fallback Windows: usa windnd sulla finestra root
                import windnd  # type: ignore[import-not-found]
                # Hook sulla finestra principale (più affidabile del canvas)
                windnd.hook_dropfiles(self.root, func=self.on_drop_windnd)
                self.drag_drop_enabled = True
            except Exception as e:
                # Ultimo fallback: nessun drag and drop
                self.drag_drop_enabled = False
                print(f"Drag&Drop non disponibile: {e}")

    def on_drop_windnd(self, files):
        """Gestisce il drop di file tramite windnd (Windows)"""
        for filepath in files:
            # windnd passa bytes su alcune versioni
            if isinstance(filepath, bytes):
                filepath = filepath.decode('utf-8')
            filepath = filepath.strip('{}')
            ext = Path(filepath).suffix.lower()
            if ext in VIDEO_FORMATS:
                self.load_video(filepath)
            elif ext in IMAGE_FORMATS:
                self.load_image(filepath)

    def on_drop_files(self, event):
        """Gestisce il drop di file nel canvas"""
        files = self.root.tk.splitlist(event.data)
        for filepath in files:
            filepath = filepath.strip('{}')
            ext = Path(filepath).suffix.lower()
            if ext in VIDEO_FORMATS:
                self.load_video(filepath)
            elif ext in IMAGE_FORMATS:
                self.load_image(filepath)

    def init_canvas_preview(self):
        """Inizializza il canvas con la preview della risoluzione di default"""
        self.canvas.update_idletasks()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w < 10 or canvas_h < 10:
            return

        output_w = self.output_width.get()
        output_h = self.output_height.get()

        # Scala preview
        self.preview_scale = min(canvas_w / output_w, canvas_h / output_h) * 0.9
        preview_w = int(output_w * self.preview_scale)
        preview_h = int(output_h * self.preview_scale)

        # Pulisci e disegna area di output
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, canvas_w, canvas_h, fill="#0a1929", outline="")

        # Posizione canvas output
        canvas_x = (canvas_w - preview_w) // 2
        canvas_y = (canvas_h - preview_h) // 2
        self.canvas_bounds = (canvas_x, canvas_y, preview_w, preview_h)

        # Sfondo output (colore selezionato)
        bg_color = self.bg_color_var.get()
        self.canvas.create_rectangle(canvas_x, canvas_y, canvas_x+preview_w, canvas_y+preview_h,
                                     fill=bg_color, outline=self.border_color, width=2)

        # Testo informativo
        self.canvas.create_text(canvas_x + preview_w//2, canvas_y + preview_h//2 - 15,
                               text=f"{output_w} x {output_h}",
                               fill=self.fg_secondary, font=('Segoe UI', 14, 'bold'))
        self.canvas.create_text(canvas_x + preview_w//2, canvas_y + preview_h//2 + 15,
                               text="Aggiungi immagini per iniziare",
                               fill=self.border_color, font=('Segoe UI', 10))

        self.info_label.config(text=f"Output: {output_w}x{output_h}")

    def on_quality_preset_change(self):
        """Gestisce il cambio del preset qualità"""
        preset = self.quality_preset.get()

        if preset == "bassa":
            self.export_dpi.set(72)
            self.export_bit_depth.set(8)
            self.img_quality.set(60)
            self.quality_info_label.config(text="DPI: 72 | Bit: 8 | Compressione: 40%")
        elif preset == "media":
            self.export_dpi.set(150)
            self.export_bit_depth.set(16)
            self.img_quality.set(85)
            self.quality_info_label.config(text="DPI: 150 | Bit: 16 | Compressione: 15%")
        else:  # alta
            self.export_dpi.set(300)
            self.export_bit_depth.set(24)
            self.img_quality.set(100)
            self.quality_info_label.config(text="DPI: 300 | Bit: 24 | Compressione: 0%")

    def on_lock_toggle(self):
        """Aggiorna l'icona del toggle quando cambia stato"""
        if self.lock_aspect_ratio.get():
            self.lock_aspect_btn.config(text="🔒 Proporzioni bloccate")
        else:
            self.lock_aspect_btn.config(text="🔓 Proporzioni libere")

    def on_size_entry(self, event=None):
        """Gestisce il cambio delle dimensioni dell'immagine in pixel"""
        if not self.selected_layer:
            return

        try:
            new_width = int(self.img_width_entry.get())
            new_height = int(self.img_height_entry.get())

            if new_width < 1 or new_height < 1:
                return

            # Calcola il nuovo zoom basato sulla dimensione originale
            orig_w, orig_h = self.selected_layer.original_image.size

            # Determina quale entry è stata modificata
            focused = event.widget if event else None

            if self.lock_aspect_ratio.get():
                # Proporzioni bloccate: calcola l'altra dimensione
                aspect = orig_w / orig_h
                if focused == self.img_width_entry:
                    # Larghezza modificata, calcola altezza
                    new_height = int(new_width / aspect)
                    zoom = (new_width / orig_w) * 100
                else:
                    # Altezza modificata, calcola larghezza
                    new_width = int(new_height * aspect)
                    zoom = (new_height / orig_h) * 100
                new_zoom = int(zoom)
            else:
                # Proporzioni libere: usa la dimensione maggiore
                zoom_w = (new_width / orig_w) * 100
                zoom_h = (new_height / orig_h) * 100
                new_zoom = int(max(zoom_w, zoom_h))

            new_zoom = max(1, min(1000, new_zoom))
            self.selected_layer.zoom = new_zoom
            self.zoom_var.set(new_zoom)
            self.zoom_entry.delete(0, tk.END)
            self.zoom_entry.insert(0, str(new_zoom))

            self.redraw_canvas()
            self.update_size_display()

        except ValueError:
            pass

    def update_size_display(self):
        """Aggiorna la visualizzazione delle dimensioni dell'immagine"""
        if not self.selected_layer:
            self.img_width_entry.delete(0, tk.END)
            self.img_width_entry.insert(0, "0")
            self.img_height_entry.delete(0, tk.END)
            self.img_height_entry.insert(0, "0")
            self.img_size_label.config(text="Originale: -")
            return

        # Dimensioni originali
        orig_w, orig_h = self.selected_layer.original_image.size
        self.img_size_label.config(text=f"Originale: {orig_w} x {orig_h}")

        # Dimensioni attuali (con zoom)
        zoom = self.selected_layer.zoom / 100.0
        current_w = int(orig_w * zoom)
        current_h = int(orig_h * zoom)

        self.img_width_entry.delete(0, tk.END)
        self.img_width_entry.insert(0, str(current_w))
        self.img_height_entry.delete(0, tk.END)
        self.img_height_entry.insert(0, str(current_h))

    # ==================== LAYER MANAGEMENT ====================

    def add_image(self):
        """Aggiunge una nuova immagine o video al collage"""
        filetypes = [
            ("Immagini e Video", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tiff *.mp4 *.avi *.mov *.mkv *.wmv *.webm"),
            ("Immagini", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tiff"),
            ("Video", "*.mp4 *.avi *.mov *.mkv *.wmv *.webm"),
            ("Tutti i file", "*.*")
        ]

        filepaths = filedialog.askopenfilenames(title="Seleziona immagini o video", filetypes=filetypes)

        for filepath in filepaths:
            ext = Path(filepath).suffix.lower()
            if ext in VIDEO_FORMATS:
                self.load_video(filepath)
            else:
                self.load_image(filepath)

    def load_image(self, filepath):
        """Carica un'immagine come nuovo layer"""
        try:
            img = Image.open(filepath)
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')

            name = Path(filepath).stem[:20]
            layer = ImageLayer(img, name)

            # Calcola zoom per far stare l'immagine nel canvas
            output_w = self.output_width.get()
            output_h = self.output_height.get()
            img_w, img_h = img.size

            # Calcola la scala per contenere l'immagine nell'output
            scale_x = output_w / img_w
            scale_y = output_h / img_h
            fit_scale = min(scale_x, scale_y)

            # Converti in percentuale zoom (massimo 100% per non ingrandire)
            fit_zoom = int(fit_scale * 100)
            fit_zoom = min(fit_zoom, 100)  # Non ingrandire oltre 100%
            fit_zoom = max(fit_zoom, 10)   # Minimo 10%

            layer.zoom = fit_zoom

            self.layers.append(layer)
            self.update_layers_list()

            # Seleziona il nuovo layer
            self.selected_layer = layer
            self.layers_listbox.selection_clear(0, tk.END)
            self.layers_listbox.selection_set(len(self.layers) - 1)
            self.update_layer_controls()

            self.file_label.config(text=f"📚 {len(self.layers)} elementi nel collage")
            self.update_export_panels()
            self.redraw_canvas()

        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare:\n{filepath}\n{str(e)}")

    def load_video(self, filepath):
        """Carica un video - salva il percorso e usa il primo frame come anteprima"""
        if not VIDEO_SUPPORT:
            messagebox.showerror("Errore", "OpenCV non installato. Installa con: pip install opencv-python")
            return

        try:
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                raise Exception("Impossibile aprire il video")

            ret, frame = cap.read()
            if not ret:
                raise Exception("Impossibile leggere il primo frame")

            # Converti BGR -> RGB -> PIL Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # Ottieni info video
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            cap.release()

            name = f"🎬{Path(filepath).stem[:15]}"
            layer = ImageLayer(img, name)
            layer.video_path = filepath  # Salva il percorso video
            layer.video_fps = fps
            layer.video_frames = frame_count
            layer.is_video = True

            # Calcola zoom per far stare nel canvas
            output_w = self.output_width.get()
            output_h = self.output_height.get()
            img_w, img_h = img.size

            scale_x = output_w / img_w
            scale_y = output_h / img_h
            fit_scale = min(scale_x, scale_y)
            fit_zoom = int(fit_scale * 100)
            fit_zoom = min(fit_zoom, 100)
            fit_zoom = max(fit_zoom, 10)
            layer.zoom = fit_zoom

            self.layers.append(layer)
            self.update_layers_list()

            self.selected_layer = layer
            self.layers_listbox.selection_clear(0, tk.END)
            self.layers_listbox.selection_set(len(self.layers) - 1)
            self.update_layer_controls()

            self.file_label.config(text=f"📚 {len(self.layers)} elementi | Video: {duration:.1f}s @ {fps:.0f}fps")
            self.update_export_panels()
            self.redraw_canvas()

        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare video:\n{filepath}\n{str(e)}")

    def update_layers_list(self):
        """Aggiorna la lista dei layer"""
        self.layers_listbox.delete(0, tk.END)
        for i, layer in enumerate(self.layers):
            prefix = "▶ " if layer == self.selected_layer else "  "
            self.layers_listbox.insert(tk.END, f"{prefix}{i+1}. {layer.name}")

    def on_layer_select(self, event=None):
        """Gestisce la selezione di un layer dalla lista"""
        selection = self.layers_listbox.curselection()
        if selection:
            idx = selection[0]
            if 0 <= idx < len(self.layers):
                self.selected_layer = self.layers[idx]
                self.update_layer_controls()
                self.update_layers_list()
                self.redraw_canvas()

    def update_layer_controls(self):
        """Aggiorna i controlli con i valori del layer selezionato"""
        if self.selected_layer:
            self.zoom_var.set(self.selected_layer.zoom)
            self.zoom_entry.delete(0, tk.END)
            self.zoom_entry.insert(0, str(self.selected_layer.zoom))
            self.rotation_var.set(self.selected_layer.rotation)
            self.rotation_entry.delete(0, tk.END)
            self.rotation_entry.insert(0, str(self.selected_layer.rotation))
            self.offset_x_var.set(self.selected_layer.offset_x)
            self.offset_x_entry.delete(0, tk.END)
            self.offset_x_entry.insert(0, str(self.selected_layer.offset_x))
            self.offset_y_var.set(self.selected_layer.offset_y)
            self.offset_y_entry.delete(0, tk.END)
            self.offset_y_entry.insert(0, str(self.selected_layer.offset_y))
            # Aggiorna dimensioni in pixel
            self.update_size_display()
        else:
            self.update_size_display()

    def remove_selected_layer(self):
        """Rimuove il layer selezionato e libera risorse"""
        if self.selected_layer and self.selected_layer in self.layers:
            layer_to_remove = self.selected_layer
            self.layers.remove(layer_to_remove)
            layer_to_remove.cleanup()  # Libera memoria
            self.selected_layer = self.layers[-1] if self.layers else None
            self.update_layers_list()
            self.update_layer_controls()
            self.update_export_panels()
            self.file_label.config(text=f"📚 {len(self.layers)} elementi nel collage" if self.layers else "📁 Aggiungi immagini")
            self.redraw_canvas()

    def move_layer_up(self):
        """Sposta il layer selezionato in alto (sopra gli altri)"""
        if self.selected_layer and self.selected_layer in self.layers:
            idx = self.layers.index(self.selected_layer)
            if idx < len(self.layers) - 1:
                self.layers[idx], self.layers[idx+1] = self.layers[idx+1], self.layers[idx]
                self.update_layers_list()
                self.layers_listbox.selection_set(idx + 1)
                self.redraw_canvas()

    def move_layer_down(self):
        """Sposta il layer selezionato in basso (sotto gli altri)"""
        if self.selected_layer and self.selected_layer in self.layers:
            idx = self.layers.index(self.selected_layer)
            if idx > 0:
                self.layers[idx], self.layers[idx-1] = self.layers[idx-1], self.layers[idx]
                self.update_layers_list()
                self.layers_listbox.selection_set(idx - 1)
                self.redraw_canvas()

    def duplicate_layer(self):
        """Duplica il layer selezionato"""
        if self.selected_layer:
            new_layer = ImageLayer(self.selected_layer.original_image.copy(),
                                   f"{self.selected_layer.name}_copia")
            new_layer.zoom = self.selected_layer.zoom
            new_layer.rotation = self.selected_layer.rotation
            new_layer.offset_x = self.selected_layer.offset_x + 50
            new_layer.offset_y = self.selected_layer.offset_y + 50
            new_layer.flip_h = self.selected_layer.flip_h
            new_layer.flip_v = self.selected_layer.flip_v

            self.layers.append(new_layer)
            self.selected_layer = new_layer
            self.update_layers_list()
            self.update_layer_controls()
            self.redraw_canvas()

    def center_selected_layer(self):
        """Centra il layer selezionato"""
        if self.selected_layer:
            self.selected_layer.offset_x = 0
            self.selected_layer.offset_y = 0
            self.offset_x_var.set(0)
            self.offset_y_var.set(0)
            self.offset_x_entry.delete(0, tk.END)
            self.offset_x_entry.insert(0, "0")
            self.offset_y_entry.delete(0, tk.END)
            self.offset_y_entry.insert(0, "0")
            self.redraw_canvas()

    def fit_keep_aspect(self):
        """Adatta il layer mantenendo le proporzioni (fit inside canvas)"""
        if not self.selected_layer:
            return
        orig_w, orig_h = self.selected_layer.original_image.size
        if orig_w == 0 or orig_h == 0:
            return
        output_w = self.output_width.get()
        output_h = self.output_height.get()

        # Calcola zoom per far entrare l'immagine nel canvas mantenendo proporzioni
        zoom_w = (output_w / orig_w) * 100
        zoom_h = (output_h / orig_h) * 100
        new_zoom = int(min(zoom_w, zoom_h))
        new_zoom = max(1, min(1000, new_zoom))

        self._apply_zoom_and_center(new_zoom)

    def fit_contain(self):
        """Adatta il layer per riempire completamente il canvas (cover)"""
        if not self.selected_layer:
            return
        orig_w, orig_h = self.selected_layer.original_image.size
        if orig_w == 0 or orig_h == 0:
            return
        output_w = self.output_width.get()
        output_h = self.output_height.get()

        # Calcola zoom per coprire il canvas (potrebbe tagliare)
        zoom_w = (output_w / orig_w) * 100
        zoom_h = (output_h / orig_h) * 100
        new_zoom = int(max(zoom_w, zoom_h))
        new_zoom = max(1, min(1000, new_zoom))

        self._apply_zoom_and_center(new_zoom)

    def fit_fill_horizontal(self):
        """Adatta il layer per riempire orizzontalmente il canvas"""
        if not self.selected_layer:
            return
        orig_w, orig_h = self.selected_layer.original_image.size
        if orig_w == 0:
            return
        output_w = self.output_width.get()

        # Calcola zoom per riempire in larghezza
        new_zoom = int((output_w / orig_w) * 100)
        new_zoom = max(1, min(1000, new_zoom))

        self._apply_zoom_and_center(new_zoom)

    def fit_fill_vertical(self):
        """Adatta il layer per riempire verticalmente il canvas"""
        if not self.selected_layer:
            return
        orig_w, orig_h = self.selected_layer.original_image.size
        if orig_h == 0:
            return
        output_h = self.output_height.get()

        # Calcola zoom per riempire in altezza
        new_zoom = int((output_h / orig_h) * 100)
        new_zoom = max(1, min(1000, new_zoom))

        self._apply_zoom_and_center(new_zoom)

    def _apply_zoom_and_center(self, new_zoom):
        """Applica lo zoom e centra il layer"""
        self.selected_layer.zoom = new_zoom
        self.selected_layer.offset_x = 0
        self.selected_layer.offset_y = 0

        self.zoom_var.set(new_zoom)
        self.zoom_entry.delete(0, tk.END)
        self.zoom_entry.insert(0, str(new_zoom))
        self.offset_x_var.set(0)
        self.offset_y_var.set(0)
        self.offset_x_entry.delete(0, tk.END)
        self.offset_x_entry.insert(0, "0")
        self.offset_y_entry.delete(0, tk.END)
        self.offset_y_entry.insert(0, "0")

        self.redraw_canvas()
        self.update_size_display()

    # ==================== LAYER CONTROLS ====================

    def on_zoom_change(self, event=None):
        if self.selected_layer:
            self.selected_layer.zoom = int(self.zoom_var.get())
            self.zoom_entry.delete(0, tk.END)
            self.zoom_entry.insert(0, str(self.selected_layer.zoom))
            self.redraw_canvas()
            self.update_size_display()

    def on_zoom_entry(self, event=None):
        if self.selected_layer:
            try:
                value = int(self.zoom_entry.get())
                value = max(1, min(1000, value))
                self.selected_layer.zoom = value
                self.zoom_var.set(value)
                self.zoom_entry.delete(0, tk.END)
                self.zoom_entry.insert(0, str(value))
                self.redraw_canvas()
                self.update_size_display()
            except ValueError:
                pass

    def adjust_layer_zoom(self, delta):
        if self.selected_layer:
            new_zoom = max(1, min(1000, self.selected_layer.zoom + delta))
            self.selected_layer.zoom = new_zoom
            self.zoom_var.set(new_zoom)
            self.zoom_entry.delete(0, tk.END)
            self.zoom_entry.insert(0, str(new_zoom))
            self.redraw_canvas()
            self.update_size_display()

    def reset_layer_zoom(self):
        if self.selected_layer:
            self.selected_layer.zoom = 100
            self.zoom_var.set(100)
            self.zoom_entry.delete(0, tk.END)
            self.zoom_entry.insert(0, "100")
            self.redraw_canvas()
            self.update_size_display()

    def on_rotation_change(self, event=None):
        if self.selected_layer:
            self.selected_layer.rotation = int(self.rotation_var.get())
            self.selected_layer.invalidate_cache()
            self.rotation_entry.delete(0, tk.END)
            self.rotation_entry.insert(0, str(self.selected_layer.rotation))
            self.redraw_canvas()

    def on_rotation_entry(self, event=None):
        if self.selected_layer:
            try:
                value = int(self.rotation_entry.get())
                value = max(-180, min(180, value))
                self.selected_layer.rotation = value
                self.selected_layer.invalidate_cache()
                self.rotation_var.set(value)
                self.rotation_entry.delete(0, tk.END)
                self.rotation_entry.insert(0, str(value))
                self.redraw_canvas()
            except ValueError:
                pass

    def set_layer_rotation(self, angle):
        if self.selected_layer:
            self.selected_layer.rotation = angle
            self.selected_layer.invalidate_cache()
            self.rotation_var.set(angle)
            self.rotation_entry.delete(0, tk.END)
            self.rotation_entry.insert(0, str(angle))
            self.redraw_canvas()

    def on_position_change(self, event=None):
        if self.selected_layer:
            self.selected_layer.offset_x = int(self.offset_x_var.get())
            self.selected_layer.offset_y = int(self.offset_y_var.get())
            self.offset_x_entry.delete(0, tk.END)
            self.offset_x_entry.insert(0, str(self.selected_layer.offset_x))
            self.offset_y_entry.delete(0, tk.END)
            self.offset_y_entry.insert(0, str(self.selected_layer.offset_y))
            self.redraw_canvas()

    def on_position_entry(self, event=None):
        if self.selected_layer:
            try:
                x_val = int(self.offset_x_entry.get())
                y_val = int(self.offset_y_entry.get())
                self.selected_layer.offset_x = x_val
                self.selected_layer.offset_y = y_val
                self.offset_x_var.set(x_val)
                self.offset_y_var.set(y_val)
                self.redraw_canvas()
            except ValueError:
                pass

    def flip_horizontal(self):
        """Applica effetto specchio orizzontale"""
        if self.selected_layer:
            self.selected_layer.flip_h = not self.selected_layer.flip_h
            self.selected_layer.invalidate_cache()
            self.redraw_canvas()

    def flip_vertical(self):
        """Applica effetto specchio verticale"""
        if self.selected_layer:
            self.selected_layer.flip_v = not self.selected_layer.flip_v
            self.selected_layer.invalidate_cache()
            self.redraw_canvas()

    # ==================== CANVAS RENDERING ====================

    def get_layer_bounds(self, layer, output_w, output_h):
        """Calcola i bounds di un layer nell'output"""
        img = layer.get_transformed_image()
        img_w, img_h = img.size

        # Applica zoom
        zoom = layer.zoom / 100.0
        final_w = int(img_w * zoom)
        final_h = int(img_h * zoom)

        # Posizione centrata + offset
        x = (output_w - final_w) // 2 + layer.offset_x
        y = (output_h - final_h) // 2 + layer.offset_y

        return (x, y, final_w, final_h)

    def create_composite_image(self, output_w, output_h, for_export=False):
        """Crea l'immagine composita di tutti i layer

        Args:
            output_w, output_h: dimensioni output
            for_export: se True usa LANCZOS per qualità migliore
        """
        # Sfondo
        bg_color = self.bg_color_var.get()
        output = Image.new('RGBA', (output_w, output_h), color=bg_color)

        # Scegli algoritmo resize
        resample = Image.Resampling.LANCZOS if for_export else Image.Resampling.BILINEAR

        # Disegna ogni layer dal basso verso l'alto
        for layer in self.layers:
            img = layer.get_transformed_image()

            # Applica zoom
            zoom = layer.zoom / 100.0
            new_w = max(1, int(img.size[0] * zoom))
            new_h = max(1, int(img.size[1] * zoom))
            img = img.resize((new_w, new_h), resample)

            # Posizione
            x = (output_w - new_w) // 2 + layer.offset_x
            y = (output_h - new_h) // 2 + layer.offset_y

            # Incolla con trasparenza
            output.paste(img, (x, y), img)

        return output.convert('RGB')

    def _schedule_redraw(self):
        """Schedula un redraw con debounce"""
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(16, self._do_redraw)  # ~60fps max

    def _do_redraw(self):
        """Esegue il redraw effettivo"""
        self._redraw_job = None
        self._redraw_canvas_internal()

    def redraw_canvas(self, immediate=False):
        """Ridisegna il canvas (con debounce se non immediate)"""
        if immediate or self.is_dragging:
            self._redraw_canvas_internal()
        else:
            self._schedule_redraw()

    def _redraw_canvas_internal(self):
        """Implementazione interna del redraw"""
        if not self.layers:
            self.draw_empty_canvas()
            return

        self.canvas.update_idletasks()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w < 10 or canvas_h < 10:
            return

        output_w = self.output_width.get()
        output_h = self.output_height.get()

        # Scala preview
        self.preview_scale = min(canvas_w / output_w, canvas_h / output_h) * 0.9
        preview_w = int(output_w * self.preview_scale)
        preview_h = int(output_h * self.preview_scale)

        # Crea immagine composita (versione preview veloce)
        composite = self.create_composite_image(output_w, output_h, for_export=False)

        # Ridimensiona per preview - usa NEAREST per velocità durante il drag
        resample = Image.Resampling.NEAREST if self.is_dragging else Image.Resampling.BILINEAR
        preview = composite.resize((preview_w, preview_h), resample)
        self.display_image = ImageTk.PhotoImage(preview)

        # Pulisci e disegna
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, canvas_w, canvas_h, fill="#0a1929", outline="")

        # Posizione canvas output
        canvas_x = (canvas_w - preview_w) // 2
        canvas_y = (canvas_h - preview_h) // 2
        self.canvas_bounds = (canvas_x, canvas_y, preview_w, preview_h)

        # Bordo output
        self.canvas.create_rectangle(canvas_x-1, canvas_y-1, canvas_x+preview_w+1, canvas_y+preview_h+1,
                                     outline="#666666", width=1)

        # Immagine
        self.canvas.create_image(canvas_x, canvas_y, anchor=tk.NW, image=self.display_image)

        # Calcola e salva bounds di ogni layer nel canvas
        for layer in self.layers:
            bounds = self.get_layer_bounds(layer, output_w, output_h)
            # Converti in coordinate canvas
            lx = canvas_x + int(bounds[0] * self.preview_scale)
            ly = canvas_y + int(bounds[1] * self.preview_scale)
            lw = int(bounds[2] * self.preview_scale)
            lh = int(bounds[3] * self.preview_scale)
            layer.bounds_in_canvas = (lx, ly, lw, lh)

        # Disegna selezione del layer selezionato
        if self.selected_layer and self.selected_layer.bounds_in_canvas:
            self.draw_selection_handles(self.selected_layer)

        # Info
        self.info_label.config(text=f"Output: {output_w}x{output_h} | Layers: {len(self.layers)}")

    def draw_selection_handles(self, layer):
        """Disegna gli handle di selezione per un layer"""
        if layer.bounds_in_canvas is None:
            return

        x, y, w, h = layer.bounds_in_canvas

        # Rettangolo selezione
        self.canvas.create_rectangle(x, y, x+w, y+h,
                                     outline=HANDLE_COLOR, width=2, dash=(4, 4))

        self.handles.clear()

        # 8 handle + rotazione
        positions = {
            'nw': (x, y), 'n': (x + w//2, y), 'ne': (x + w, y),
            'e': (x + w, y + h//2), 'se': (x + w, y + h),
            's': (x + w//2, y + h), 'sw': (x, y + h), 'w': (x, y + h//2),
        }

        # Handle rotazione
        rotate_x = x + w//2
        rotate_y = y - ROTATION_HANDLE_DISTANCE
        positions['rotate'] = (rotate_x, rotate_y)

        self.canvas.create_line(x + w//2, y, rotate_x, rotate_y, fill=HANDLE_COLOR, width=2)

        for handle_id, (hx, hy) in positions.items():
            self.handles[handle_id] = (hx, hy)

            if handle_id == 'rotate':
                self.canvas.create_oval(hx - HANDLE_SIZE - 2, hy - HANDLE_SIZE - 2,
                                        hx + HANDLE_SIZE + 2, hy + HANDLE_SIZE + 2,
                                        fill="#00aa00", outline="white", width=2)
                self.canvas.create_text(hx, hy, text="↻", fill="white", font=('Segoe UI', 9, 'bold'))
            else:
                hs = HANDLE_SIZE // 2
                self.canvas.create_rectangle(hx - hs, hy - hs, hx + hs, hy + hs,
                                            fill="white", outline=HANDLE_COLOR, width=2)

    # ==================== MOUSE EVENTS ====================

    def get_handle_at(self, x, y):
        """Trova handle alla posizione"""
        for handle_id, (hx, hy) in self.handles.items():
            dist = math.sqrt((x - hx)**2 + (y - hy)**2)
            threshold = HANDLE_SIZE * 2 if handle_id == 'rotate' else HANDLE_SIZE * 1.5
            if dist <= threshold:
                return handle_id
        return None

    def get_layer_at(self, x, y):
        """Trova il layer alla posizione (dall'alto verso il basso)"""
        for layer in reversed(self.layers):
            if layer.bounds_in_canvas:
                lx, ly, lw, lh = layer.bounds_in_canvas
                if lx <= x <= lx + lw and ly <= y <= ly + lh:
                    return layer
        return None

    def on_mouse_down(self, event):
        if not self.layers:
            return

        # Controlla handle del layer selezionato
        if self.selected_layer:
            handle = self.get_handle_at(event.x, event.y)
            if handle:
                self.active_handle = handle
                self.is_dragging = True

                if handle == 'rotate':
                    if self.selected_layer.bounds_in_canvas:
                        bx, by, bw, bh = self.selected_layer.bounds_in_canvas
                        self.rotation_center = (bx + bw//2, by + bh//2)
                        self.rotation_start_angle = math.atan2(event.y - self.rotation_center[1],
                                                               event.x - self.rotation_center[0])
                        self.rotation_start_value = self.selected_layer.rotation
                else:
                    self.resize_start_zoom = self.selected_layer.zoom
                    self.resize_start_pos = (event.x, event.y)
                    if self.selected_layer.bounds_in_canvas:
                        bx, by, bw, bh = self.selected_layer.bounds_in_canvas
                        self.rotation_center = (bx + bw//2, by + bh//2)
                return

        # Controlla click su layer
        clicked_layer = self.get_layer_at(event.x, event.y)

        if clicked_layer:
            self.selected_layer = clicked_layer
            self.is_dragging = True
            self.active_handle = None
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.drag_start_offset_x = clicked_layer.offset_x
            self.drag_start_offset_y = clicked_layer.offset_y

            # Aggiorna selezione nella lista
            idx = self.layers.index(clicked_layer)
            self.layers_listbox.selection_clear(0, tk.END)
            self.layers_listbox.selection_set(idx)
            self.update_layer_controls()
            self.update_layers_list()
            self.redraw_canvas()
        else:
            # Click fuori - deseleziona
            self.selected_layer = None
            self.layers_listbox.selection_clear(0, tk.END)
            self.update_layers_list()
            self.redraw_canvas()

    def on_mouse_move(self, event):
        if not self.is_dragging or not self.selected_layer:
            return

        if self.active_handle == 'rotate':
            # Rotazione
            cx, cy = self.rotation_center
            current_angle = math.atan2(event.y - cy, event.x - cx)
            angle_diff = math.degrees(current_angle - self.rotation_start_angle)

            new_rotation = self.rotation_start_value + angle_diff
            while new_rotation > 180: new_rotation -= 360
            while new_rotation < -180: new_rotation += 360

            self.selected_layer.rotation = int(new_rotation)
            self.rotation_var.set(int(new_rotation))
            self.rotation_entry.delete(0, tk.END)
            self.rotation_entry.insert(0, str(int(new_rotation)))
            self.redraw_canvas()

        elif self.active_handle:
            # Resize
            cx, cy = self.rotation_center
            dx = event.x - cx
            dy = event.y - cy
            current_dist = math.sqrt(dx**2 + dy**2)

            start_dx = self.resize_start_pos[0] - cx
            start_dy = self.resize_start_pos[1] - cy
            start_dist = math.sqrt(start_dx**2 + start_dy**2)

            if start_dist > 5:
                scale = current_dist / start_dist
                new_zoom = max(1, min(1000, int(self.resize_start_zoom * scale)))
                self.selected_layer.zoom = new_zoom
                self.zoom_var.set(new_zoom)
                self.zoom_entry.delete(0, tk.END)
                self.zoom_entry.insert(0, str(new_zoom))
                self.redraw_canvas()
                self.update_size_display()
        else:
            # Spostamento
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y

            scale = 1.0 / self.preview_scale if self.preview_scale > 0 else 1.0

            self.selected_layer.offset_x = self.drag_start_offset_x + int(dx * scale)
            self.selected_layer.offset_y = self.drag_start_offset_y + int(dy * scale)

            self.offset_x_var.set(self.selected_layer.offset_x)
            self.offset_y_var.set(self.selected_layer.offset_y)

            self.redraw_canvas()

    def on_mouse_up(self, event):
        self.is_dragging = False
        self.active_handle = None
        if self.layers:
            self.redraw_canvas()

    def on_mouse_hover(self, event):
        if not self.layers:
            self.canvas.config(cursor="")
            return

        if self.selected_layer:
            handle = self.get_handle_at(event.x, event.y)
            if handle:
                cursors = {
                    'nw': 'size_nw_se', 'se': 'size_nw_se',
                    'ne': 'size_ne_sw', 'sw': 'size_ne_sw',
                    'n': 'size_ns', 's': 'size_ns',
                    'e': 'size_we', 'w': 'size_we',
                    'rotate': 'exchange'
                }
                self.canvas.config(cursor=cursors.get(handle, 'arrow'))
                return

        layer = self.get_layer_at(event.x, event.y)
        if layer:
            self.canvas.config(cursor="fleur" if layer == self.selected_layer else "hand2")
        else:
            self.canvas.config(cursor="")

    def on_mouse_wheel(self, event):
        """Zoom con mouse wheel sul canvas - sensibilità ridotta"""
        if self.selected_layer:
            # Delta più piccolo per zoom più delicato
            delta = 1 if event.delta > 0 else -1
            self.adjust_layer_zoom(delta)

    def on_left_panel_scroll(self, event):
        """Scroll del pannello sinistro con mouse wheel"""
        if event.delta != 0:
            self.left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"  # Previene propagazione

    def _bind_scroll_to_children(self, widget):
        """Bind ricorsivo dello scroll a tutti i widget figli"""
        for child in widget.winfo_children():
            child.bind("<MouseWheel>", self.on_left_panel_scroll)
            self._bind_scroll_to_children(child)

    def on_canvas_resize(self, event):
        if self.layers:
            self.redraw_canvas()
        else:
            self.draw_empty_canvas()

    def on_delete_key(self, event=None):
        if self.selected_layer:
            self.remove_selected_layer()

    def on_escape_key(self, event=None):
        self.selected_layer = None
        self.layers_listbox.selection_clear(0, tk.END)
        self.update_layers_list()
        self.redraw_canvas()

    # ==================== OUTPUT SETTINGS ====================

    def on_preset_change(self, event=None):
        preset = self.preset_combo.get()
        resolution = RESOLUTION_PRESETS.get(preset)
        if resolution:
            self.output_width.set(resolution[0])
            self.output_height.set(resolution[1])
            self.redraw_canvas()

    def apply_resolution(self):
        try:
            w = int(self.output_width.get())
            h = int(self.output_height.get())
            if w < 1 or h < 1:
                raise ValueError("Dimensioni non valide")
            self.preset_combo.set("Personalizzato")
            self.redraw_canvas()
        except (ValueError, tk.TclError):
            messagebox.showerror("Errore", "Valori non validi")

    def set_bg_color(self, color):
        self.bg_color_var.set(color)
        self.redraw_canvas()

    def choose_custom_color(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="Scegli colore sfondo")
        if color[1]:
            self.set_bg_color(color[1])

    def on_img_quality_change(self, event=None):
        self.img_quality_label.config(text=f"{int(self.img_quality.get())}%")

    def on_vid_quality_preset_change(self, event=None):
        """Aggiorna i parametri video in base al preset selezionato"""
        preset = self.vid_quality_preset.get()
        if preset == "bassa":
            self.vid_quality.set(50)
            self.vid_bitrate.set(2000)
            info_text = "Bitrate: 2000 kbps | CRF: 28"
        elif preset == "media":
            self.vid_quality.set(75)
            self.vid_bitrate.set(5000)
            info_text = "Bitrate: 5000 kbps | CRF: 23"
        else:  # alta
            self.vid_quality.set(100)
            self.vid_bitrate.set(8000)
            info_text = "Bitrate: 8000 kbps | CRF: 18"
        self.vid_quality_info_label.config(text=info_text)

    def set_video_export_enabled(self, enabled):
        """Abilita/disabilita il box esportazione video"""
        state = 'normal' if enabled else 'disabled'
        for child in self.video_export_frame.winfo_children():
            self._set_widget_state(child, state)
        # Cambia colore del frame
        if enabled:
            self.video_export_frame.config(text="🎬 Esporta Video")
        else:
            self.video_export_frame.config(text="🎬 Esporta Video (nessun video)")

    def set_image_export_enabled(self, enabled):
        """Abilita/disabilita il box esportazione immagine"""
        state = 'normal' if enabled else 'disabled'
        for child in self.image_export_frame.winfo_children():
            self._set_widget_state(child, state)
        if enabled:
            self.image_export_frame.config(text="🖼️ Esporta Immagine")
        else:
            self.image_export_frame.config(text="🖼️ Esporta Immagine (nessuna immagine)")

    def _set_widget_state(self, widget, state):
        """Imposta ricorsivamente lo stato di un widget e i suoi figli"""
        try:
            widget.config(state=state)
        except tk.TclError:
            pass  # Widget non supporta state
        except Exception:
            pass
        for child in widget.winfo_children():
            self._set_widget_state(child, state)

    def update_export_panels(self):
        """Aggiorna i pannelli di esportazione in base ai layer presenti"""
        has_videos = any(getattr(layer, 'is_video', False) for layer in self.layers)

        # Se non ci sono layer, disabilita entrambi
        if not self.layers:
            self.set_image_export_enabled(False)
            self.set_video_export_enabled(False)
        else:
            # Immagine sempre abilitata se ci sono layer (può esportare un frame)
            self.set_image_export_enabled(True)
            # Video solo se c'è almeno un video
            self.set_video_export_enabled(has_videos)

    def clear_all(self):
        """Rimuove tutti i layer"""
        if self.layers:
            if messagebox.askyesno("Conferma", "Rimuovere tutti gli elementi?"):
                self.layers.clear()
                self.selected_layer = None
                self.update_layers_list()
                self.update_export_panels()
                self.file_label.config(text="📁 Aggiungi immagini per creare un collage")
                self.redraw_canvas()

    # ==================== EXPORT ====================

    def export_image(self):
        """Esporta come immagine"""
        if not self.layers:
            messagebox.showwarning("Avviso", "Aggiungi almeno un'immagine")
            return

        fmt = self.output_format.get()
        ext = f".{fmt}"

        filepath = filedialog.asksaveasfilename(
            title="Salva collage",
            defaultextension=ext,
            initialfile=f"collage{ext}",
            filetypes=[(fmt.upper(), f"*{ext}")]
        )

        if not filepath:
            return

        self.progress.start()
        thread = threading.Thread(target=self._do_export_image, args=(filepath,))
        thread.start()

    def export_video(self):
        """Esporta come video"""
        if not VIDEO_SUPPORT:
            messagebox.showerror("Errore", "OpenCV non installato. Installa con: pip install opencv-python")
            return

        # Trova video nei layer
        video_layers = [layer for layer in self.layers if hasattr(layer, 'is_video') and layer.is_video]
        if not video_layers:
            messagebox.showwarning("Avviso", "Nessun video caricato. Per esportare video carica almeno un file video.")
            return

        fmt = self.video_format.get()
        ext = f".{fmt}"

        filepath = filedialog.asksaveasfilename(
            title="Salva video",
            defaultextension=ext,
            initialfile=f"video_output{ext}",
            filetypes=[(fmt.upper(), f"*{ext}")]
        )

        if not filepath:
            return

        self.progress.start()
        thread = threading.Thread(target=self._do_export_video, args=(filepath, video_layers[0]))
        thread.start()

    def _do_export_image(self, filepath):
        try:
            output_w = self.output_width.get()
            output_h = self.output_height.get()

            # Usa for_export=True per qualità massima
            img = self.create_composite_image(output_w, output_h, for_export=True)
            quality = self.img_quality.get()
            ext = Path(filepath).suffix.lower()

            if ext in ['.jpg', '.jpeg']:
                img.convert('RGB').save(filepath, 'JPEG', quality=quality, optimize=True)
            elif ext == '.png':
                img.save(filepath, 'PNG', optimize=True)
            elif ext == '.webp':
                img.save(filepath, 'WEBP', quality=quality)
            else:
                img.save(filepath)

            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: messagebox.showinfo("Successo", f"Collage salvato:\n{filepath}"))
        except Exception as ex:
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda err=str(ex): messagebox.showerror("Errore", err))

    def _do_export_video(self, filepath, video_layer):
        """Esporta video con tutte le trasformazioni applicate"""
        cap = None
        out = None
        try:
            output_w = self.output_width.get()
            output_h = self.output_height.get()
            fps = self.fps_var.get()
            ext = Path(filepath).suffix.lower()

            cap = cv2.VideoCapture(video_layer.video_path)
            if not cap.isOpened():
                raise Exception("Impossibile aprire il video sorgente")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Codec in base al formato
            if ext == '.mp4':
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            elif ext == '.avi':
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
            elif ext == '.webm':
                fourcc = cv2.VideoWriter_fourcc(*'VP80')
            elif ext == '.gif':
                # Per GIF usiamo un approccio diverso con ottimizzazione memoria
                frames = []
                frame_count = 0

                # Pre-calcola trasformazioni costanti
                needs_flip_h = video_layer.flip_h
                needs_flip_v = video_layer.flip_v
                rotation = video_layer.rotation
                zoom = video_layer.zoom / 100.0
                offset_x = video_layer.offset_x
                offset_y = video_layer.offset_y
                bg_color = self.bg_color_var.get()

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # Converti e processa frame
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_frame = Image.fromarray(frame_rgb)
                    processed = self._process_video_frame_optimized(
                        pil_frame, output_w, output_h,
                        needs_flip_h, needs_flip_v, rotation, zoom,
                        offset_x, offset_y, bg_color
                    )

                    # Per GIF converti a palette per risparmiare memoria
                    frames.append(processed.quantize(colors=256, method=Image.Quantize.MEDIANCUT))
                    frame_count += 1

                    # Aggiorna progress ogni 10 frame
                    if frame_count % 10 == 0:
                        progress_pct = int((frame_count / total_frames) * 100)
                        self.root.after(0, lambda p=progress_pct:
                                       self.info_label.config(text=f"Esportazione GIF: {p}%"))

                cap.release()
                cap = None

                if frames:
                    # Converti palette a RGB per save
                    rgb_frames = [f.convert('P') for f in frames]
                    rgb_frames[0].save(filepath, save_all=True, append_images=rgb_frames[1:],
                                       duration=int(1000/fps), loop=0, optimize=True)

                self.root.after(0, lambda: self.progress.stop())
                self.root.after(0, lambda: self.info_label.config(text=""))
                self.root.after(0, lambda: messagebox.showinfo("Successo", f"GIF salvata:\n{filepath}\n{frame_count} frames"))
                return
            else:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')

            out = cv2.VideoWriter(filepath, fourcc, fps, (output_w, output_h))
            if not out.isOpened():
                raise Exception("Impossibile creare il file video di output")

            # Pre-calcola trasformazioni costanti
            needs_flip_h = video_layer.flip_h
            needs_flip_v = video_layer.flip_v
            rotation = video_layer.rotation
            zoom = video_layer.zoom / 100.0
            offset_x = video_layer.offset_x
            offset_y = video_layer.offset_y
            bg_color = self.bg_color_var.get()

            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Converti frame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_frame = Image.fromarray(frame_rgb)

                # Applica trasformazioni (versione ottimizzata)
                processed = self._process_video_frame_optimized(
                    pil_frame, output_w, output_h,
                    needs_flip_h, needs_flip_v, rotation, zoom,
                    offset_x, offset_y, bg_color
                )

                # Converti a BGR per OpenCV
                output_frame = cv2.cvtColor(np.array(processed), cv2.COLOR_RGB2BGR)
                out.write(output_frame)

                frame_count += 1

                # Aggiorna progress ogni 30 frame
                if frame_count % 30 == 0:
                    progress_pct = int((frame_count / total_frames) * 100)
                    self.root.after(0, lambda p=progress_pct:
                                   self.info_label.config(text=f"Esportazione video: {p}%"))

            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.info_label.config(text=""))
            self.root.after(0, lambda: messagebox.showinfo("Successo", f"Video salvato:\n{filepath}\n{frame_count} frames"))

        except Exception as ex:
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.info_label.config(text=""))
            self.root.after(0, lambda err=str(ex): messagebox.showerror("Errore", err))
        finally:
            if cap is not None:
                cap.release()
            if out is not None:
                out.release()

    def _process_video_frame_optimized(self, frame, output_w, output_h,
                                        flip_h, flip_v, rotation, zoom,
                                        offset_x, offset_y, bg_color):
        """Processa un singolo frame video (versione ottimizzata con parametri pre-calcolati)"""
        # Crea sfondo
        output = Image.new('RGB', (output_w, output_h), color=bg_color)

        img = frame
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # Applica flip
        if flip_h:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if flip_v:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        # Applica rotazione
        if rotation != 0:
            img = img.rotate(-rotation, resample=Image.Resampling.BILINEAR, expand=True)

        # Applica zoom
        new_w = max(1, int(img.size[0] * zoom))
        new_h = max(1, int(img.size[1] * zoom))
        img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        # Posizione
        x = (output_w - new_w) // 2 + offset_x
        y = (output_h - new_h) // 2 + offset_y

        # Incolla
        output.paste(img, (x, y), img)

        return output

    def _process_video_frame(self, frame, video_layer, output_w, output_h):
        """Processa un singolo frame video con le trasformazioni del layer (legacy)"""
        return self._process_video_frame_optimized(
            frame, output_w, output_h,
            video_layer.flip_h, video_layer.flip_v, video_layer.rotation,
            video_layer.zoom / 100.0, video_layer.offset_x, video_layer.offset_y,
            self.bg_color_var.get()
        )


def main():
    root = tk.Tk()
    _app = RConverter(root)  # noqa: F841

    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
