# R-Converter

**Convertitore di Immagini e Video con supporto Multi-Layer Collage**

> Versione 1.3.1 | Python 3.8+ | Windows 10/11

---

## Indice

- [Caratteristiche](#caratteristiche)
- [Architettura](#architettura)
- [Installazione](#installazione)
- [Avvio](#avvio)
- [Guida all'uso](#guida-alluso)
- [Struttura del Codice](#struttura-del-codice)
- [API e Classi Principali](#api-e-classi-principali)
- [Performance e Ottimizzazioni](#performance-e-ottimizzazioni)
- [Build e Distribuzione](#build-e-distribuzione)
- [Risoluzione Problemi](#risoluzione-problemi)
- [Contributi](#contributi)

---

## Caratteristiche

### Core
- **Multi-Layer Collage** - Crea composizioni con immagini sovrapposte
- **Drag & Drop** - Trascina file nella finestra (windnd, funziona anche nella versione portable .exe singolo)
- **Handle di Selezione** - Ridimensiona e ruota con handle visivi stile PowerPoint
- **Zoom 1-1000%** - Scroll delicato (1% per tick) per controllo preciso
- **Trasformazioni Complete** - Rotazione -180/+180, specchio H/V, posizionamento pixel-perfect
- **Adattamento Automatico** - 4 modalita: Adatta, Riempi, Riempi H, Riempi V
- **Blocco Proporzioni** - Toggle per mantenere aspect ratio durante ridimensionamento

### Esportazione
- **Multi-formato Immagine** - JPG, PNG, WebP, BMP con preset qualita
- **Multi-formato Video** - MP4, AVI, WebM, GIF animata
- **Preset Qualita** - Bassa/Media/Alta con DPI e bitrate ottimizzati
- **Sfondo Personalizzabile** - 9 colori preset + color picker

### UI/UX
- **Tema Dark Moderno** - Interfaccia blu notte con accenti cyan
- **Fullscreen all'avvio** - Massimizza spazio di lavoro
- **Pannello Scrollabile** - Tutti i controlli accessibili con scroll
- **Sezioni Colorate** - Differenziazione visiva: Layers (blu), Transform (cyan), Size (teal), Fit (viola), Mirror (arancio)
- **Logging integrato** - File di log per diagnostica (in `%LOCALAPPDATA%\R-Converter\`)

---

## Architettura

```
+-------------------------------------------------------------+
|                        RConverter                            |
|  (Classe principale - gestisce UI, eventi, logica)          |
+-------------------------------------------------------------+
|  +-------------+  +-------------+  +---------------------+  |
|  | ImageLayer  |  | ImageLayer  |  | ImageLayer (video)  |  |
|  | __slots__   |  | __slots__   |  | __slots__           |  |
|  | + cache     |  | + cache     |  | + video_path        |  |
|  +-------------+  +-------------+  +---------------------+  |
+-------------------------------------------------------------+
|  Canvas Preview (Tkinter)  |  Threading Export               |
|  Debounce 60fps            |  Progress Feedback              |
+-------------------------------------------------------------+
|  windnd Drag & Drop        |  Logging (%LOCALAPPDATA%)       |
+-------------------------------------------------------------+
```

### Dipendenze

| Libreria | Versione | Scopo |
|----------|----------|-------|
| Pillow | >=10.0.0 | Elaborazione immagini |
| opencv-python | >=4.8.0 | Elaborazione video (opzionale) |
| numpy | >=1.24.0 | Array processing per video |
| windnd | >=1.0.7 | Drag & drop nativo Windows |
| pyinstaller | >=5.0 | Build eseguibile (dev) |

---

## Installazione

### Requisiti Sistema
- **OS**: Windows 10/11
- **Python**: 3.8 o superiore (testato con 3.13)
- **RAM**: 4GB minimo, 8GB consigliato per video
- **Disco**: ~100MB per installazione completa

### Da Sorgente

```bash
# Clona o scarica il progetto
cd R-Converter

# Installa dipendenze
pip install -r requirements.txt
```

### Versione Portable
Scarica `R-Converter_Portable.exe` dalla release - un singolo file .exe, nessuna installazione richiesta.

### Versione Installer
Scarica `R-Converter_Setup_v1.3.1.exe` per l'installazione guidata con icona desktop e menu Start.

---

## Avvio

### Sviluppo
```bash
python main.py
```

### Portable
Doppio click su `R-Converter_Portable.exe` - funziona da qualsiasi posizione, anche da chiavetta USB.

---

## Guida all'uso

### Workflow Base

1. **Carica file** - `Aggiungi File` o `Ctrl+O` o trascina file nella finestra
2. **Imposta canvas** - Scegli un preset (Full HD, 4K, Instagram, etc.) o dimensioni personalizzate
3. **Trasforma layer** - Zoom, rotazione, posizione, flip con slider o mouse
4. **Esporta** - `ESPORTA IMMAGINE` o `ESPORTA VIDEO` o `Ctrl+S`

### Controlli Layer

| Azione | Mouse | Tastiera | Slider |
|--------|-------|----------|--------|
| Seleziona | Click su immagine | Click lista | - |
| Sposta | Drag centrale | - | Pan X / Tilt Y |
| Zoom | Scroll wheel | - | Zoom % |
| Ridimensiona | Drag handle angolo | - | Zoom % |
| Ruota | Drag handle rotazione (verde) | - | Rotazione |
| Elimina | - | Canc/Delete | Pulsante Rimuovi |
| Deseleziona | Click area vuota | Esc | - |

### Preset Risoluzioni Disponibili

| Preset | Dimensioni | Uso tipico |
|--------|-----------|------------|
| Full HD 16:9 | 1920x1080 | Video, presentazioni |
| HD 16:9 | 1280x720 | Web, streaming |
| 4K 16:9 | 3840x2160 | Ultra HD |
| Full HD Verticale 9:16 | 1080x1920 | Stories, Reels |
| Quadrato 1:1 | 1080x1080 | Instagram, profilo |
| Banner 3:1 | 1200x400 | Banner web |
| Twitter Header | 1500x500 | Copertina Twitter/X |
| Facebook Cover | 820x312 | Copertina Facebook |
| YouTube Thumbnail | 1280x720 | Miniature YouTube |
| Instagram Landscape | 1080x608 | Post Instagram |
| 4:3 | 800x600, 1024x768 | Formato classico |

### Preset Qualita

#### Immagini
| Preset | DPI | Bit Depth | Compressione | Uso |
|--------|-----|-----------|-------------|-----|
| Bassa | 72 | 8-bit | 40% | Web, preview |
| Media | 150 | 16-bit | 15% | Stampa casalinga |
| Alta | 300 | 24-bit | 0% | Stampa professionale |

#### Video
| Preset | Bitrate | CRF | Uso |
|--------|---------|-----|-----|
| Bassa | 2000 kbps | 28 | Web, file piccoli |
| Media | 5000 kbps | 23 | Qualita bilanciata |
| Alta | 8000 kbps | 18 | Massima qualita |

### Scorciatoie

| Tasto | Azione |
|-------|--------|
| `Ctrl+O` | Apri file |
| `Ctrl+S` | Esporta immagine |
| `Canc` | Elimina layer selezionato |
| `Esc` | Deseleziona tutto |
| `Scroll` | Zoom +/-1% |
| `Drag` | Sposta layer |

---

## Struttura del Codice

```
R-Converter/
├── main.py                    # Applicazione principale (~2226 righe)
├── build_exe.py               # Script build interattivo
├── requirements.txt           # Dipendenze Python
├── README.md                  # Questa documentazione
├── icon.ico                   # Icona applicazione
├── R-Converter.spec           # PyInstaller spec (installer, onedir)
├── R-Converter_Portable.spec  # PyInstaller spec (portable, onefile)
├── installer.iss              # Inno Setup script (v1.3.1)
├── _clean_and_build.bat       # Build rapida (doppio click)
├── .cursor/rules/             # Cursor AI rules
│   ├── project.mdc            # Regole generali progetto
│   ├── build.mdc              # Regole build e distribuzione
│   └── main-py.mdc            # Regole specifiche per main.py
└── dist/                      # Output build
    ├── R-Converter/           # Versione installer (cartella)
    └── R-Converter_Portable.exe  # Versione portable (singolo exe)
```

### Organizzazione main.py

```
Righe 1-77:      Import, logging (%LOCALAPPDATA%), costanti, preset risoluzioni
Righe 80-153:    Classe ImageLayer (data model con __slots__ e cache)
Righe 156-762:   RConverter.__init__, setup_style, create_widgets (UI 3 colonne)
Righe 764-846:   Setup drag & drop (windnd + fallback tkinterdnd2)
Righe 847-952:   Init canvas, preset qualita, size display
Righe 987-1335:  Gestione layer (add, load, remove, move, duplicate, fit)
Righe 1336-1445: Trasformazioni (zoom, rotation, position, flip)
Righe 1447-1593: Rendering canvas (composite, handles, debounce)
Righe 1595-1866: Mouse handlers, scroll, keyboard, output settings
Righe 1866-2210: Export image/video (threading, progress, GIF ottimizzata)
Righe 2212-2226: main() entry point
```

---

## API e Classi Principali

### ImageLayer

```python
class ImageLayer:
    """Rappresenta un elemento nel collage"""
    __slots__ = ['id', 'original_image', 'name', 'offset_x', 'offset_y',
                 'zoom', 'rotation', 'flip_h', 'flip_v', 'is_video',
                 'video_path', 'video_fps', 'video_frames',
                 'bounds_in_canvas', '_cache', '_cache_key']

    def get_transformed_image(use_cache=True) -> Image
    def invalidate_cache() -> None
    def cleanup() -> None          # Libera risorse (immagine, cache)
    def get_display_name() -> str
```

### RConverter (metodi chiave)

```python
class RConverter:
    # Inizializzazione
    def __init__(root: tk.Tk)
    def setup_style() -> None           # Tema dark blue
    def create_widgets() -> None        # Layout 3 colonne
    def setup_drag_and_drop() -> None   # windnd + fallback tkinterdnd2

    # Layer management
    def load_image(filepath) -> None
    def load_video(filepath) -> None
    def remove_selected_layer() -> None
    def duplicate_layer() -> None
    def move_layer_up/down() -> None

    # Trasformazioni
    def fit_keep_aspect() -> None       # Adatta mantenendo proporzioni
    def fit_contain() -> None           # Riempi (cover)
    def fit_fill_horizontal() -> None   # Riempi larghezza
    def fit_fill_vertical() -> None     # Riempi altezza

    # Rendering
    def redraw_canvas() -> None                  # Schedula con debounce
    def create_composite_image(w, h, ...) -> Image  # Composizione layer

    # Export (thread separato)
    def export_image() -> None          # Avvia thread export immagine
    def export_video() -> None          # Avvia thread export video
```

---

## Performance e Ottimizzazioni

### Implementate

| Ottimizzazione | Descrizione | Impatto |
|----------------|-------------|---------|
| `__slots__` | Memoria layer ridotta ~40% | RAM |
| Cache trasformazioni | Evita ricalcolo flip/rotation | CPU |
| Debounce 60fps | Max 16ms tra redraw | UI fluida |
| NEAREST durante drag | Resize veloce mentre trascini | Responsivita |
| BILINEAR statico | Qualita buona per preview | Bilanciamento |
| LANCZOS export | Massima qualita in output | Qualita |
| Pre-calc video | Parametri calcolati una volta per export | Export speed |
| Quantize GIF | Palette 256 colori, limite 3000 frame | RAM |
| Threading export | UI non bloccante durante export | UX |
| Cleanup layer | Libera memoria + gc.collect | Memory leak prevention |

### Logging

Il file `r_converter.log` viene creato in `%LOCALAPPDATA%\R-Converter\` e traccia:
- Caricamento immagini/video con dimensioni e parametri
- Operazioni di export con dimensioni file risultante
- Errori di drag & drop e conversione
- Stato del supporto video (OpenCV)

---

## Build e Distribuzione

### Build rapida (consigliato)

Doppio click su `_clean_and_build.bat` nella root del progetto. Genera automaticamente entrambe le versioni.

### Versione Portable (singolo .exe)

```bash
python -m PyInstaller R-Converter_Portable.spec --noconfirm --clean
```

Output: `dist/R-Converter_Portable.exe` (singolo file, ~65MB)

Il drag & drop funziona tramite windnd (Python puro), che viene incluso nella build con `collect_all('windnd')`.

### Versione Installer (cartella per Inno Setup)

```bash
python -m PyInstaller R-Converter.spec --noconfirm --clean
```

Output: `dist/R-Converter/` (cartella con exe + DLL)

Poi compilare l'installer: aprire `installer.iss` con Inno Setup Compiler (Ctrl+F9).
Output installer: `installer_output/R-Converter_Setup_v1.3.1.exe`

### Entrambe le versioni

```bash
python build_exe.py
# -> Scegli opzione 3
```

### Differenze tra versioni

| Aspetto | Installer | Portable |
|---------|-----------|----------|
| Formato | Cartella + Inno Setup | Singolo .exe |
| Avvio | Immediato | ~3-5 secondi (estrazione) |
| Dimensione | ~65MB installato | ~65MB singolo file |
| Drag & Drop | windnd | windnd |
| Icona desktop | Si (opzionale) | No (portatile) |
| Menu Start | Si | No |
| USB | No | Si, copia e usa |

---

## Risoluzione Problemi

### Errori Comuni

| Errore | Causa | Soluzione |
|--------|-------|-----------|
| "OpenCV non installato" | cv2 mancante | `pip install opencv-python` |
| Video non si carica | Codec mancante | Installa K-Lite Codec Pack |
| Export lento | File/risoluzione grande | Usa preset qualita inferiore |
| Crash su immagini grandi | RAM insufficiente | Riduci risoluzione sorgente |
| D&D non funziona | Esecuzione come admin | Avvia senza "Esegui come admin" |

### Diagnostica

Il file `r_converter.log` (in `%LOCALAPPDATA%\R-Converter\`) contiene informazioni dettagliate:

```
2026-02-11 10:00:00 [INFO] OpenCV 4.10.0 caricato, supporto video attivo
2026-02-11 10:00:01 [INFO] Drag & Drop: windnd attivo
2026-02-11 10:00:15 [INFO] Immagine caricata: foto (3840x2160) zoom=50%
2026-02-11 10:01:00 [INFO] Export completato: 2450.3 KB
```

### Nota su Drag & Drop

Il drag & drop non funziona se l'applicazione viene eseguita "come Amministratore" e i file vengono trascinati da un processo non-admin (limitazione UIPI di Windows). Soluzione: avviare normalmente senza privilegi elevati.

### Test Dipendenze

```bash
python -c "from PIL import Image; import cv2; import numpy; import windnd; print('Tutte le dipendenze OK')"
```

---

## Contributi

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
- **Logging**: `logger.info/warning/error()` al posto di `print()`

---

## Changelog

### v1.3.1 (2026-02-11)
- **Fix Drag & Drop portable** - Rimossa implementazione ctypes Win32 (causava crash), ripristinato windnd
- **Fix log file** - Spostato da cartella exe a `%LOCALAPPDATA%\R-Converter\` (non invasivo)
- **Build scripts** - Aggiunto `_clean_and_build.bat` per build rapida con doppio click
- **Build command** - Tutti i comandi usano `python -m PyInstaller` (compatibile con installazioni utente)

### v1.3.0 (2026-02-11)
- **Logging integrato** - File `r_converter.log` per diagnostica in produzione
- **Gestione errori migliorata** - Protezione su percorsi non-UTF8, division-by-zero, file non validi
- **Export GIF ottimizzato** - Limite 3000 frame con rilascio memoria (gc.collect)
- **Export video robusto** - Rilascio risorse garantito nel finally, FPS fallback
- **Validazione file** - Controllo esistenza e dimensioni prima del caricamento
- **Cursor Rules** - Regole AI dedicate al progetto per sviluppo assistito
- **Documentazione aggiornata** - README completo con tutti i preset e la nuova architettura

### v1.2.0
- Zoom 1-1000% con scroll 1% per tick
- Pulsanti adattamento (Adatta, Riempi, Riempi H, Riempi V)
- Toggle blocco proporzioni
- Pannello sinistro scrollabile
- Sezioni con colori differenziati
- Fix gestione eccezioni e divisione per zero
- Cleanup memoria layer rimossi

### v1.1.0
- Preset qualita immagine/video
- Campi dimensione pixel con aspect ratio lock
- Fullscreen all'avvio

### v1.0.0
- Release iniziale
- Multi-layer collage
- Export immagine/video
- Drag & drop

---

## Licenza

MIT License - Libero per uso personale e commerciale.

---

**Creato per semplificare la conversione di immagini e video**
