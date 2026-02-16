"""
R-Converter PRO - Convertitore Broadcast per LED Wall
Applicazione per adattare immagini e video a risoluzioni broadcast,
con preset ottimizzati per Resolume, vMix, Millumin e export generico.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageFilter, ImageOps
import threading
from queue import Queue
import math
import re
import zipfile
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path
import uuid
from urllib.request import urlopen, Request
import sys
import os
import logging
import gc
import copy
import json

# Configura logging (solo su file in temp user, non nella cartella dell'exe)
def _get_log_path():
    """Restituisce il percorso del file di log in una posizione non invasiva"""
    # Usa la cartella AppData/Local per il log, non la cartella dell'exe
    if sys.platform == 'win32':
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        log_dir = Path(appdata) / 'R-Converter'
    else:
        log_dir = Path.home() / '.r-converter'
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback: cartella temp di sistema
        import tempfile
        log_dir = Path(tempfile.gettempdir())
    return log_dir / 'r_converter.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(_get_log_path(), encoding='utf-8', errors='replace'),
    ]
)
logger = logging.getLogger('R-Converter')

try:
    import cv2
    import numpy as np
    VIDEO_SUPPORT = True
    logger.info(f"OpenCV {cv2.__version__} caricato, supporto video attivo")
except ImportError:
    VIDEO_SUPPORT = False
    logger.info("OpenCV non disponibile, supporto video disattivato")

# Costanti per i formati supportati (set per lookup O(1))
IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'}
VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}

# Preset di risoluzioni comuni
RESOLUTION_PRESETS = {
    "Personalizzato": None,
    "3840x1152 (Holiday Inn 10m×3m)": (3840, 1152),
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

# =============================================================================
# DATI BROADCAST PRO - Preset LED Wall e Software Target
# =============================================================================

HZ_PRESETS = [25, 30, 50, 60]
HZ_DEFAULT = 50

# Quality tier: entry < professional < broadcast
QUALITY_ENTRY = "entry"
QUALITY_PROFESSIONAL = "professional"
QUALITY_BROADCAST = "broadcast"

# Chiavi preset LED wall (6 built-in)
LED_WALL_KEYS = [
    "novastar_a5_plus",
    "novastar_a8_plus",
    "novastar_a10_plus",
    "holiday_inn_uniview_gx",
    "uniview_2_6",
    "waveco_2_9",
]

# Chiavi software target (5 opzioni)
SOFTWARE_KEYS = [
    "resolume",
    "vmix",
    "millumin",
    "generic_h264",
    "generic_h265",
]

# LED Wall Specs - 6 preset validati su hardware reale
# refresh_hz = refresh pannello; input_signal_hz = segnale HDMI (50/60)
LED_WALL_SPECS = {
    "novastar_a5_plus": {
        "name": "NovaStar A5 Plus",
        "brand": "NovaStar",
        "receiving_card": "A5S Plus",
        "driver_ic": "ICN2153 / MBI5124",
        "pixel_pitch_mm": 2.5,
        "quality_tier": QUALITY_ENTRY,
        "gray_depth": 13,
        "scan_type": "1/16",
        "scan_ratio": 16,
        "gamma": 2.2,
        "refresh_hz": 1920,
        "input_signal_hz": 50,
        "optimal_fps": [25, 30, 50, 60],
        "description": "Entry-level, 13-bit grayscale",
    },
    "novastar_a8_plus": {
        "name": "NovaStar A8 Plus",
        "brand": "NovaStar",
        "receiving_card": "A8S Plus",
        "driver_ic": "ICN2153S / MBI5153",
        "pixel_pitch_mm": 2.0,
        "quality_tier": QUALITY_PROFESSIONAL,
        "gray_depth": 14,
        "scan_type": "1/16",
        "scan_ratio": 16,
        "gamma": 2.2,
        "refresh_hz": 3840,
        "input_signal_hz": 50,
        "optimal_fps": [25, 30, 50, 60],
        "description": "Professional, 14-bit grayscale",
    },
    "novastar_a10_plus": {
        "name": "NovaStar A10 Plus",
        "brand": "NovaStar",
        "receiving_card": "A10S Plus",
        "driver_ic": "ICN2053 / MBI5264",
        "pixel_pitch_mm": 1.5,
        "quality_tier": QUALITY_BROADCAST,
        "gray_depth": 16,
        "scan_type": "1/32",
        "scan_ratio": 32,
        "gamma": 2.2,
        "refresh_hz": 7680,
        "input_signal_hz": 50,
        "optimal_fps": [25, 30, 50, 60],
        "description": "Broadcast, 16-bit grayscale",
    },
    "holiday_inn_uniview_gx": {
        "name": "Holiday Inn 2.6mm Uniview GX",
        "brand": "Uniview",
        "receiving_card": "A5S Plus",
        "driver_ic": "ICN2153 (ChipCode 232)",
        "pixel_pitch_mm": 2.604,
        "quality_tier": QUALITY_PROFESSIONAL,
        "gray_depth": 13,
        "scan_type": "1/24",
        "scan_ratio": 24,
        "gamma": 2.2,
        "refresh_hz": 1920,
        "input_signal_hz": 50,
        "width_px": 192,
        "height_px": 384,
        "cabinet_width_mm": 500.0,
        "cabinet_height_mm": 1000.0,
        "optimal_fps": [25, 30, 50, 60],
        "description": "Installazione Holiday Inn, 3840x1152, cabinet 500x1000mm",
    },
    "uniview_2_6": {
        "name": "Uniview 2.6mm",
        "brand": "Uniview",
        "receiving_card": "A5S Plus",
        "driver_ic": "ICN2153",
        "pixel_pitch_mm": 2.604,
        "quality_tier": QUALITY_PROFESSIONAL,
        "gray_depth": 13,
        "scan_type": "1/24",
        "scan_ratio": 24,
        "gamma": 1.8,
        "refresh_hz": 1920,
        "input_signal_hz": 50,
        "optimal_fps": [25, 30, 50, 60],
        "description": "Rental, gamma 1.8 custom",
    },
    "waveco_2_9": {
        "name": "Wave&Co 2.9mm",
        "brand": "Wave&Co",
        "receiving_card": "i5A-F (Colorlight)",
        "driver_ic": "MBI5124 / ICN2038",
        "pixel_pitch_mm": 2.91,
        "quality_tier": QUALITY_PROFESSIONAL,
        "gray_depth": 14,
        "scan_type": "1/16",
        "scan_ratio": 16,
        "gamma": 2.2,
        "refresh_hz": 1920,
        "input_signal_hz": 50,
        "dual_frequency": True,
        "supported_hz": [50, 60],
        "width_px": 172,
        "height_px": 344,
        "optimal_fps": [25, 30, 50, 60],
        "description": "Colorlight, dual 50/60Hz",
    },
}

# Filtri Magic Upscale per ogni LED wall
FILTER_PROFILES = {
    "novastar_a5_plus": {
        "deband_threshold": 48,
        "deband_grain": 4,
        "dither_type": "bayer",
        "dither_scale": 2,
        "black_level": 3,
        "white_level": 252,
        "denoise_strength": 0.40,
        "sharpen_amount": 0.25,
        "bilateral_sigma_s": 2,
        "bilateral_sigma_r": 0.08,
    },
    "novastar_a8_plus": {
        "deband_threshold": 40,
        "deband_grain": 3,
        "dither_type": "bayer",
        "dither_scale": 2,
        "black_level": 2,
        "white_level": 253,
        "denoise_strength": 0.35,
        "sharpen_amount": 0.25,
        "bilateral_sigma_s": 2,
        "bilateral_sigma_r": 0.08,
    },
    "novastar_a10_plus": {
        "deband_threshold": 32,
        "deband_grain": 2,
        "dither_type": "bayer",
        "dither_scale": 1,
        "black_level": 1,
        "white_level": 254,
        "denoise_strength": 0.30,
        "sharpen_amount": 0.25,
        "bilateral_sigma_s": 2,
        "bilateral_sigma_r": 0.08,
    },
    "holiday_inn_uniview_gx": {
        "deband_threshold": 44,
        "deband_grain": 4,
        "dither_type": "bayer",
        "dither_scale": 2,
        "black_level": 3,
        "white_level": 252,
        "denoise_strength": 0.40,
        "sharpen_amount": 0.28,
        "bilateral_sigma_s": 2,
        "bilateral_sigma_r": 0.08,
    },
    "uniview_2_6": {
        "deband_threshold": 44,
        "deband_grain": 4,
        "dither_type": "bayer",
        "dither_scale": 2,
        "black_level": 2,
        "white_level": 253,
        "denoise_strength": 0.38,
        "sharpen_amount": 0.28,
        "bilateral_sigma_s": 2,
        "bilateral_sigma_r": 0.08,
    },
    "waveco_2_9": {
        "deband_threshold": 42,
        "deband_grain": 3,
        "dither_type": "bayer",
        "dither_scale": 2,
        "black_level": 2,
        "white_level": 253,
        "denoise_strength": 0.36,
        "sharpen_amount": 0.30,
        "bilateral_sigma_s": 2,
        "bilateral_sigma_r": 0.08,
    },
}

# Profili video base (codec, container, bitrate, color space)
VIDEO_PROFILES_BASE = {
    "dnxhr_sq": {"codec": "dnxhd", "profile": "dnxhr_sq", "pixel_format": "yuv422p", "container": "mov",
                 "color_space": "Rec.709", "bit_depth": 8,
                 "bitrate_mode": "cbr", "bitrate_1080p_mbps": 145, "bitrate_4k_mbps": 580,
                 "gop_size": 1, "b_frames": 0},
    "dnxhr_hq": {"codec": "dnxhd", "profile": "dnxhr_hq", "pixel_format": "yuv422p", "container": "mov",
                 "color_space": "Rec.709", "bit_depth": 8,
                 "bitrate_mode": "cbr", "bitrate_1080p_mbps": 220, "bitrate_4k_mbps": 880,
                 "gop_size": 1, "b_frames": 0},
    "dnxhr_hqx": {"codec": "dnxhd", "profile": "dnxhr_hqx", "pixel_format": "yuv422p10le", "container": "mov",
                  "color_space": "Rec.709", "bit_depth": 10,
                  "bitrate_mode": "cbr", "bitrate_1080p_mbps": 220, "bitrate_4k_mbps": 880,
                  "gop_size": 1, "b_frames": 0},
    "hap": {"codec": "hap", "format_name": "hap", "pixel_format": "rgb24", "container": "mov",
            "color_space": "sRGB", "bit_depth": 8,
            "bitrate_mode": "vbr", "bitrate_1080p_mbps": 50, "bitrate_4k_mbps": 200,
            "gop_size": 1, "b_frames": 0, "hap_chunks": 8},
    "hap_q": {"codec": "hap", "format_name": "hap_q", "pixel_format": "rgb24", "container": "mov",
              "color_space": "sRGB", "bit_depth": 8,
              "bitrate_mode": "vbr", "bitrate_1080p_mbps": 180, "bitrate_4k_mbps": 720,
              "gop_size": 1, "b_frames": 0, "hap_chunks": 8},
    "prores_422": {"codec": "prores_ks", "profile": "2", "pixel_format": "yuv422p10le", "container": "mov",
                   "color_space": "Rec.709", "bit_depth": 10,
                   "bitrate_mode": "vbr", "bitrate_1080p_mbps": 147, "bitrate_4k_mbps": 588,
                   "gop_size": 1, "b_frames": 0},
    "h264_intra": {"codec": "libx264", "profile": "high", "level": "5.2", "pixel_format": "yuv420p",
                   "container": "mp4", "color_space": "Rec.709", "bit_depth": 8,
                   "bitrate_mode": "cbr", "bitrate_1080p_mbps": 200, "bitrate_4k_mbps": 800,
                   "gop_size": 1, "b_frames": 0, "preset": "fast"},
    "h265_intra": {"codec": "libx265", "profile": "main", "level": "5.1", "pixel_format": "yuv420p",
                   "container": "mp4", "color_space": "Rec.709", "bit_depth": 8,
                   "bitrate_mode": "cbr", "bitrate_1080p_mbps": 140, "bitrate_4k_mbps": 560,
                   "gop_size": 1, "b_frames": 0, "preset": "medium"},
}

# Profili audio
AUDIO_PROFILES = {
    "pcm_16": {"codec": "pcm_s16le", "sample_rate": 48000, "bit_depth": 16, "channels": 2, "bitrate_kbps": None},
    "pcm_24": {"codec": "pcm_s24le", "sample_rate": 48000, "bit_depth": 24, "channels": 2, "bitrate_kbps": None},
    "aac_320": {"codec": "aac", "sample_rate": 48000, "bit_depth": 16, "channels": 2, "bitrate_kbps": 320},
}

# Profili immagine broadcast per tier (receiver card, RCFGX, software)
IMAGE_PROFILES = {
    QUALITY_ENTRY: {"format": "png", "bit_depth": 8, "dpi": 72, "compression": 6, "quality_pct": 85},
    QUALITY_PROFESSIONAL: {"format": "png", "bit_depth": 8, "dpi": 150, "compression": 3, "quality_pct": 95},
    QUALITY_BROADCAST: {"format": "png", "bit_depth": 16, "dpi": 300, "compression": 1, "quality_pct": 100},
}

# Note compatibilità per software target (sw_info_label)
CODEC_COMPATIBILITY = {
    "resolume": "Resolume usa GPU per HAP. HAP Q = qualità massima. No audio embedded.",
    "vmix": "vMix usa DNxHR via CPU. HQ per HD, HQX (10-bit) per 4K.",
    "millumin": "Millumin supporta HAP Q e ProRes 422. Vendor apl0 per compatibilità.",
    "generic_h264": "Massima compatibilità. CBR intra-frame per scrub istantaneo.",
    "generic_h265": "30-40% più compatto di H.264. Richiede hardware recente.",
}


def get_export_profile(led_wall_key, software_key, output_hz, custom_presets=None):
    """
    Restituisce il profilo export ottimale per la combinazione LED wall + software.
    output_hz: frequenza segnale (25/30/50/60) - usata per FPS
    custom_presets: {name: data} per preset custom (filtri da magic_upscale_filters)
    """
    custom_presets = custom_presets or {}
    wall_spec = LED_WALL_SPECS.get(led_wall_key)
    if not wall_spec and led_wall_key.startswith("custom_"):
        name = led_wall_key[7:]
        cdata = custom_presets.get(name, {})
        gs = cdata.get("grayscale_specs", {})
        gray = gs.get("gray_depth_bits", 14)
        tier = QUALITY_ENTRY if gray <= 13 else (QUALITY_BROADCAST if gray >= 16 else QUALITY_PROFESSIONAL)
        wall_spec = {"quality_tier": tier}
        filters = cdata.get("magic_upscale_filters", FILTER_PROFILES["novastar_a8_plus"])
    elif not wall_spec:
        wall_spec = LED_WALL_SPECS["novastar_a8_plus"]
        led_wall_key = "novastar_a8_plus"
        filters = FILTER_PROFILES["novastar_a8_plus"]
    else:
        filters = FILTER_PROFILES.get(led_wall_key, FILTER_PROFILES["novastar_a8_plus"])
    tier = wall_spec["quality_tier"]

    # Video profile
    if software_key == "vmix":
        vid_key = "dnxhr_sq" if tier == QUALITY_ENTRY else "dnxhr_hq" if tier == QUALITY_PROFESSIONAL else "dnxhr_hqx"
    elif software_key == "resolume":
        vid_key = "hap" if tier == QUALITY_ENTRY else "hap_q"
    elif software_key == "millumin":
        vid_key = "prores_422" if tier == QUALITY_BROADCAST else ("hap" if tier == QUALITY_ENTRY else "hap_q")
    elif software_key == "generic_h265":
        vid_key = "h265_intra"
    else:
        vid_key = "h264_intra"

    video = copy.deepcopy(VIDEO_PROFILES_BASE[vid_key])
    video["framerate"] = min(output_hz, 60)

    # Audio
    if software_key in ("generic_h264", "generic_h265"):
        audio = AUDIO_PROFILES["aac_320"]
    elif tier == QUALITY_BROADCAST:
        audio = AUDIO_PROFILES["pcm_24"]
    else:
        audio = AUDIO_PROFILES["pcm_16"]

    # Image profile dal tier (broadcast-grade)
    img_prof = IMAGE_PROFILES.get(tier, IMAGE_PROFILES[QUALITY_PROFESSIONAL])

    return {
        "video": video,
        "audio": audio,
        "filters": filters,
        "image_format": img_prof["format"],
        "image_bit_depth": img_prof["bit_depth"],
        "image_dpi": img_prof["dpi"],
        "image_compression": img_prof["compression"],
        "image_quality_pct": img_prof["quality_pct"],
        "led_wall_spec": wall_spec,
        "software_target": software_key,
    }


class ImageLayer:
    """Rappresenta un'immagine nel collage con le sue proprietà"""
    __slots__ = ['id', 'original_image', 'name', 'offset_x', 'offset_y', 'zoom',
                 'rotation', 'flip_h', 'flip_v', 'is_video', 'video_path',
                 'video_fps', 'video_frames', 'bounds_in_canvas', '_cache', '_cache_key',
                 '_zoom_cache', '_zoom_cache_key']

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

        # Cache per immagine trasformata (rotation, flip)
        self._cache = None
        self._cache_key = None

        # Cache per immagine già zoomata (evita resize ripetuti durante pan)
        self._zoom_cache = None
        self._zoom_cache_key = None

    def get_transformed_image(self, use_cache=True, zoom=None, for_export=False):
        """Restituisce l'immagine con trasformazioni applicate (con cache).
        Se zoom è fornito, restituisce l'immagine già ridimensionata (cache separata).
        for_export: se True usa LANCZOS per qualità migliore (rotation, resize).
        """
        if self.original_image is None:
            return None

        base_key = (self.rotation, self.flip_h, self.flip_v)
        resample = Image.Resampling.LANCZOS if for_export else Image.Resampling.BILINEAR

        # Cache zoom: se zoom fornito e cache hit, ritorna subito
        if zoom is not None and use_cache:
            zoom_key = (*base_key, zoom)
            if self._zoom_cache is not None and self._zoom_cache_key == zoom_key:
                return self._zoom_cache

        # Base: trasformazioni (rotation, flip)
        if use_cache and self._cache is not None and self._cache_key == base_key:
            img = self._cache
        else:
            img = self.original_image.copy()
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            if self.flip_h:
                img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if self.flip_v:
                img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if self.rotation != 0:
                img = img.rotate(-self.rotation, resample=resample, expand=True)
            if use_cache:
                self._cache = img
                self._cache_key = base_key

        # Applica zoom se richiesto
        if zoom is not None:
            zoom_pct = zoom / 100.0
            new_w = max(1, int(img.size[0] * zoom_pct))
            new_h = max(1, int(img.size[1] * zoom_pct))
            img = img.resize((new_w, new_h), resample)
            if use_cache:
                self._zoom_cache = img
                self._zoom_cache_key = (*base_key, zoom)

        return img

    def invalidate_cache(self):
        """Invalida la cache dell'immagine trasformata"""
        self._cache = None
        self._cache_key = None
        self._zoom_cache = None
        self._zoom_cache_key = None

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
        self.root.title("R-Converter PRO  •  Broadcast LED Wall")
        self.root.state('zoomed')  # Fullscreen su Windows
        self.root.minsize(1100, 700)

        # Lista delle immagini (layers)
        self.layers = []
        self.selected_layer = None

        # Stato video (per il primo layer se è video)
        self.is_video = False
        self.video_file = None

        # Parametri output (default: Holiday Inn 3840x1152 @ 50Hz)
        self.output_width = tk.IntVar(value=3840)
        self.output_height = tk.IntVar(value=1152)
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
        self._resize_job = None

        # Cache dimensioni canvas (evita update_idletasks nel hot path)
        self._cached_canvas_size = (0, 0)

        # Oggetti canvas riutilizzabili (evita delete/create ogni frame)
        self._canvas_persistent_ids = None

        # Flag per evitare re-bind ricorsivo scroll
        self._scroll_bound = False
        self._scroll_bound_right = False

        # Parametri qualità export (gestiti da IMAGE_PROFILES via get_export_profile)

        # PRO: Broadcast - variabili pannello destro
        self.output_hz = tk.IntVar(value=HZ_DEFAULT)
        self.led_wall_var = tk.StringVar(value="novastar_a8_plus")
        self.software_target_var = tk.StringVar(value="resolume")
        self.custom_presets = {}
        # Processing sempre attivo al massimo (nascosto, obbligatorio)
        self.proc_uniform = tk.BooleanVar(value=True)
        self.proc_anti_solar = tk.BooleanVar(value=True)
        self.proc_anti_flicker = tk.BooleanVar(value=True)
        self.proc_anti_pixel = tk.BooleanVar(value=True)
        self.proc_intensity = tk.DoubleVar(value=100.0)  # 0-100 per Scale, convertito a 0-1 in processing
        self.ffmpeg_path = None

        # Setup
        self.setup_style()
        self.create_widgets()
        self.setup_bindings()
        self.setup_drag_and_drop()
        self._find_ffmpeg()
        self._load_presets_from_appdata()

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

        # Header bar: titolo (sinistra) | Check for Update (centro) | stato FFmpeg (destra)
        header = ttk.Frame(main_frame)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="R-Converter PRO", font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Button(header, text="Verifica FFmpeg", command=self._check_and_update_ffmpeg).pack(side=tk.LEFT, expand=True, padx=20)
        self.ffmpeg_status_label = ttk.Label(header, text="", font=('Segoe UI', 9))
        self.ffmpeg_status_label.pack(side=tk.RIGHT)
        self.root.after(500, self._update_ffmpeg_status_label)

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
        # Bind anche su Enter/Leave per propagare scroll a tutti i widget figli (una sola volta)
        self.left_canvas.bind("<Enter>", lambda e: self._bind_scroll_to_children_once(self.left_scrollable_frame))

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
        """Pannello destro PRO - Output, LED Wall, Software, Processing, Export"""
        right_container = ttk.Frame(parent, width=290)
        right_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_container.pack_propagate(False)

        self.right_canvas = tk.Canvas(right_container, bg=self.bg_color, highlightthickness=0, width=290)
        right_scrollbar = ttk.Scrollbar(right_container, orient="vertical", command=self.right_canvas.yview)
        right_scrollable = ttk.Frame(self.right_canvas)
        right_scrollable.bind("<Configure>", lambda e: self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all")))
        self.right_canvas.create_window((0, 0), window=right_scrollable, anchor="nw", width=275)
        self.right_canvas.configure(yscrollcommand=right_scrollbar.set)
        self.right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_canvas.bind("<MouseWheel>", self.on_right_panel_scroll)
        right_scrollable.bind("<MouseWheel>", self.on_right_panel_scroll)
        self.right_canvas.bind("<Enter>", lambda e: self._bind_scroll_to_children_once_right(right_scrollable))

        right_frame = right_scrollable

        # [1] Dimensioni Output + Hz
        output_frame = ttk.LabelFrame(right_frame, text="⬡ Dimensioni Output", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(output_frame, text="Preset:").pack(anchor=tk.W)
        self.preset_combo = ttk.Combobox(output_frame, values=list(RESOLUTION_PRESETS.keys()), state="readonly")
        self.preset_combo.set("3840x1152 (Holiday Inn 10m×3m)")
        self.preset_combo.pack(fill=tk.X, pady=(2, 5))
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_change)

        size_frame = ttk.Frame(output_frame)
        size_frame.pack(fill=tk.X)
        ttk.Label(size_frame, text="W:").grid(row=0, column=0)
        self.width_entry = ttk.Entry(size_frame, textvariable=self.output_width, width=7)
        self.width_entry.grid(row=0, column=1, padx=2)
        ttk.Label(size_frame, text="H:").grid(row=0, column=2, padx=(10, 0))
        self.height_entry = ttk.Entry(size_frame, textvariable=self.output_height, width=7)
        self.height_entry.grid(row=0, column=3, padx=2)

        ttk.Label(output_frame, text="Hz LED Wall:").pack(anchor=tk.W, pady=(8, 2))
        self.hz_combo = ttk.Combobox(output_frame, values=[f"{h} Hz" for h in HZ_PRESETS], state="readonly", width=10)
        self.hz_combo.set(f"{HZ_DEFAULT} Hz")
        self.hz_combo.pack(fill=tk.X, pady=(0, 5))
        self.hz_combo.bind("<<ComboboxSelected>>", self._on_hz_change)

        ttk.Button(output_frame, text="✓ Applica", command=self.apply_resolution).pack(pady=(5, 0))

        # [2] Sfondo
        bg_frame = ttk.LabelFrame(right_frame, text="◐ Sfondo", padding=10)
        bg_frame.pack(fill=tk.X, pady=(0, 8))

        color_grid = ttk.Frame(bg_frame)
        color_grid.pack()
        colors = [("#000000", "Nero"), ("#FFFFFF", "Bianco"), ("#808080", "Grigio"),
                  ("#FF0000", "Rosso"), ("#00FF00", "Verde"), ("#0000FF", "Blu"),
                  ("#FFFF00", "Giallo"), ("#FF00FF", "Magenta"), ("#00FFFF", "Ciano")]
        for i, (color, _) in enumerate(colors):
            btn = tk.Button(color_grid, bg=color, width=3, height=1, bd=0, activebackground=color, relief=tk.FLAT,
                            command=lambda c=color: self.set_bg_color(c))
            btn.grid(row=i // 3, column=i % 3, padx=2, pady=2)
        ttk.Button(bg_frame, text="⊞ Personalizza", command=self.choose_custom_color).pack(pady=(8, 0))

        # [3] LED Wall / Receiver Card
        led_frame = ttk.LabelFrame(right_frame, text="📺 LED Wall / Receiver Card", padding=10)
        led_frame.pack(fill=tk.X, pady=(0, 8))

        led_names = [LED_WALL_SPECS[k]["name"] for k in LED_WALL_KEYS]
        self.led_wall_combo = ttk.Combobox(led_frame, values=led_names, state="readonly", width=28)
        self.led_wall_combo.set(LED_WALL_SPECS["novastar_a8_plus"]["name"])
        self.led_wall_combo.pack(fill=tk.X, pady=(0, 5))
        self.led_wall_combo.bind("<<ComboboxSelected>>", self._on_led_wall_change)

        self.led_info_label = ttk.Label(led_frame, text="", font=('Segoe UI', 8), wraplength=250)
        self.led_info_label.pack(anchor=tk.W, pady=(0, 5))

        led_btn_frame = ttk.Frame(led_frame)
        led_btn_frame.pack(fill=tk.X)
        ttk.Button(led_btn_frame, text="Importa JSON", command=self._import_led_config).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(led_btn_frame, text="Salva", command=self._save_custom_preset).pack(side=tk.LEFT)

        # [4] Software Target
        sw_frame = ttk.LabelFrame(right_frame, text="🎯 Software Target", padding=10)
        sw_frame.pack(fill=tk.X, pady=(0, 8))

        sw_names = ["Resolume Arena (HAP Q)", "vMix (DNxHR)", "Millumin (HAP Q/ProRes)",
                    "Generico H.264", "Generico H.265"]
        self.software_combo = ttk.Combobox(sw_frame, values=sw_names, state="readonly", width=28)
        self.software_combo.set(sw_names[0])
        self.software_combo.pack(fill=tk.X, pady=(0, 5))
        self.software_combo.bind("<<ComboboxSelected>>", self._on_software_change)

        self.sw_info_label = ttk.Label(sw_frame, text="", font=('Segoe UI', 8), wraplength=250)
        self.sw_info_label.pack(anchor=tk.W)

        # [5] Processing Pre-Export: nascosto, sempre al massimo (proc_* = True, proc_intensity = 100)

        # [6] Riepilogo Export
        summary_frame = ttk.LabelFrame(right_frame, text="📋 Riepilogo Export", padding=10)
        summary_frame.pack(fill=tk.X, pady=(0, 8))

        self.summary_label = ttk.Label(summary_frame, text="", font=('Segoe UI', 9), wraplength=250)
        self.summary_label.pack(anchor=tk.W)

        # [6] Export Composito
        export_frame = ttk.LabelFrame(right_frame, text="▶ Export Composito", padding=12)
        export_frame.pack(fill=tk.X, pady=(0, 8))

        self.export_pro_btn = ttk.Button(export_frame, text="▶ ESPORTA COMPOSITO", style="Green.TButton",
                                         command=self.export_project)
        self.export_pro_btn.pack(fill=tk.X, ipady=4)

        self.progress = ttk.Progressbar(right_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(5, 10))

        self.fps_var = tk.IntVar(value=30)

        self._on_led_wall_change(None)
        self._on_software_change(None)
        self.update_export_summary()

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
        self.root.bind("<Control-s>", lambda e: self.export_image())
        self.root.bind("<Delete>", self.on_delete_key)
        self.root.bind("<Escape>", self.on_escape_key)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Motion>", self.on_mouse_hover)

    def setup_drag_and_drop(self):
        """Configura il drag and drop per file esterni.
        
        Usa windnd (Python puro, nessun subclassing pericoloso).
        Fallback: tkinterdnd2.
        Il setup è ritardato per assicurare che la finestra sia pronta.
        Con PyInstaller onefile (portable) serve più tempo: estrazione in temp.
        """
        self.drag_drop_enabled = False
        # Ritarda il setup: 500ms da sorgente, 1200ms se frozen/onefile (portable)
        delay = 1200 if getattr(sys, 'frozen', False) else 500
        self.root.after(delay, self._do_setup_drag_and_drop)

    def _find_ffmpeg(self):
        """Cerca ffmpeg: bundled (PyInstaller), LOCALAPPDATA, PATH, cartelle note."""
        import shutil
        candidates = []
        # 1. Bundled: PyInstaller onefile (sys._MEIPASS) o onedir (cartella exe)
        if getattr(sys, 'frozen', False):
            base = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
            candidates.append(base / "ffmpeg" / "bin" / "ffmpeg.exe")
        # 2. LOCALAPPDATA (download Check for Update)
        if sys.platform == 'win32':
            appdata = os.environ.get('LOCALAPPDATA', '')
            if appdata:
                candidates.append(Path(appdata) / "R-Converter" / "ffmpeg" / "bin" / "ffmpeg.exe")
        # 3. PATH
        path = shutil.which("ffmpeg")
        if path:
            self.ffmpeg_path = path
            logger.info(f"FFmpeg trovato: {path}")
            return
        # 4. Cartelle note
        for candidate in [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "ffmpeg", "bin", "ffmpeg.exe"),
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
        ]:
            candidates.append(Path(candidate))
        for c in candidates:
            p = Path(c) if not isinstance(c, Path) else c
            if p.is_file():
                self.ffmpeg_path = str(p)
                logger.info(f"FFmpeg trovato: {self.ffmpeg_path}")
                return
        self.ffmpeg_path = None
        logger.warning("FFmpeg non trovato - export video broadcast disabilitato")

    def _check_and_update_ffmpeg(self):
        """Verifica FFmpeg/codec e scarica da internet se mancanti."""
        try:
            if not self.ffmpeg_path:
                self._find_ffmpeg()
            missing = []
            if self.ffmpeg_path:
                out2 = subprocess.run([self.ffmpeg_path, "-codecs"], capture_output=True, text=True, timeout=10,
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) or 0)
                codecs_out = (out2.stdout or "") + (out2.stderr or "")
                required = ["dnxhd", "hap", "prores_ks", "libx264", "libx265"]
                for c in required:
                    if f" {c} " not in codecs_out and f".{c} " not in codecs_out:
                        missing.append(c)
            needs_download = not self.ffmpeg_path or missing
            if needs_download:
                ok = messagebox.askyesno("Verifica FFmpeg",
                    "FFmpeg non trovato o codec mancanti.\n\n"
                    "Scaricare FFmpeg (~31 MB) da internet?\n"
                    "(dnxhd, hap, prores_ks, libx264, libx265)\n\n"
                    "Build full: https://www.gyan.dev/ffmpeg/builds/")
                if ok:
                    threading.Thread(target=self._download_ffmpeg, daemon=True).start()
                return
            out = subprocess.run([self.ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) or 0)
            version_line = out.stdout.split("\n")[0] if out.stdout else "?"
            messagebox.showinfo("Verifica FFmpeg", f"FFmpeg aggiornato.\n\n{version_line}\n\nTutti i codec presenti.")
            self._update_ffmpeg_status_label()
        except subprocess.TimeoutExpired:
            messagebox.showerror("Timeout", "FFmpeg non ha risposto in tempo.")
        except Exception as e:
            logger.error(f"Check FFmpeg: {e}")
            messagebox.showerror("Errore", f"Impossibile verificare FFmpeg:\n{e}")

    def _download_ffmpeg(self):
        """Scarica ffmpeg-release-essentials.zip da gyan.dev ed estrae in LOCALAPPDATA."""
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        try:
            self.root.after(0, lambda: self.ffmpeg_status_label.config(text="Download FFmpeg..."))
            appdata = os.environ.get('LOCALAPPDATA', '') or os.path.expanduser('~')
            dest_dir = Path(appdata) / "R-Converter" / "ffmpeg"
            dest_dir.mkdir(parents=True, exist_ok=True)
            zip_path = dest_dir / "ffmpeg-release-essentials.zip"
            req = Request(url, headers={"User-Agent": "R-Converter/2.0"})
            with urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                data = resp.read()
            zip_path.write_bytes(data)
            self.root.after(0, lambda: self.ffmpeg_status_label.config(text="Estrazione..."))
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    if "ffmpeg.exe" in name or "ffprobe.exe" in name:
                        zf.extract(name, dest_dir)
            zip_path.unlink(missing_ok=True)
            ffmpeg_exe = None
            for p in dest_dir.rglob("ffmpeg.exe"):
                ffmpeg_exe = str(p)
                break
            if ffmpeg_exe:
                self.ffmpeg_path = ffmpeg_exe
                self.root.after(0, self._update_ffmpeg_status_label)
                self.root.after(0, lambda: messagebox.showinfo("Verifica FFmpeg", "FFmpeg scaricato e installato."))
            else:
                raise FileNotFoundError("ffmpeg.exe non trovato nell'archivio")
        except Exception as e:
            logger.error(f"Download FFmpeg: {e}")
            self.root.after(0, lambda: self.ffmpeg_status_label.config(text="FFmpeg ?"))
            self.root.after(0, lambda: messagebox.showerror("Errore", f"Download fallito:\n{e}"))

    def _update_ffmpeg_status_label(self):
        """Aggiorna la label di stato FFmpeg nell'header"""
        try:
            if not self.ffmpeg_path:
                self._find_ffmpeg()
            if self.ffmpeg_path:
                out = subprocess.run([self.ffmpeg_path, "-version"], capture_output=True, text=True, timeout=3,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) or 0)
                line = (out.stdout or "").split("\n")[0]
                ver = line.split("version")[1].strip().split()[0] if "version" in line else "?"
                self.ffmpeg_status_label.config(text=f"FFmpeg {ver}")
            else:
                self.ffmpeg_status_label.config(text="FFmpeg non trovato")
        except Exception as ex:
            logger.debug(f"update_ffmpeg_status_label: {ex}")
            if hasattr(self, 'ffmpeg_status_label'):
                self.ffmpeg_status_label.config(text="FFmpeg ?")

    def _do_setup_drag_and_drop(self):
        """Setup effettivo del drag and drop (chiamato dopo init finestra)"""
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass
        try:
            import windnd  # type: ignore[import-not-found]
            windnd.hook_dropfiles(self.root, func=self._on_drop_windnd)
            self.drag_drop_enabled = True
            logger.info("Drag & Drop: windnd attivo")
            return
        except ImportError:
            logger.info("windnd non installato, provo tkinterdnd2")
        except Exception as e:
            logger.warning(f"windnd fallito: {e}")

        # Tentativo 2: tkinterdnd2
        try:
            from tkinterdnd2 import DND_FILES  # type: ignore[import-not-found]
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind('<<Drop>>', self._on_drop_tkdnd)
            self.drag_drop_enabled = True
            logger.info("Drag & Drop: tkinterdnd2 attivo")
            return
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"tkinterdnd2 fallito: {e}")

        logger.warning("Drag & Drop non disponibile (installa windnd: pip install windnd)")

    def _process_dropped_files(self, files):
        """Processa la lista di file droppati (chiamato nel main thread Tk)"""
        for filepath in files:
            try:
                filepath = str(filepath).strip()
                if not filepath or not os.path.isfile(filepath):
                    logger.warning(f"File non valido nel drop: {filepath}")
                    continue

                ext = Path(filepath).suffix.lower()
                if ext in VIDEO_FORMATS:
                    self.load_video(filepath)
                elif ext in IMAGE_FORMATS:
                    self.load_image(filepath)
                else:
                    logger.info(f"Formato non supportato nel drop: {ext}")
            except Exception as e:
                logger.error(f"Errore elaborazione file droppato: {e}")

    def _on_drop_windnd(self, files):
        """Gestisce il drop di file tramite windnd"""
        processed = []
        for filepath in files:
            try:
                if isinstance(filepath, bytes):
                    try:
                        filepath = filepath.decode('utf-8')
                    except UnicodeDecodeError:
                        filepath = filepath.decode('cp1252', errors='replace')
                processed.append(str(filepath).strip('{}').strip('"').strip("'"))
            except Exception as e:
                logger.error(f"Errore decodifica file windnd: {e}")
        if processed:
            self._process_dropped_files(processed)

    def _on_drop_tkdnd(self, event):
        """Gestisce il drop di file tramite tkinterdnd2"""
        try:
            files = self.root.tk.splitlist(event.data)
            self._process_dropped_files([f.strip('{}') for f in files])
        except Exception as e:
            logger.error(f"Errore on_drop_tkdnd: {e}")

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
            filepath = str(filepath)
            if not os.path.isfile(filepath):
                logger.warning(f"File non trovato: {filepath}")
                return

            img = Image.open(filepath)
            img.load()  # Forza il caricamento e rilascia il file handle
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')

            name = Path(filepath).stem[:20]
            layer = ImageLayer(img, name)

            # Calcola zoom per far stare l'immagine nel canvas
            output_w = self.output_width.get()
            output_h = self.output_height.get()
            img_w, img_h = img.size

            if img_w == 0 or img_h == 0:
                logger.warning(f"Immagine con dimensioni zero: {filepath}")
                return

            # Calcola la scala per contenere l'immagine nell'output (evita div-by-zero)
            out_w = max(1, output_w)
            out_h = max(1, output_h)
            scale_x = out_w / img_w
            scale_y = out_h / img_h
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

            logger.info(f"Immagine caricata: {name} ({img_w}x{img_h}) zoom={fit_zoom}%")

        except Exception as e:
            logger.error(f"Errore caricamento immagine {filepath}: {e}")
            messagebox.showerror("Errore", f"Impossibile caricare:\n{filepath}\n{str(e)}")

    def load_video(self, filepath):
        """Carica un video - salva il percorso e usa il primo frame come anteprima"""
        if not VIDEO_SUPPORT:
            messagebox.showerror("Errore", "OpenCV non installato. Installa con: pip install opencv-python")
            return

        cap = None
        try:
            filepath = str(filepath)
            if not os.path.isfile(filepath):
                logger.warning(f"File video non trovato: {filepath}")
                return

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
            if fps <= 0:
                fps = 30.0  # Fallback sicuro
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            cap.release()
            cap = None

            name = f"🎬{Path(filepath).stem[:15]}"
            layer = ImageLayer(img, name)
            layer.video_path = filepath
            layer.video_fps = fps
            layer.video_frames = frame_count
            layer.is_video = True

            # Calcola zoom per far stare nel canvas
            output_w = self.output_width.get()
            output_h = self.output_height.get()
            img_w, img_h = img.size

            if img_w == 0 or img_h == 0:
                logger.warning(f"Video con frame di dimensioni zero: {filepath}")
                return

            out_w = max(1, output_w)
            out_h = max(1, output_h)
            scale_x = out_w / img_w
            scale_y = out_h / img_h
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

            logger.info(f"Video caricato: {name} ({img_w}x{img_h}) {duration:.1f}s @ {fps:.0f}fps")

        except Exception as e:
            logger.error(f"Errore caricamento video {filepath}: {e}")
            messagebox.showerror("Errore", f"Impossibile caricare video:\n{filepath}\n{str(e)}")
        finally:
            if cap is not None:
                cap.release()

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
            idx = self.layers.index(layer_to_remove)
            self.layers.remove(layer_to_remove)
            layer_to_remove.cleanup()  # Libera memoria
            # Seleziona il layer adiacente (precedente se possibile)
            if self.layers:
                new_idx = min(idx, len(self.layers) - 1)
                self.selected_layer = self.layers[new_idx]
            else:
                self.selected_layer = None
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

    def _apply_image_processing(self, img, filters, intensity=1.0):
        """Pipeline broadcast ottimizzata: color levels, deband, denoise, bilateral, sharpen.
        Una sola conversione PIL->numpy all'inizio, una numpy->PIL alla fine.
        intensity: 0-1 scala i parametri (da proc_intensity)
        """
        if not filters or img is None:
            return img
        try:
            arr = np.array(img)
            if arr.size == 0:
                return img
            if arr.shape[2] == 4:
                bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            else:
                bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            scale = max(0.01, min(1.0, float(intensity)))
            # 1+2. Color levels + deband combinati (float32, evita allocazioni intermedie)
            bl = int(filters.get("black_level", 0) * scale)
            wl = int(255 - (255 - filters.get("white_level", 255)) * scale)
            wl = max(wl, bl + 1)
            scale_val = 255.0 / (wl - bl)
            bgr_f = (bgr.astype(np.float32) - bl) * scale_val
            grain = int(filters.get("deband_grain", 2) * scale)
            if grain > 0 and VIDEO_SUPPORT:
                noise = np.random.randint(-grain, grain + 1, bgr.shape, dtype=np.int16)
                bgr_f = np.clip(bgr_f + noise.astype(np.float32), 0, 255)
            bgr = np.clip(bgr_f, 0, 255).astype(np.uint8)
            # 3. Denoise (median blur su BGR)
            dn = filters.get("denoise_strength", 0) * scale
            if dn > 0.2 and VIDEO_SUPPORT:
                k = 3 if dn < 0.5 else 5
                bgr = cv2.medianBlur(bgr, k)
            # 4. Bilateral (su BGR)
            if VIDEO_SUPPORT and bgr.shape[0] * bgr.shape[1] < 4_500_000:
                sigma_s = max(1, int(filters.get("bilateral_sigma_s", 2) * scale))
                sigma_r = filters.get("bilateral_sigma_r", 0.08) * scale
                bgr = cv2.bilateralFilter(bgr, d=5, sigmaColor=int(sigma_r * 255), sigmaSpace=sigma_s)
            # 5. Sharpen: converti a PIL (unica conversione finale)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            amt = filters.get("sharpen_amount", 0) * scale
            if amt > 0:
                percent = min(int(amt * 200), 200)
                img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=percent, threshold=2))
        except Exception as e:
            logger.warning(f"Processing filtri: {e}")
        return img

    def _apply_layer_transforms_to_image(self, img, layer, for_export=False):
        """Applica flip e rotation di un layer a un'immagine (per override frame video nel composito).
        for_export: se True usa LANCZOS per qualità migliore.
        """
        if img is None:
            return None
        img = img.copy()
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        if layer.flip_h:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if layer.flip_v:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        resample = Image.Resampling.LANCZOS if for_export else Image.Resampling.BILINEAR
        if layer.rotation != 0:
            img = img.rotate(-layer.rotation, resample=resample, expand=True)
        return img

    def create_composite_image(self, output_w, output_h, for_export=False, target_size=None,
                               video_frame_overrides=None, layers=None):
        """Crea l'immagine composita di tutti i layer (immagini + video)

        Args:
            output_w, output_h: dimensioni output (logiche)
            for_export: se True usa LANCZOS per qualità migliore
            target_size: (w, h) - se fornito, crea direttamente a questa dimensione
            video_frame_overrides: {layer: PIL.Image} - frame corrente per layer video (export video)
            layers: se fornito usa questi layer (thread-safe export); altrimenti self.layers
        """
        output_w = max(1, output_w)
        output_h = max(1, output_h)
        video_frame_overrides = video_frame_overrides or {}
        layers = layers if layers is not None else self.layers

        if target_size:
            target_w, target_h = target_size
            target_w = max(1, target_w)
            target_h = max(1, target_h)
            scale = min(target_w / output_w, target_h / output_h)
            out_img = Image.new('RGBA', (target_w, target_h), color=self.bg_color_var.get())
            resample = Image.Resampling.NEAREST
        else:
            scale = 1.0
            out_img = Image.new('RGBA', (output_w, output_h), color=self.bg_color_var.get())
            resample = Image.Resampling.LANCZOS if for_export else Image.Resampling.BILINEAR

        for layer in layers:
            try:
                if layer in video_frame_overrides and video_frame_overrides[layer] is not None:
                    img = self._apply_layer_transforms_to_image(video_frame_overrides[layer], layer, for_export=for_export)
                else:
                    img = layer.get_transformed_image(use_cache=True,
                        zoom=layer.zoom if target_size else None, for_export=for_export)
                if img is None:
                    continue

                if target_size:
                    new_w = max(1, int(img.size[0] * scale))
                    new_h = max(1, int(img.size[1] * scale))
                    img = img.resize((new_w, new_h), resample)
                    x = (target_w - new_w) // 2 + int(layer.offset_x * scale)
                    y = (target_h - new_h) // 2 + int(layer.offset_y * scale)
                else:
                    zoom_pct = layer.zoom / 100.0
                    new_w = max(1, int(img.size[0] * zoom_pct))
                    new_h = max(1, int(img.size[1] * zoom_pct))
                    img = img.resize((new_w, new_h), resample)
                    x = (output_w - new_w) // 2 + layer.offset_x
                    y = (output_h - new_h) // 2 + layer.offset_y

                try:
                    out_img.paste(img, (x, y), img)
                except ValueError:
                    try:
                        out_img.paste(img, (x, y))
                    except Exception as paste_ex:
                        logger.debug(f"Paste fallback layer {layer.name}: {paste_ex}")
            except Exception as e:
                logger.warning(f"Errore rendering layer {layer.name}: {e}")
                continue

        return out_img.convert('RGB')

    def _schedule_redraw(self, delay_ms=16):
        """Schedula un redraw con debounce (evita accumulo eventi durante drag)"""
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(delay_ms, self._do_redraw)

    def _do_redraw(self):
        """Esegue il redraw effettivo"""
        self._redraw_job = None
        self._redraw_canvas_internal()

    def redraw_canvas(self, immediate=False):
        """Ridisegna il canvas (con debounce per evitare lag durante interazioni)"""
        if immediate:
            self._redraw_canvas_internal()
        else:
            # Durante drag: 33ms (~30fps) per ridurre carico; altrimenti 16ms (~60fps)
            delay = 33 if self.is_dragging else 16
            self._schedule_redraw(delay)

    def _redraw_canvas_internal(self):
        """Implementazione interna del redraw"""
        if not self.layers:
            self._canvas_persistent_ids = None
            self.draw_empty_canvas()
            return

        # Usa cache dimensioni (aggiornata su Configure); fallback se non valida
        canvas_w, canvas_h = self._cached_canvas_size
        if canvas_w < 10 or canvas_h < 10:
            self.canvas.update_idletasks()
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            self._cached_canvas_size = (canvas_w, canvas_h)

        if canvas_w < 10 or canvas_h < 10:
            return

        output_w = max(1, self.output_width.get())
        output_h = max(1, self.output_height.get())

        # Scala preview (evita div-by-zero)
        self.preview_scale = min(canvas_w / output_w, canvas_h / output_h) * 0.9
        preview_w = int(output_w * self.preview_scale)
        preview_h = int(output_h * self.preview_scale)

        # Crea composita direttamente a risoluzione preview (evita resize da 4K->preview)
        composite = self.create_composite_image(
            output_w, output_h, for_export=False, target_size=(preview_w, preview_h)
        )
        self.display_image = ImageTk.PhotoImage(composite)

        canvas_x = (canvas_w - preview_w) // 2
        canvas_y = (canvas_h - preview_h) // 2
        self.canvas_bounds = (canvas_x, canvas_y, preview_w, preview_h)

        # Riusa oggetti canvas invece di delete/create ogni frame
        if self._canvas_persistent_ids is None:
            self.canvas.delete("all")
            bg_id = self.canvas.create_rectangle(0, 0, canvas_w, canvas_h, fill="#0a1929", outline="", tags="persistent")
            img_id = self.canvas.create_image(canvas_x, canvas_y, anchor=tk.NW, image=self.display_image, tags="persistent")
            border_id = self.canvas.create_rectangle(canvas_x-1, canvas_y-1, canvas_x+preview_w+1, canvas_y+preview_h+1,
                                                    outline="#666666", width=1, tags="persistent")
            self._canvas_persistent_ids = {"bg": bg_id, "img": img_id, "border": border_id}
        else:
            self.canvas.delete("handles")
            self.canvas.coords(self._canvas_persistent_ids["bg"], 0, 0, canvas_w, canvas_h)
            self.canvas.coords(self._canvas_persistent_ids["img"], canvas_x, canvas_y)
            self.canvas.itemconfig(self._canvas_persistent_ids["img"], image=self.display_image)
            self.canvas.coords(self._canvas_persistent_ids["border"],
                              canvas_x-1, canvas_y-1, canvas_x+preview_w+1, canvas_y+preview_h+1)

        # Calcola e salva bounds di ogni layer nel canvas
        for layer in self.layers:
            bounds = self.get_layer_bounds(layer, output_w, output_h)
            lx = canvas_x + int(bounds[0] * self.preview_scale)
            ly = canvas_y + int(bounds[1] * self.preview_scale)
            lw = int(bounds[2] * self.preview_scale)
            lh = int(bounds[3] * self.preview_scale)
            layer.bounds_in_canvas = (lx, ly, lw, lh)

        # Disegna handle (sempre create fresh, posizioni variabili)
        if self.selected_layer and self.selected_layer.bounds_in_canvas:
            self.draw_selection_handles(self.selected_layer)

        self.info_label.config(text=f"Output: {output_w}x{output_h} | Layers: {len(self.layers)}")

    def draw_selection_handles(self, layer):
        """Disegna gli handle di selezione per un layer (tag handles per riuso canvas)"""
        if layer.bounds_in_canvas is None:
            return

        x, y, w, h = layer.bounds_in_canvas

        self.handles.clear()

        # Rettangolo selezione e handle con tag per delete selettivo
        self.canvas.create_rectangle(x, y, x+w, y+h,
                                     outline=HANDLE_COLOR, width=2, dash=(4, 4), tags="handles")

        positions = {
            'nw': (x, y), 'n': (x + w//2, y), 'ne': (x + w, y),
            'e': (x + w, y + h//2), 'se': (x + w, y + h),
            's': (x + w//2, y + h), 'sw': (x, y + h), 'w': (x, y + h//2),
        }
        rotate_x = x + w//2
        rotate_y = y - ROTATION_HANDLE_DISTANCE
        positions['rotate'] = (rotate_x, rotate_y)

        self.canvas.create_line(x + w//2, y, rotate_x, rotate_y, fill=HANDLE_COLOR, width=2, tags="handles")

        for handle_id, (hx, hy) in positions.items():
            self.handles[handle_id] = (hx, hy)
            if handle_id == 'rotate':
                self.canvas.create_oval(hx - HANDLE_SIZE - 2, hy - HANDLE_SIZE - 2,
                                        hx + HANDLE_SIZE + 2, hy + HANDLE_SIZE + 2,
                                        fill="#00aa00", outline="white", width=2, tags="handles")
                self.canvas.create_text(hx, hy, text="↻", fill="white", font=('Segoe UI', 9, 'bold'), tags="handles")
            else:
                hs = HANDLE_SIZE // 2
                self.canvas.create_rectangle(hx - hs, hy - hs, hx + hs, hy + hs,
                                            fill="white", outline=HANDLE_COLOR, width=2, tags="handles")

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

    def _bind_scroll_to_children_once(self, widget):
        """Bind ricorsivo dello scroll a tutti i widget figli (eseguito una sola volta)"""
        if self._scroll_bound:
            return
        self._scroll_bound = True
        self._bind_scroll_to_children(widget)

    def _bind_scroll_to_children(self, widget):
        """Bind ricorsivo dello scroll a tutti i widget figli"""
        for child in widget.winfo_children():
            child.bind("<MouseWheel>", self.on_left_panel_scroll)
            self._bind_scroll_to_children(child)

    def on_right_panel_scroll(self, event):
        """Scroll del pannello destro con mouse wheel"""
        if event.delta != 0 and hasattr(self, 'right_canvas'):
            self.right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _bind_scroll_to_children_once_right(self, widget):
        """Bind ricorsivo scroll pannello destro (una sola volta)"""
        if self._scroll_bound_right:
            return
        self._scroll_bound_right = True
        self._bind_scroll_to_children_right(widget)

    def _bind_scroll_to_children_right(self, widget):
        """Bind ricorsivo scroll a figli del pannello destro"""
        for child in widget.winfo_children():
            child.bind("<MouseWheel>", self.on_right_panel_scroll)
            self._bind_scroll_to_children_right(child)

    def on_canvas_resize(self, event):
        """Gestisce il resize del canvas con debounce per evitare lag"""
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(50, self._do_canvas_resize)

    def _do_canvas_resize(self):
        """Esegue il resize effettivo dopo il debounce"""
        self._resize_job = None
        self._cached_canvas_size = (self.canvas.winfo_width(), self.canvas.winfo_height())
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

    def _on_hz_change(self, event=None):
        """Callback cambio Hz - aggiorna output_hz e riepilogo"""
        try:
            s = self.hz_combo.get()
            hz = int(s.replace(" Hz", "").strip())
            self.output_hz.set(hz)
            self.fps_var.set(min(hz, 60))
            self.update_export_summary()
        except (ValueError, tk.TclError):
            pass

    def _on_led_wall_change(self, event=None):
        """Callback cambio LED Wall - aggiorna led_wall_var, info e auto-imposta Hz da input_signal_hz"""
        try:
            name = self.led_wall_combo.get()
            for key in LED_WALL_KEYS:
                if LED_WALL_SPECS[key]["name"] == name:
                    self.led_wall_var.set(key)
                    spec = LED_WALL_SPECS[key]
                    info = f"{spec['receiving_card']} | {spec['gray_depth']}bit | {spec['scan_type']} | {spec['refresh_hz']}Hz"
                    self.led_info_label.config(text=info)
                    hz = spec.get("input_signal_hz")
                    if hz and hz in HZ_PRESETS:
                        self.output_hz.set(hz)
                        self.hz_combo.set(f"{hz} Hz")
                    self.update_export_summary()
                    return
            if name in self.custom_presets:
                self.led_wall_var.set(f"custom_{name}")
                data = self.custom_presets[name]
                hw = data.get("hardware", {})
                gs = data.get("grayscale_specs", {})
                info = f"{hw.get('receiving_card', '?')} | {gs.get('gray_depth_bits', '?')}bit | Custom"
                self.led_info_label.config(text=info)
                hz = data.get("input_signal_hz")
                if hz and hz in HZ_PRESETS:
                    self.output_hz.set(hz)
                    self.hz_combo.set(f"{hz} Hz")
            self.update_export_summary()
        except (KeyError, tk.TclError):
            pass

    def _on_software_change(self, event=None):
        """Callback cambio Software Target - aggiorna software_target_var"""
        try:
            sw_names = ["Resolume Arena (HAP Q)", "vMix (DNxHR)", "Millumin (HAP Q/ProRes)",
                        "Generico H.264", "Generico H.265"]
            sel = self.software_combo.get()
            idx = sw_names.index(sel) if sel in sw_names else 0
            key = SOFTWARE_KEYS[idx]
            self.software_target_var.set(key)
            profile = get_export_profile(self.led_wall_var.get(), key, self.output_hz.get(),
                                         custom_presets=self.custom_presets)
            v = profile["video"]
            codec = v.get("format_name") or v.get("codec", "")
            if v.get("profile"):
                codec = f"{codec} {v['profile']}"
            note = CODEC_COMPATIBILITY.get(key, "")
            txt = f"Codec: {codec} | {v.get('container', 'mov').upper()}"
            if note:
                txt += f"\n{note}"
            self.sw_info_label.config(text=txt)
            self.update_export_summary()
        except (KeyError, ValueError, tk.TclError):
            pass

    def update_export_summary(self):
        """Aggiorna il riepilogo export in base alle selezioni correnti"""
        try:
            profile = get_export_profile(
                self.led_wall_var.get(),
                self.software_target_var.get(),
                self.output_hz.get(),
                custom_presets=self.custom_presets
            )
            v, a, f = profile["video"], profile["audio"], profile["filters"]
            codec = v.get("format_name") or v.get("codec", "?")
            if v.get("profile"):
                codec = f"{codec} {v['profile']}"
            br = v.get("bitrate_1080p_mbps", 0)
            pf = v.get("pixel_format", "yuv420p")
            cs = v.get("color_space", "Rec.709")
            bd = v.get("bit_depth", 8)
            audio_str = f"PCM {a['bit_depth']}bit" if a["codec"].startswith("pcm") else f"AAC {a.get('bitrate_kbps', 0)}k"
            txt = f"Video: {codec} / {v.get('container', 'mov').upper()}\n"
            txt += f"Bitrate: {br} Mbps @ 1080p | FPS: {v.get('framerate', 30)}\n"
            txt += f"Bit: {bd}bit | Spazio colore: {cs} {pf.upper()}\n"
            txt += f"Audio: {audio_str} @ {a['sample_rate']}Hz\n"
            txt += f"Filtri: Deband({f['deband_threshold']}) | Sharp({f['sharpen_amount']})"
            self.summary_label.config(text=txt)
        except Exception as e:
            logger.warning(f"update_export_summary: {e}")
            self.summary_label.config(text="Riepilogo non disponibile")

    def _parse_rcfgx(self, filepath):
        """Parsa file RCFGX NovaStar (ZIP con XML) o RCFG (XML diretto)"""
        result = {"brand": "NovaStar", "receiving_card": "A5S Plus"}
        try:
            if str(filepath).lower().endswith(".rcfgx"):
                with zipfile.ZipFile(filepath, "r") as zf:
                    rcfg_files = [f for f in zf.namelist() if f.lower().endswith(".rcfg")]
                    if not rcfg_files:
                        raise ValueError("Nessun file .rcfg nell'archivio")
                    xml_content = zf.read(rcfg_files[0])
                    root = ET.fromstring(xml_content)
            else:
                tree = ET.parse(filepath)
                root = tree.getroot()
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                txt = (elem.text or "").strip()
                if not txt:
                    continue
                if tag == "ModuleWidth":
                    result["module_width"] = int(txt)
                elif tag == "ModuleHeight":
                    result["module_height"] = int(txt)
                elif tag == "DriverChipType":
                    result["driver_ic"] = txt
                elif tag == "GrayLevel":
                    result["gray_depth"] = int(txt)
                elif tag == "RefreshRate":
                    result["refresh_hz"] = int(txt)
                elif tag in ("ScanType", "ScanNum"):
                    try:
                        result["scan_ratio"] = int(txt)
                        result["scan_type"] = f"1/{txt}"
                    except ValueError:
                        result["scan_type"] = txt
                elif tag == "GammaValue":
                    try:
                        result["gamma"] = float(txt)
                    except ValueError:
                        pass
                elif tag == "PixelPitch":
                    try:
                        result["pixel_pitch_mm"] = float(txt)
                    except ValueError:
                        pass
            gray = result.get("gray_depth", 14)
            result["quality_tier"] = QUALITY_ENTRY if gray <= 13 else (QUALITY_BROADCAST if gray >= 16 else QUALITY_PROFESSIONAL)
            result["input_signal_hz"] = 50
            result["optimal_fps"] = [25, 30, 50, 60]
        except Exception as e:
            logger.warning(f"Parse RCFGX: {e}")
        return result

    def _parse_rcvbp_filename(self, filepath):
        """Estrae parametri dal nome file RCVBP Colorlight"""
        name = Path(filepath).stem.upper()
        result = {"brand": "Colorlight", "receiving_card": "i5A-F"}
        pitch_match = re.search(r"[PA](\d+\.?\d*)", name)
        if pitch_match:
            result["pixel_pitch_mm"] = float(pitch_match.group(1))
        scan_match = re.search(r"(\d+)S", name)
        if scan_match:
            result["scan_ratio"] = int(scan_match.group(1))
            result["scan_type"] = f"1/{scan_match.group(1)}"
        for ic in ["MBI5124", "MBI5153", "MBI5264", "ICN2153", "ICN2038", "ICN2053"]:
            if ic in name:
                result["driver_ic"] = ic
                break
        hz_match = re.search(r"(\d+)HZ", name)
        if hz_match:
            result["refresh_hz"] = int(hz_match.group(1))
        result["gray_depth"] = result.get("gray_depth", 14)
        result["quality_tier"] = QUALITY_PROFESSIONAL
        result["gamma"] = 2.2
        result["input_signal_hz"] = 50
        result["optimal_fps"] = [25, 30, 50, 60]
        return result

    def _parse_rcg_filename(self, filepath):
        """Estrae parametri dal nome file RCG Linsn (supporto base)"""
        name = Path(filepath).stem.upper()
        result = {"brand": "Linsn", "receiving_card": "Linsn"}
        pitch_match = re.search(r"[PA](\d+\.?\d*)", name)
        if pitch_match:
            result["pixel_pitch_mm"] = float(pitch_match.group(1))
        result["gray_depth"] = 14
        result["quality_tier"] = QUALITY_PROFESSIONAL
        result["scan_type"] = "1/16"
        result["gamma"] = 2.2
        result["refresh_hz"] = 1920
        result["input_signal_hz"] = 50
        result["optimal_fps"] = [25, 30, 50, 60]
        return result

    def _auto_configure_from_preset(self, data):
        """Auto-configura risoluzione e Hz dal preset/JSON importato"""
        if not data:
            return
        try:
            # Risoluzione: cerca output_resolution, resolution, total_width_px, width_px, physical_specs
            w, h = None, None
            if "output_resolution" in data:
                r = data["output_resolution"]
                if isinstance(r, (list, tuple)) and len(r) >= 2:
                    w, h = int(r[0]), int(r[1])
            elif "resolution" in data:
                r = data["resolution"]
                if isinstance(r, dict):
                    w = r.get("width") or r.get("output_width")
                    h = r.get("height") or r.get("output_height")
                    if w is not None and h is not None:
                        w, h = int(w), int(h)
            elif "total_width_px" in data and "total_height_px" in data:
                w, h = int(data["total_width_px"]), int(data["total_height_px"])
            else:
                ps = data.get("physical_specs", {})
                mw = ps.get("module_width_pixels") or ps.get("width_pixels")
                mh = ps.get("module_height_pixels") or ps.get("height_pixels")
                mc = ps.get("module_cols", 1)
                mr = ps.get("module_rows", 1)
                if mw is not None and mh is not None:
                    w = int(mw) * int(mc) if mc else int(mw)
                    h = int(mh) * int(mr) if mr else int(mh)
            if w and h and 64 <= w <= 8192 and 64 <= h <= 8192:
                self.output_width.set(w)
                self.output_height.set(h)
                self.preset_combo.set("Personalizzato")
                logger.info(f"Auto-config risoluzione: {w}x{h}")
            # Hz: input_signal_hz, timing_specs.refresh_hz (50/60), hardware
            hz = None
            if "input_signal_hz" in data:
                hz = int(data["input_signal_hz"])
            elif "timing_specs" in data:
                ts = data["timing_specs"]
                rhz = ts.get("refresh_hz") or ts.get("ref_num_per_vs")
                if rhz is not None:
                    rhz = int(rhz)
                    hz = 60 if rhz >= 55 else 50 if rhz >= 45 else 30
            if hz and hz in HZ_PRESETS:
                self.output_hz.set(hz)
                self.hz_combo.set(f"{hz} Hz")
                logger.info(f"Auto-config Hz: {hz}")
        except Exception as e:
            logger.warning(f"Auto-config preset: {e}")

    def _config_to_led_spec(self, parsed):
        """Converte dati parsati in preset custom con filtri auto-generati"""
        gray = parsed.get("gray_depth", 14)
        tier = QUALITY_ENTRY if gray <= 13 else (QUALITY_BROADCAST if gray >= 16 else QUALITY_PROFESSIONAL)
        base_filters = FILTER_PROFILES["novastar_a8_plus"]
        if tier == QUALITY_ENTRY:
            base_filters = FILTER_PROFILES["novastar_a5_plus"]
        elif tier == QUALITY_BROADCAST:
            base_filters = FILTER_PROFILES["novastar_a10_plus"]
        ps = {"pixel_pitch_mm": parsed.get("pixel_pitch_mm", 2.5)}
        if parsed.get("module_width") and parsed.get("module_height"):
            ps["module_width_pixels"] = parsed["module_width"]
            ps["module_height_pixels"] = parsed["module_height"]
            ps["module_cols"] = 1
            ps["module_rows"] = 1
        return {
            "led_wall_name": parsed.get("led_wall_name", "Importato"),
            "hardware": {"brand": parsed.get("brand", "?"), "receiving_card": parsed.get("receiving_card", "?")},
            "physical_specs": ps,
            "grayscale_specs": {"gray_depth_bits": gray, "scan_ratio": parsed.get("scan_type", "1/16")},
            "magic_upscale_filters": dict(base_filters),
            "input_signal_hz": parsed.get("input_signal_hz", 50),
        }

    def _get_presets_dir(self):
        """Restituisce la cartella preset utente (%LOCALAPPDATA%/R-Converter/presets)"""
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        presets_dir = Path(appdata) / 'R-Converter' / 'presets'
        try:
            presets_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return presets_dir

    def _load_presets_from_appdata(self):
        """Carica preset JSON dalla cartella %LOCALAPPDATA%/R-Converter/presets/"""
        presets_dir = self._get_presets_dir()
        if not presets_dir.exists():
            return
        for p in presets_dir.glob("*.json"):
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("Preset non valido")
                name = data.get("led_wall_name", p.stem) or p.stem
                if "magic_upscale_filters" not in data:
                    data["magic_upscale_filters"] = dict(FILTER_PROFILES["novastar_a8_plus"])
                if "grayscale_specs" not in data:
                    data["grayscale_specs"] = {"gray_depth_bits": 14, "scan_ratio": "1/16"}
                self.custom_presets[name] = data
                led_names = list(self.led_wall_combo["values"])
                if name not in led_names:
                    led_names.append(name)
                    self.led_wall_combo["values"] = led_names
                logger.info(f"Preset caricato: {name}")
            except Exception as e:
                logger.warning(f"Preset {p.name} non caricato: {e}")

    def _import_led_config(self):
        """Importa preset da file JSON o config LED (RCFGX, RCVBP, RCG)"""
        path = filedialog.askopenfilename(
            title="Importa configurazione LED",
            filetypes=[
                ("File configurazione LED", "*.json *.rcfgx *.rcfg *.rcvbp *.rcg"),
                ("NovaStar RCFGX/RCFG", "*.rcfgx *.rcfg"),
                ("Colorlight RCVBP", "*.rcvbp"),
                ("Linsn RCG", "*.rcg"),
                ("Preset JSON", "*.json"),
                ("Tutti", "*.*"),
            ]
        )
        if not path:
            return
        try:
            path_lower = path.lower()
            if path_lower.endswith(".json"):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("led_wall_name", Path(path).stem)
            elif path_lower.endswith((".rcfgx", ".rcfg")):
                parsed = self._parse_rcfgx(path)
                parsed["led_wall_name"] = f"Importato: {Path(path).stem}"
                data = self._config_to_led_spec(parsed)
                name = data["led_wall_name"]
                self._auto_configure_from_preset(data)
                messagebox.showinfo("Import", f"Config NovaStar importata.\nVerifica i parametri estratti.")
            elif path_lower.endswith(".rcvbp"):
                parsed = self._parse_rcvbp_filename(path)
                parsed["led_wall_name"] = f"Importato: {Path(path).stem}"
                data = self._config_to_led_spec(parsed)
                name = data["led_wall_name"]
                self._auto_configure_from_preset(data)
                messagebox.showinfo("Import", f"Config Colorlight importata.\nParametri estratti dal nome file.")
            elif path_lower.endswith(".rcg"):
                parsed = self._parse_rcg_filename(path)
                parsed["led_wall_name"] = f"Importato: {Path(path).stem}"
                data = self._config_to_led_spec(parsed)
                name = data["led_wall_name"]
                self._auto_configure_from_preset(data)
                messagebox.showinfo("Import", "File Linsn RCG importato.\nVerifica i parametri estratti.")
            else:
                messagebox.showwarning("Formato", "Formato file non supportato.")
                return
            self.custom_presets[name] = data
            led_names = list(self.led_wall_combo["values"])
            if name not in led_names:
                led_names.append(name)
                self.led_wall_combo["values"] = led_names
            self.led_wall_combo.set(name)
            self.led_wall_var.set(f"custom_{name}")
            self.led_info_label.config(text=f"Importato: {name}")
            self._auto_configure_from_preset(data)
            self.update_export_summary()
            logger.info(f"Preset importato: {name}")
        except Exception as e:
            logger.error(f"Import preset: {e}")
            messagebox.showerror("Errore", f"Impossibile importare:\n{e}")

    def _save_custom_preset(self):
        """Salva il preset corrente come JSON (in preset folder o percorso scelto)"""
        key = self.led_wall_var.get()
        name = self.led_wall_combo.get()
        data = None
        if key in LED_WALL_KEYS:
            spec = LED_WALL_SPECS[key]
            filters = FILTER_PROFILES[key]
            data = {
                "led_wall_name": spec["name"],
                "hardware": {"brand": spec["brand"], "receiving_card": spec["receiving_card"]},
                "physical_specs": {"pixel_pitch_mm": spec["pixel_pitch_mm"]},
                "grayscale_specs": {"gray_depth_bits": spec["gray_depth"], "scan_ratio": spec["scan_type"]},
                "magic_upscale_filters": dict(filters),
            }
        elif name in self.custom_presets:
            data = self.custom_presets[name]
        if not data:
            messagebox.showinfo("Info", "Seleziona un preset built-in da modificare,\no importa un JSON da salvare.")
            return
        presets_dir = self._get_presets_dir()
        default_name = f"{data.get('led_wall_name', name)}.json".replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Salva preset",
            defaultextension=".json",
            initialdir=str(presets_dir) if presets_dir.exists() else None,
            initialfile=default_name,
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Preset salvato: {path}")
            messagebox.showinfo("Successo", f"Preset salvato:\n{path}")
        except Exception as e:
            logger.error(f"Salva preset: {e}")
            messagebox.showerror("Errore", str(e))

    def export_project(self):
        """Export composito - placeholder, usa export_image per ora"""
        if not self.layers:
            messagebox.showwarning("Avviso", "Aggiungi almeno un elemento al progetto")
            return
        has_video = any(getattr(l, "is_video", False) for l in self.layers)
        if has_video:
            video_layers = [l for l in self.layers if getattr(l, "is_video", False)]
            self.export_video()
        else:
            self.export_image()

    def set_bg_color(self, color):
        self.bg_color_var.set(color)
        self.redraw_canvas()

    def choose_custom_color(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="Scegli colore sfondo")
        if color[1]:
            self.set_bg_color(color[1])

    def set_video_export_enabled(self, enabled):
        """Compatibilità - PRO: abilita export se ci sono layer"""
        self._update_export_btn_state()

    def set_image_export_enabled(self, enabled):
        """Compatibilità - PRO: abilita export se ci sono layer"""
        self._update_export_btn_state()

    def _update_export_btn_state(self):
        """Abilita/disabilita pulsante Export Composito in base ai layer"""
        try:
            state = 'normal' if self.layers else 'disabled'
            self.export_pro_btn.config(state=state)
        except (AttributeError, tk.TclError):
            pass

    def _set_widget_state(self, widget, state):
        """Imposta ricorsivamente lo stato di un widget e i suoi figli"""
        try:
            widget.config(state=state)
        except tk.TclError:
            pass  # Widget non supporta state
        except Exception as ex:
            logger.debug(f"set_widget_state: {ex}")
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
        """Rimuove tutti i layer e libera risorse"""
        if self.layers:
            if messagebox.askyesno("Conferma", "Rimuovere tutti gli elementi?"):
                for layer in self.layers:
                    layer.cleanup()
                self.layers.clear()
                self.selected_layer = None
                self.update_layers_list()
                self.update_export_panels()
                self.file_label.config(text="📁 Aggiungi immagini per creare un collage")
                self.redraw_canvas()

    # ==================== EXPORT ====================

    def export_image(self):
        """Esporta come immagine (formato e qualità dal profilo LED wall + software)"""
        if not self.layers:
            messagebox.showwarning("Avviso", "Aggiungi almeno un'immagine")
            return

        profile = get_export_profile(
            self.led_wall_var.get(), self.software_target_var.get(), self.output_hz.get(),
            custom_presets=self.custom_presets
        )
        fmt = profile.get("image_format", "png")
        ext = f".{fmt}"

        filepath = filedialog.asksaveasfilename(
            title="Salva collage",
            defaultextension=ext,
            initialfile=f"collage{ext}",
            filetypes=[(fmt.upper(), f"*{ext}"), ("PNG", "*.png"), ("JPEG", "*.jpg"), ("Tutti", "*.*")]
        )

        if not filepath:
            return
        out_dir = Path(filepath).parent
        if not out_dir.exists():
            messagebox.showerror("Errore", f"Cartella di destinazione non esiste:\n{out_dir}")
            return

        self.progress.start()
        thread = threading.Thread(target=self._do_export_image, args=(filepath,), daemon=True)
        thread.start()

    def export_video(self):
        """Esporta come video"""
        if not VIDEO_SUPPORT:
            messagebox.showerror("Errore", "OpenCV non installato. Installa con: pip install opencv-python")
            return
        if not self.ffmpeg_path:
            messagebox.showwarning("FFmpeg non trovato",
                "FFmpeg non è nel PATH. L'export userà OpenCV (più lento).\n"
                "Per export veloce: installa FFmpeg e aggiungilo al PATH.")

        # Trova video nei layer
        video_layers = [layer for layer in self.layers if hasattr(layer, 'is_video') and layer.is_video]
        if not video_layers:
            messagebox.showwarning("Avviso", "Nessun video caricato. Per esportare video carica almeno un file video.")
            return

        profile = get_export_profile(
            self.led_wall_var.get(), self.software_target_var.get(), self.output_hz.get(),
            custom_presets=self.custom_presets
        )
        container = profile["video"].get("container", "mp4")
        ext = ".mov" if container == "mov" else ".mp4"
        fmt = "MOV" if container == "mov" else "MP4"

        filepath = filedialog.asksaveasfilename(
            title="Salva video",
            defaultextension=ext,
            initialfile=f"video_output{ext}",
            filetypes=[(fmt, f"*{ext}"), ("Tutti", "*.*")]
        )

        if not filepath:
            return
        out_dir = Path(filepath).parent
        if not out_dir.exists():
            messagebox.showerror("Errore", f"Cartella di destinazione non esiste:\n{out_dir}")
            return

        self.progress.start()
        layers_snapshot = list(self.layers)
        thread = threading.Thread(target=self._do_export_video, args=(filepath, layers_snapshot), daemon=True)
        thread.start()

    def _build_ffmpeg_video_command(self, filepath, output_w, output_h, fps, profile, ext):
        """Costruisce comando FFmpeg per export video broadcast.
        HAP: -an (no audio). ProRes: -vendor apl0 solo per Millumin. DNxHR: profilo, no bitrate.
        """
        if not self.ffmpeg_path:
            return None
        v = profile["video"]
        software = profile.get("software_target", "resolume")
        cmd = [self.ffmpeg_path, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{output_w}x{output_h}", "-r", str(fps), "-i", "pipe:0"]
        codec = v.get("codec", "libx264")
        pf = v.get("pixel_format", "yuv420p")
        container = v.get("container", "mp4")
        if codec == "hap" or v.get("format_name") in ("hap", "hap_q"):
            fmt_hap = v.get("format_name", "hap")
            cmd.extend(["-c:v", "hap", "-format", fmt_hap, "-an"])
        elif codec == "dnxhd":
            cmd.extend(["-c:v", "dnxhd", "-profile:v", v.get("profile", "dnxhr_hq")])
            if software != "vmix":
                cmd.append("-an")
            else:
                cmd.extend(["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"])
        elif "prores" in codec:
            cmd.extend(["-c:v", "prores_ks", "-profile:v", v.get("profile", "2"),
                        "-pix_fmt", "yuv422p10le"])
            if software == "millumin":
                cmd.extend(["-vendor", "apl0"])
            cmd.extend(["-c:a", "pcm_s24le", "-ar", "48000", "-ac", "2"])
        elif codec == "libx265":
            denom = max(1920 * 1080, 1)
            br = int(v.get("bitrate_1080p_mbps", 140) * (output_w * output_h) / denom)
            cmd.extend(["-c:v", "libx265", "-preset", v.get("preset", "medium"),
                        "-x265-params", f"vbv-maxrate={br}:vbv-bufsize={br}"])
            cmd.extend(["-c:a", "aac", "-b:a", "320k", "-ar", "48000"])
        else:
            denom = max(1920 * 1080, 1)
            br = int(v.get("bitrate_1080p_mbps", 200) * (output_w * output_h) / denom) * 1000
            cmd.extend(["-c:v", "libx264", "-preset", v.get("preset", "fast"),
                        "-profile:v", "high", "-b:v", f"{br}", "-maxrate", f"{br}", "-bufsize", f"{br*2}"])
            cmd.extend(["-c:a", "aac", "-b:a", "320k", "-ar", "48000"])
        if ext == ".mov" or container == "mov":
            cmd.extend(["-f", "mov"])
        cmd.append(filepath)
        return cmd

    def _do_export_image(self, filepath):
        try:
            # Snapshot completo contesto (thread-safety, lettura una sola volta)
            output_w = self.output_width.get()
            output_h = self.output_height.get()
            proc_int = self.proc_intensity.get() / 100.0
            led_key = self.led_wall_var.get()
            sw_key = self.software_target_var.get()
            hz_val = self.output_hz.get()
            custom = self.custom_presets

            profile = get_export_profile(led_key, sw_key, hz_val, custom_presets=custom)
            quality = profile.get("image_quality_pct", 95)
            bit_depth = profile.get("image_bit_depth", 16)
            dpi = profile.get("image_dpi", 150)
            compress = profile.get("image_compression", 3)
            filters = profile.get("filters", {})

            if not (64 <= output_w <= 8192 and 64 <= output_h <= 8192):
                raise ValueError(f"Risoluzione non valida: {output_w}x{output_h}")

            logger.info(f"Export immagine: {output_w}x{output_h} -> {filepath} (profilo: {quality}%, {bit_depth}bit)")

            # Composito + processing broadcast (filtri dal preset LED wall)
            img = self.create_composite_image(output_w, output_h, for_export=True)
            img = self._apply_image_processing(img, filters, intensity=proc_int)
            ext = Path(filepath).suffix.lower()

            if ext in ['.jpg', '.jpeg']:
                img.convert('RGB').save(filepath, 'JPEG', quality=quality, optimize=True,
                                        dpi=(dpi, dpi))
            elif ext == '.png':
                if bit_depth >= 16:
                    if img.mode == 'RGB':
                        img = img.convert('RGBA')
                    elif img.mode not in ('RGBA', 'LA'):
                        img = img.convert('RGBA')
                img.info['dpi'] = (dpi, dpi)
                img.save(filepath, 'PNG', optimize=True, compress_level=min(9, max(0, compress)))
            elif ext == '.webp':
                img.save(filepath, 'WEBP', quality=quality)
            else:
                img.save(filepath)

            file_size = Path(filepath).stat().st_size
            size_str = f"{file_size / 1024:.1f} KB" if file_size < 1048576 else f"{file_size / 1048576:.2f} MB"
            logger.info(f"Export completato: {size_str} | {output_w}x{output_h} | {bit_depth}bit | {dpi}dpi | {ext}")
            del img
            gc.collect()

            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: messagebox.showinfo("Successo", f"Collage salvato:\n{filepath}"))
        except Exception as ex:
            logger.error(f"Errore export immagine: {ex}")
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda err=str(ex): messagebox.showerror("Errore", err))

    def _do_export_video(self, filepath, all_layers):
        """Esporta video composito di TUTTI i layer (immagini + video)"""
        caps = {}
        out = None
        try:
            # Snapshot contesto (thread-safety, lettura una sola volta)
            output_w = self.output_width.get()
            output_h = self.output_height.get()
            fps = max(1, self.fps_var.get())
            ext = Path(filepath).suffix.lower()
            led_key = self.led_wall_var.get()
            sw_key = self.software_target_var.get()
            hz_val = self.output_hz.get()
            profile = get_export_profile(led_key, sw_key, hz_val, custom_presets=self.custom_presets)

            video_layers = [l for l in all_layers if getattr(l, 'is_video', False) and l.is_video]
            if not video_layers:
                raise Exception("Nessun layer video nel progetto")

            try:
                for layer in video_layers:
                    vpath = getattr(layer, 'video_path', None)
                    if not vpath or not os.path.isfile(vpath):
                        raise Exception(f"File video non valido: {vpath}")
                    cap = cv2.VideoCapture(vpath)
                    if not cap.isOpened():
                        cap.release()
                        raise Exception(f"Impossibile aprire video: {vpath}")
                    caps[layer] = cap
            except Exception:
                for cap in caps.values():
                    cap.release()
                caps.clear()
                raise

            total_frames = max((int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) for cap in caps.values()), default=0)
            total_frames = min(max(1, total_frames), 3000)  # Limite GIF, evita div-by-zero in progress
            last_frame = {}  # Ultimo frame per video più corti

            logger.info(f"Export composito: {output_w}x{output_h} @ {fps}fps, {len(all_layers)} layer -> {filepath}")

            def make_composite_frame(video_frame_overrides):
                """Crea il composito di tutti i layer con override per i video"""
                return self.create_composite_image(output_w, output_h, for_export=True,
                                                   video_frame_overrides=video_frame_overrides, layers=all_layers)

            if ext == '.gif':
                frames = []
                frame_count = 0
                GIF_MAX_FRAMES = 3000

                while frame_count < min(GIF_MAX_FRAMES, total_frames):
                    video_frame_overrides = {}
                    for layer, cap in caps.items():
                        ret, frame = cap.read()
                        if ret:
                            pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                            video_frame_overrides[layer] = pil_frame
                            last_frame[layer] = pil_frame
                        elif layer in last_frame:
                            video_frame_overrides[layer] = last_frame[layer]

                    composite = make_composite_frame(video_frame_overrides)
                    frames.append(composite.quantize(colors=256, method=Image.Quantize.MEDIANCUT))
                    del composite
                    frame_count += 1

                    if frame_count % 10 == 0:
                        progress_pct = int((frame_count / max(total_frames, 1)) * 100)
                        self.root.after(0, lambda p=progress_pct:
                                       self.info_label.config(text=f"Esportazione GIF: {p}%"))

                for cap in caps.values():
                    cap.release()
                caps.clear()

                if frames:
                    frames[0].save(filepath, save_all=True, append_images=frames[1:],
                                   duration=int(1000 / max(fps, 1)), loop=0, optimize=True)
                    del frames
                    gc.collect()

                logger.info(f"GIF esportata: {frame_count} frames (composito completo)")
                self.root.after(0, lambda: self.progress.stop())
                self.root.after(0, lambda: self.info_label.config(text=""))
                self.root.after(0, lambda: messagebox.showinfo("Successo", f"GIF salvata:\n{filepath}\n{frame_count} frames"))
                return

            # MP4/AVI/WEBM: usa FFmpeg se disponibile (10-50x più veloce), altrimenti OpenCV
            ff_cmd = self._build_ffmpeg_video_command(filepath, output_w, output_h, fps, profile, ext)
            if ff_cmd and ext != '.gif':
                # Export via FFmpeg pipe con double-buffering (pre-fetch frame)
                try:
                    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0
                    proc = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                                            creationflags=creationflags)
                    frame_queue = Queue(maxsize=4)

                    def frame_reader():
                        """Producer: legge frame in anticipo e li mette in coda"""
                        try:
                            lf = {}
                            for _ in range(total_frames):
                                overrides = {}
                                for layer, cap in caps.items():
                                    ret, frame = cap.read()
                                    if ret:
                                        pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                                        overrides[layer] = pil_frame
                                        lf[layer] = pil_frame
                                    elif layer in lf:
                                        overrides[layer] = lf[layer]
                                frame_queue.put(overrides)
                            frame_queue.put(None)
                        except Exception as e:
                            logger.warning(f"Frame reader: {e}")
                            frame_queue.put(None)

                    threading.Thread(target=frame_reader, daemon=True).start()
                    frame_count = 0
                    while True:
                        overrides = frame_queue.get()
                        if overrides is None:
                            break
                        composite = make_composite_frame(overrides)
                        proc.stdin.write(composite.tobytes())
                        del composite
                        frame_count += 1
                        if frame_count % 30 == 0:
                            pct = int((frame_count / max(total_frames, 1)) * 100)
                            self.root.after(0, lambda p=pct: self.info_label.config(text=f"FFmpeg: {p}%"))
                    proc.stdin.close()
                    proc.wait(timeout=120)
                    if proc.returncode != 0:
                        err = proc.stderr.read().decode(errors='replace')[-500:]
                        raise Exception(f"FFmpeg errore: {err}")
                    for cap in caps.values():
                        cap.release()
                    caps.clear()
                    logger.info(f"Video FFmpeg: {frame_count} frames")
                    gc.collect()
                    self.root.after(0, lambda: self.progress.stop())
                    self.root.after(0, lambda: self.info_label.config(text=""))
                    self.root.after(0, lambda: messagebox.showinfo("Successo", f"Video salvato:\n{filepath}\n{frame_count} frames"))
                    return
                except Exception as ff_ex:
                    logger.warning(f"FFmpeg fallback a OpenCV: {ff_ex}")
                    for cap in caps.values():
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    # Ricrea caps se necessario (alcuni non supportano seek)
                    for layer in list(caps.keys()):
                        caps[layer].release()
                    caps.clear()
                    for layer in video_layers:
                        cap = cv2.VideoCapture(layer.video_path)
                        if cap.isOpened():
                            caps[layer] = cap

            # Fallback OpenCV
            fourcc = cv2.VideoWriter_fourcc(*'mp4v') if ext == '.mp4' else \
                     cv2.VideoWriter_fourcc(*'XVID') if ext == '.avi' else \
                     cv2.VideoWriter_fourcc(*'VP80') if ext == '.webm' else \
                     cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(filepath, fourcc, fps, (output_w, output_h))
            if not out.isOpened():
                raise Exception("Impossibile creare il file video di output")

            frame_count = 0
            while frame_count < total_frames:
                video_frame_overrides = {}
                for layer, cap in caps.items():
                    ret, frame = cap.read()
                    if ret:
                        pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        video_frame_overrides[layer] = pil_frame
                        last_frame[layer] = pil_frame
                    elif layer in last_frame:
                        video_frame_overrides[layer] = last_frame[layer]

                composite = make_composite_frame(video_frame_overrides)
                output_frame = cv2.cvtColor(np.array(composite), cv2.COLOR_RGB2BGR)
                out.write(output_frame)
                del composite
                frame_count += 1

                if frame_count % 30 == 0:
                    progress_pct = int((frame_count / max(total_frames, 1)) * 100)
                    self.root.after(0, lambda p=progress_pct:
                                   self.info_label.config(text=f"Esportazione video: {p}%"))

            logger.info(f"Video esportato: {frame_count} frames (composito completo)")
            gc.collect()
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.info_label.config(text=""))
            self.root.after(0, lambda: messagebox.showinfo("Successo", f"Video salvato:\n{filepath}\n{frame_count} frames"))

        except Exception as ex:
            logger.error(f"Errore export video: {ex}")
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.info_label.config(text=""))
            self.root.after(0, lambda err=str(ex): messagebox.showerror("Errore", err))
        finally:
            for cap in caps.values():
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
    app = RConverter(root)
    argv_files = []
    if len(sys.argv) > 1 and getattr(sys, 'frozen', False):
        argv_files = [f for f in sys.argv[1:] if os.path.isfile(f)]
    if argv_files:
        root.after(1500, lambda: app._process_dropped_files(argv_files))

    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
