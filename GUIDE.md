# R-Converter PRO - Guida Completa

**Convertitore Broadcast per LED Wall - Immagini e Video Multi-Layer**

> Versione 2.0.0 PRO | Python 3.8+ | Windows 10/11

---

## Indice

1. [Introduzione e Caratteristiche](#1-introduzione-e-caratteristiche)
2. [Installazione e Avvio](#2-installazione-e-avvio)
3. [Guida all'Uso](#3-guida-alluso)
4. [Build e Distribuzione](#4-build-e-distribuzione)
5. [Architettura e Struttura Codice](#5-architettura-e-struttura-codice)
6. [Performance e Ottimizzazioni](#6-performance-e-ottimizzazioni)
7. [Risoluzione Problemi](#7-risoluzione-problemi)
8. [Sviluppo e Git](#8-sviluppo-e-git)

---

## 1. Introduzione e Caratteristiche

### Core
- **Multi-Layer Collage** - Composizioni con immagini sovrapposte
- **Drag & Drop** - Trascina file nella finestra (windnd, funziona anche nella versione portable)
- **Handle di Selezione** - Ridimensiona e ruota stile PowerPoint
- **Zoom 1-1000%** - Scroll 1% per tick
- **Trasformazioni** - Rotazione -180/+180, specchio H/V, posizionamento pixel-perfect
- **Adattamento** - Adatta, Riempi, Riempi H, Riempi V
- **Blocco Proporzioni** - Toggle aspect ratio

### Export Broadcast
- **6 preset LED Wall** - NovaStar A5/A8/A10, Holiday Inn, Uniview, Wave&Co
- **5 software target** - Resolume (HAP Q), vMix (DNxHR), Millumin, H.264, H.265
- **Pipeline ottimizzata** - Color levels, deband, denoise, bilateral, sharpen, dither Bayer
- **Export immagine/video** - PNG/JPG, MP4/MOV/GIF con codec broadcast
- **Color metadata bt709** - Tag corretti per Resolume/vMix/NovaStar
- **HAP Snappy + Chunks** - Ottimizzato per Resolume GPU

### UI/UX
- Tema dark blu notte, pannello destro PRO con dropdown a cascata
- Logging in `%LOCALAPPDATA%\R-Converter\`

---

## 2. Installazione e Avvio

### Requisiti
- **OS**: Windows 10/11
- **Python**: 3.8+ (testato con 3.13)
- **RAM**: 4GB minimo, 8GB per video

### Da Sorgente
```bash
cd R-Converter
pip install -r requirements.txt
python main.py
```

### Versione Portable
Doppio click su `R-Converter_Portable.exe`. Funziona da USB, nessuna installazione.

**Nota**: Avvio ~3-5 secondi (estrazione in temp). Il drag & drop è attivo dopo ~1.2 secondi. Puoi anche trascinare file sull'icona dell'exe prima di aprirlo.

### Versione Installer
Esegui `R-Converter_PRO_Setup_v2.0.0.exe` per installazione con icona desktop e menu Start.

---

## 3. Guida all'Uso

### Workflow
1. **Carica** - `Aggiungi File`, `Ctrl+O` o trascina nella finestra
2. **Canvas** - Preset (Full HD, 4K, etc.) o dimensioni personalizzate
3. **Trasforma** - Zoom, rotazione, posizione, flip
4. **Esporta** - `ESPORTA IMMAGINE` o `ESPORTA VIDEO`

### Controlli Layer
| Azione | Mouse | Tastiera |
|--------|-------|----------|
| Seleziona | Click | - |
| Sposta | Drag | - |
| Zoom | Scroll | - |
| Ridimensiona | Handle angolo | - |
| Ruota | Handle verde | - |
| Elimina | - | Canc |
| Deseleziona | Click vuoto | Esc |

### Preset Risoluzioni
Full HD 16:9, HD, 4K, Verticale 9:16, Quadrato 1:1, Banner, Twitter, Facebook, YouTube, Instagram, 4:3.

### Scorciatoie
- `Ctrl+O` Apri | `Ctrl+S` Esporta | `Canc` Elimina | `Esc` Deseleziona

---

## 4. Build e Distribuzione

### Build Rapida
Doppio click su `_clean_and_build.bat`. Genera installer + portable.

### Prerequisiti
1. Python nel PATH
2. `pip install -r requirements.txt`
3. `python _download_ffmpeg_build.py` (eseguito automaticamente dal bat)
4. Inno Setup 6 (opzionale, per installer)

### Comandi Manuali
```bash
# Installer (onedir)
python -m PyInstaller R-Converter.spec --noconfirm --clean

# Portable (onefile)
python -m PyInstaller R-Converter_Portable.spec --noconfirm --clean

# Setup (dopo build installer)
# Apri installer.iss con Inno Setup, Ctrl+F9
```

### Output
- `dist/R-Converter_Portable.exe` - Singolo exe (~100MB)
- `dist/R-Converter/` - Cartella per Inno Setup
- `installer_output/R-Converter_PRO_Setup_v2.0.0.exe` - Installer

### Regole Build Critiche
- Usare sempre `python -m PyInstaller` (non `pyinstaller` diretto)
- FFmpeg: eseguire `_download_ffmpeg_build.py` prima della build
- windnd: `collect_all('windnd')` obbligatorio in entrambi gli spec
- icon.ico obbligatorio in root

### Test Post-Build
1. Avvio senza errori
2. **Canvas area LED wall visibile** (rettangolo con risoluzione output al centro)
3. **Drag & drop funziona** (anche portable - windnd con ritardo 500ms)
4. Export immagine e video
5. Log in %LOCALAPPDATA%\R-Converter\

---

## 5. Architettura e Struttura Codice

### Struttura Progetto
```
R-Converter/
├── main.py                 # Applicazione (~3400 righe)
├── requirements.txt
├── icon.ico
├── R-Converter.spec        # PyInstaller installer
├── R-Converter_Portable.spec
├── installer.iss           # Inno Setup
├── _clean_and_build.bat    # Build completa
├── _download_ffmpeg_build.py
├── GUIDE.md                # Questa guida
├── README.md               # Sintesi
└── .cursor/rules/          # Regole AI
```

### main.py - Sezioni
- Import, logging, costanti, preset LED wall
- ImageLayer (__slots__, cache)
- RConverter: init, UI, drag & drop, layer, export
- Pipeline processing, compositing, FFmpeg

### Dipendenze
| Libreria | Uso |
|----------|-----|
| Pillow | Immagini, resize, filtri |
| opencv-python | Video, bilateral, denoise |
| numpy | Array processing |
| windnd | Drag & drop Windows |

---

## 6. Performance e Ottimizzazioni

### Export Implementate (v2.0+)
- **Pipeline unificata** - 2 conversioni PIL↔numpy invece di 6 (~30-40% più veloce)
- **Double-buffering video** - Pre-fetch frame, Queue producer/consumer (~20-30% più veloce)
- **Processing su video** - Stessi filtri dell'export immagine applicati a ogni frame (color levels, deband, denoise, bilateral, sharpen, dither Bayer)
- **Dither Bayer** - Anti-banding per LED wall 13-14 bit gray depth
- **Color metadata bt709** - Tag corretti per interpretazione colore su Resolume/vMix/NovaStar
- **HAP Snappy + Chunks** - File più piccoli, decodifica parallela Resolume
- **CBR H.264/H.265** - Bitrate costante per broadcast
- **LANCZOS export** - Qualità superiore per rotation/resize
- **Thread-safety** - Snapshot layer, cleanup VideoCapture

### Preview (suggerimenti futuri)
- Compositing a risoluzione preview durante drag (5-10x)
- Debounce sempre attivo anche durante drag
- Cache zoom nei layer

### Regole Performance
- NEAREST preview, LANCZOS export
- Export in thread separato
- FFmpeg subprocess (non OpenCV frame-by-frame)
- gc.collect dopo export

---

## 7. Risoluzione Problemi

### Errori Comuni
| Errore | Soluzione |
|--------|-----------|
| OpenCV non installato | `pip install opencv-python` |
| Video non si carica | K-Lite Codec Pack |
| D&D non funziona (portable) | Attendi ~1.2s dopo avvio; non eseguire come Admin |
| D&D non funziona | Avvia senza "Esegui come amministratore" |
| Export lento | Preset qualità inferiore |

### Drag & Drop Portable
- **Ritardo 1.2s**: Con onefile la finestra impiega più tempo. Il setup D&D è ritardato.
- **Trascina sull'exe**: Puoi trascinare file sull'icona dell'exe prima di aprirlo; verranno caricati all'avvio.
- **UIPI**: Se l'app è "Esegui come admin" e trascini da Esplora (non admin), Windows blocca. Soluzione: avvia normalmente.

### Diagnostica
Log: `%LOCALAPPDATA%\R-Converter\r_converter.log`

```
[INFO] OpenCV 4.10.0 caricato
[INFO] Drag & Drop: windnd attivo
[INFO] Export completato: 2450.3 KB
```

### Test Dipendenze
```bash
python -c "from PIL import Image; import cv2; import numpy; import windnd; print('OK')"
```

---

## 8. Sviluppo e Git

### Commit e Push (AI)
```bash
git add -A && git commit -m "chore: descrizione" && git push
```

### Configurazione Cursor
- `.cursor/cli.json` - Permessi Shell(git)
- "Allow Git Writes Without Approval" = true

### Code Style
- 4 spazi, max 120 caratteri
- snake_case funzioni, CamelCase classi
- logger invece di print()

### Changelog
- **v2.0.1** - Fix broadcast: processing su video, dither Bayer, color metadata bt709, HAP snappy+chunks, H.264/H.265 CBR
- **v2.0.0** - Pannello PRO, export broadcast, pipeline ottimizzata
- **v1.3.1** - Fix D&D portable, log in AppData
- **v1.3.0** - Logging, gestione errori

---

*R-Converter PRO - Creato per semplificare la conversione broadcast per LED wall*
