# 🖼️ R-Converter

**Convertitore di Immagini e Video con supporto Multi-Layer Collage**

> Versione 1.2.0 | Python 3.8+ | Windows 10/11

---

## 📋 Indice

- [Caratteristiche](#-caratteristiche)
- [Architettura](#-architettura)
- [Installazione](#-installazione)
- [Avvio](#-avvio)
- [Guida all'uso](#-guida-alluso)
- [Struttura del Codice](#-struttura-del-codice)
- [API e Classi Principali](#-api-e-classi-principali)
- [Performance e Ottimizzazioni](#-performance-e-ottimizzazioni)
- [Build e Distribuzione](#-build-e-distribuzione)
- [Risoluzione Problemi](#-risoluzione-problemi)
- [Contributi](#-contributi)

---

## ✨ Caratteristiche

### Core
- 🎨 **Multi-Layer Collage** - Crea composizioni con più immagini sovrapposte
- 🖱️ **Drag & Drop** - Trascina file direttamente nella finestra (supporto windnd)
- ⬚ **Handle di Selezione** - Ridimensiona e ruota con handle visivi stile PowerPoint
- 🔍 **Zoom 1-1000%** - Scroll delicato (1% per tick) per controllo preciso
- 🔄 **Trasformazioni Complete** - Rotazione 0-360°, specchio H/V, posizionamento pixel-perfect
- 📐 **Adattamento Automatico** - 4 modalità: Adatta, Riempi, Riempi H, Riempi V
- 🔒 **Blocco Proporzioni** - Toggle per mantenere aspect ratio durante ridimensionamento

### Esportazione
- 💾 **Multi-formato Immagine** - JPG, PNG, WebP, BMP, GIF, TIFF
- 🎬 **Multi-formato Video** - MP4, AVI, WebM, GIF animata
- ⭐ **Preset Qualità** - Bassa/Media/Alta con DPI e bitrate ottimizzati
- 🎨 **Sfondo Personalizzabile** - Colori preset + color picker

### UI/UX
- 🌙 **Tema Tech/Cyber** - Interfaccia moderna blu scuro
- 📱 **Fullscreen all'avvio** - Massimizza spazio di lavoro
- 🎛️ **Pannello Scrollabile** - Tutti i controlli accessibili con scroll
- 📊 **Sezioni Colorate** - Differenziazione visiva: Layers (blu), Transform (cyan), Size (teal), Fit (viola), Mirror (arancio)

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                        RConverter                            │
│  (Classe principale - gestisce UI, eventi, logica)          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ ImageLayer  │  │ ImageLayer  │  │ ImageLayer (video)  │  │
│  │ __slots__   │  │ __slots__   │  │ __slots__           │  │
│  │ + cache     │  │ + cache     │  │ + video_path        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Canvas Preview (Tkinter)  │  Threading Export              │
│  Debounce 60fps            │  Progress Feedback             │
└─────────────────────────────────────────────────────────────┘
```

### Dipendenze

| Libreria | Versione | Scopo |
|----------|----------|-------|
| Pillow | ≥9.0 | Elaborazione immagini |
| opencv-python | ≥4.0 | Elaborazione video (opzionale) |
| numpy | ≥1.20 | Array processing per video |
| windnd | ≥1.0 | Drag & drop Windows |
| pyinstaller | ≥5.0 | Build eseguibile (dev) |

---

## 📦 Installazione

### Requisiti Sistema
- **OS**: Windows 10/11 (testato)
- **Python**: 3.8 o superiore
- **RAM**: 4GB minimo, 8GB consigliato per video
- **Disco**: ~100MB per installazione completa

### Da Sorgente

```bash
# Clona o scarica il progetto
cd R-Converter

# Installa dipendenze
pip install -r requirements.txt

# Oppure manualmente:
pip install Pillow opencv-python numpy windnd
```

### Versione Portable
Scarica `R-Converter.exe` dalla release - nessuna installazione richiesta!

---

## 🚀 Avvio

### Sviluppo
```bash
python main.py
```

### Portable
Doppio click su `R-Converter.exe`

### Argomenti CLI (futuro)
```bash
# Pianificato per v2.0
python main.py --input image.jpg --output banner.png --preset "1500x500"
```

---

## 📖 Guida all'uso

### Workflow Base

1. **Carica file** → `⊕ Aggiungi File` o `Ctrl+O` o Drag & Drop
2. **Imposta canvas** → Preset o dimensioni personalizzate
3. **Trasforma layer** → Zoom, rotazione, posizione, flip
4. **Esporta** → `📤 ESPORTA` o `Ctrl+S`

### Controlli Layer

| Azione | Mouse | Tastiera | Slider |
|--------|-------|----------|--------|
| Seleziona | Click su immagine | Click lista | - |
| Sposta | Drag centrale | - | Offset X/Y |
| Zoom | Scroll wheel | - | Zoom % |
| Ruota | Drag handle rotazione | - | Rotazione ° |
| Elimina | - | Canc/Delete | Pulsante 🗑️ |

### Preset Qualità

#### Immagini
| Preset | DPI | Bit Depth | Uso |
|--------|-----|-----------|-----|
| Bassa | 72 | 8-bit | Web, preview |
| Media | 150 | 16-bit | Stampa casalinga |
| Alta | 300 | 24-bit | Stampa professionale |

#### Video
| Preset | Bitrate | CRF | Uso |
|--------|---------|-----|-----|
| Bassa | 2000 kbps | 28 | Web, file piccoli |
| Media | 5000 kbps | 23 | Qualità bilanciata |
| Alta | 8000 kbps | 18 | Massima qualità |

### Scorciatoie

| Tasto | Azione |
|-------|--------|
| `Ctrl+O` | Apri file |
| `Ctrl+S` | Esporta |
| `Canc` | Elimina layer |
| `Esc` | Deseleziona |
| `Scroll` | Zoom ±1% |
| `Drag` | Sposta layer |

---

## 🧩 Struttura del Codice

```
R-Converter/
├── main.py              # Applicazione principale (~2070 righe)
├── build_exe.py         # Script build PyInstaller
├── requirements.txt     # Dipendenze Python
├── README.md            # Questa documentazione
├── icon.ico             # Icona applicazione (opzionale)
└── dist/                # Output build
    └── R-Converter.exe  # Eseguibile portable
```

### Organizzazione main.py

```python
# Linee 1-50:     Import, costanti, preset
# Linee 51-115:   Classe ImageLayer (data model)
# Linee 116-800:  RConverter.__init__, setup_style, create_widgets
# Linee 800-1070: Gestione layer, controlli UI
# Linee 1070-1300: Trasformazioni (fit, zoom, rotation, flip)
# Linee 1300-1550: Rendering canvas, composite image
# Linee 1550-1750: Mouse handlers, scroll, output settings
# Linee 1750-2070: Export image/video, processing ottimizzato
```

---

## 🔌 API e Classi Principali

### ImageLayer

```python
class ImageLayer:
    """Rappresenta un elemento nel collage"""
    __slots__ = ['id', 'original_image', 'name', 'offset_x', 'offset_y', 
                 'zoom', 'rotation', 'flip_h', 'flip_v', 'is_video', 
                 'video_path', 'video_fps', 'video_frames', 
                 'bounds_in_canvas', '_cache', '_cache_key']
    
    def get_transformed_image(self, use_cache=True) -> Image
    def invalidate_cache() -> None
    def cleanup() -> None  # Libera risorse
    def get_display_name() -> str
```

### RConverter (metodi chiave)

```python
class RConverter:
    # Inizializzazione
    def __init__(self, root: tk.Tk)
    def setup_style() -> None
    def create_widgets() -> None
    def setup_bindings() -> None
    def setup_drag_and_drop() -> None
    
    # Layer management
    def add_layer(path: str) -> None
    def remove_selected_layer() -> None
    def duplicate_layer() -> None
    def select_layer_at(x: int, y: int) -> bool
    
    # Trasformazioni
    def fit_keep_aspect() -> None      # Adatta
    def fit_contain() -> None          # Riempi
    def fit_fill_horizontal() -> None  # Riempi H
    def fit_fill_vertical() -> None    # Riempi V
    
    # Rendering
    def redraw_canvas() -> None  # Schedula con debounce
    def _do_redraw() -> None     # Esegue rendering
    def create_composite_image(w, h, for_export=False) -> Image
    
    # Export
    def export_image() -> None   # Thread wrapper
    def export_video() -> None   # Thread wrapper
    def _do_export_image(path) -> None  # Worker thread
    def _do_export_video(path, layer) -> None  # Worker thread
```

---

## ⚡ Performance e Ottimizzazioni

### Implementate

| Ottimizzazione | Descrizione | Impatto |
|----------------|-------------|---------|
| `__slots__` | Memoria layer ridotta ~40% | RAM |
| Cache trasformazioni | Evita ricalcolo flip/rotation | CPU |
| Debounce 60fps | Max 16ms tra redraw | UI fluida |
| NEAREST durante drag | Resize veloce mentre trascini | Responsività |
| BILINEAR statico | Qualità buona per preview | Bilanciamento |
| LANCZOS export | Massima qualità in output | Qualità |
| Pre-calc video | Parametri calcolati una volta per export | Export speed |
| Quantize GIF | Palette 256 colori per memoria | RAM GIF |
| Threading export | UI non bloccante durante export | UX |
| Cleanup layer | Libera memoria quando rimosso | Memory leak prevention |

### Gestione Eccezioni

```python
# Pattern utilizzato
try:
    widget.config(state=state)
except tk.TclError:
    pass  # Widget non supporta state
except Exception:
    pass  # Fallback generico

# Divisione per zero protetta
if orig_w == 0 or orig_h == 0:
    return
```

---

## 📦 Build e Distribuzione

### Build Portable (Singolo File)

```bash
# Installa PyInstaller
pip install pyinstaller

# Build con script
python build_exe.py

# Oppure manualmente:
pyinstaller --onefile --windowed --name="R-Converter" main.py
```

Output: `dist/R-Converter.exe` (~65MB)

### Build Folder (Più Veloce all'Avvio)

```bash
pyinstaller --onedir --windowed --name="R-Converter" main.py
```

Output: `dist/R-Converter/` (cartella distribuibile)

### Opzioni PyInstaller Consigliate

```bash
pyinstaller \
  --onefile \
  --windowed \
  --name="R-Converter" \
  --icon=icon.ico \
  --add-data="icon.ico;." \
  --hidden-import=PIL \
  --hidden-import=cv2 \
  main.py
```

---

## 🔧 Risoluzione Problemi

### Errori Comuni

| Errore | Causa | Soluzione |
|--------|-------|-----------|
| "OpenCV non installato" | cv2 mancante | `pip install opencv-python` |
| "windnd not found" | Drag&drop non funziona | `pip install windnd` |
| Video non si carica | Codec mancante | Installa K-Lite Codec Pack |
| Export lento | File grande | Usa preset qualità inferiore |
| Crash su immagini grandi | RAM insufficiente | Riduci risoluzione sorgente |

### Debug Mode

```python
# In main.py, aggiungi all'inizio:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Sintassi

```bash
python -m py_compile main.py
```

### Lint Check

```bash
pip install flake8
flake8 main.py --max-line-length=120
```

---

## 🧪 Testing

### Smoke Test
```bash
# Verifica avvio senza errori
python -c "import main; print('OK')"

# Verifica dipendenze
python -c "from PIL import Image; import cv2; import numpy; import windnd; print('Deps OK')"
```

### Test Funzionale
1. Avvia applicazione
2. Carica immagine JPG
3. Applica zoom 50%
4. Ruota 45°
5. Esporta come PNG
6. Verifica output

---

## 🤝 Contributi

### Guidelines

1. Fork del repository
2. Crea branch feature: `git checkout -b feature/nome`
3. Commit con messaggi chiari
4. Test funzionale completo
5. Pull request con descrizione

### Code Style

- **Indentazione**: 4 spazi
- **Line length**: max 120 caratteri
- **Docstrings**: per funzioni pubbliche
- **Naming**: snake_case per funzioni, CamelCase per classi
- **Commenti**: in italiano per UI, inglese per logica

---

## 📝 Changelog

### v1.2.0 (2026-02-04)
- ✨ Zoom 1-1000% con scroll 1% per tick
- ✨ Pulsanti adattamento (Adatta, Riempi, Riempi H, Riempi V)
- ✨ Toggle blocco proporzioni
- ✨ Pannello sinistro scrollabile
- ✨ Sezioni con colori differenziati
- 🐛 Fix gestione eccezioni
- 🐛 Fix divisione per zero
- ⚡ Cleanup memoria layer rimossi

### v1.1.0
- ✨ Preset qualità immagine/video
- ✨ Campi dimensione pixel con aspect ratio lock
- ✨ Fullscreen all'avvio

### v1.0.0
- 🎉 Release iniziale
- Multi-layer collage
- Export immagine/video
- Drag & drop

---

## 📄 Licenza

MIT License - Libero per uso personale e commerciale.

---

**Creato con ❤️ per semplificare la conversione di immagini e video**
