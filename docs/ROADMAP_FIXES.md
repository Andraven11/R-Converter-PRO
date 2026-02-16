# R-Converter PRO - Roadmap Correzioni Broadcast

> Documento tecnico per guidare le modifiche al codice.
> Basato su: analisi main.py, specifiche NovaStar A8/A10, Resolume Arena, vMix, Millumin, FFmpeg docs.
> Data: Feb 2026

---

## Stato implementazione (Feb 2026)

| Fix | Priorita | Stato | Commit |
|-----|----------|-------|--------|
| FIX-1 Processing video | CRITICO | IMPLEMENTATO | - |
| FIX-2 Dither Bayer | CRITICO | IMPLEMENTATO | - |
| FIX-3 Color metadata bt709 | CRITICO | IMPLEMENTATO | - |
| FIX-4 HAP Snappy + Chunks | IMPORTANTE | IMPLEMENTATO | - |
| FIX-5 H.265 CBR reale | IMPORTANTE | IMPLEMENTATO | - |
| FIX-6 H.264 bitrate | UTILE | IMPLEMENTATO | - |

---

## Indice

1. [FIX-1 CRITICO: Processing video mancante](#fix-1-critico-processing-video-mancante)
2. [FIX-2 CRITICO: Dither Bayer non implementato](#fix-2-critico-dither-bayer-non-implementato)
3. [FIX-3 CRITICO: Color metadata bt709 mancanti](#fix-3-critico-color-metadata-bt709-mancanti)
4. [FIX-4 IMPORTANTE: HAP senza Snappy e Chunks](#fix-4-importante-hap-senza-snappy-e-chunks)
5. [FIX-5 IMPORTANTE: H.265 non e CBR reale](#fix-5-importante-h265-non-e-cbr-reale)
6. [FIX-6 UTILE: H.264 bitrate calcolo sospetto](#fix-6-utile-h264-bitrate-calcolo-sospetto)
7. [Verifica finale: checklist per test](#verifica-finale-checklist-per-test)

---

## FIX-1 CRITICO: Processing video mancante

### Problema

I frame video passano dal compositing a FFmpeg **senza filtri di processing**.
La funzione `_apply_image_processing()` (riga ~1962) e chiamata solo per export immagine (riga ~3084),
ma MAI nel loop producer-consumer dell'export video (righe ~3207-3247).

### Impatto LED wall

Senza processing, i video esportati per LED wall avranno:
- **Banding visibile** nei gradienti scuri (tipico con 13-14 bit gray depth)
- **Rumore non filtrato** (soprattutto su pannelli con scan ratio 1/16 e 1/24)
- **Neri schiacciati** senza color levels
- **Dettaglio perso** senza sharpen adattivo

### Fonte tecnica

- NovaStar A8s-N: supporta 8/10/12-bit input, 22-bit+ grayscale enhancement
- NovaStar A10s Plus-N: 16-bit grayscale, 65536 livelli
- A gray_depth bassa (13-14 bit), il processing pre-output e essenziale per mascherare i limiti del pannello

### Soluzione

Nel loop `frame_reader()` (riga ~3217), dopo il compositing di ogni frame,
applicare `_apply_image_processing()`:

```python
# Dentro make_composite_frame(), DOPO create_composite_image:
def make_composite_frame(video_frame_overrides):
    composite = self.create_composite_image(output_w, output_h, for_export=True,
                                             video_frame_overrides=video_frame_overrides,
                                             layers=all_layers)
    # AGGIUNGERE: processing broadcast sul frame composito
    composite = self._apply_image_processing(composite, filters, intensity=proc_int)
    return composite
```

### Variabili necessarie

`filters` e `proc_int` devono essere snapshotted prima del thread (come gia fatto per output_w, output_h):
```python
filters = profile.get("filters", {})
proc_int = self.proc_intensity.get() / 100.0
```

### Performance

- Il processing aggiunge ~5-15ms per frame (1080p) o ~20-40ms per frame (4K)
- Con 50fps e Queue(maxsize=4), la pipeline rimane sostenibile fino a ~3840x2160
- Per risoluzioni maggiori, valutare di spostare i filtri nella filter chain FFmpeg

### File da modificare

- `main.py`: funzione `_do_export_project()`, area ~3150-3250

---

## FIX-2 CRITICO: Dither Bayer non implementato

### Problema

I `FILTER_PROFILES` definiscono `dither_type: "bayer"` e `dither_scale` per ogni preset,
ma `_apply_image_processing()` non li usa. Il dither non e mai applicato.

### Impatto LED wall

- **Banding nei gradienti scuri**: il problema piu visibile su LED wall con gray depth 13-14 bit
- **Transizioni a gradini**: visibili su sfondi sfumati, video con gradienti cielo/tramonto
- NovaStar A8: 14-bit / 3840Hz refresh - anche con buon refresh, senza dither il banding e evidente
- NovaStar A5: 13-bit / 1920Hz - dither ancora piu critico

### Fonte tecnica

- FFmpeg swscale: SWS_DITHER_BAYER supportato nativamente
- Bayer ordered dithering: pattern 8x8 deterministico, ideale per display LED (nessun flicker temporale)
- Human visual perception: soglia ~12 bit SDR, ~14 bit HDR - sotto questi valori il dither e obbligatorio
- bayer_scale: 0-5, valori bassi = pattern piu visibile ma meno banding

### Soluzione

Aggiungere il passo di dithering nella pipeline `_apply_image_processing()`,
DOPO lo sharpen e PRIMA del return:

```python
# 6. Dither Bayer (dopo sharpen, prima del return)
dither_type = filters.get("dither_type", "")
dither_scale = int(filters.get("dither_scale", 2) * scale)
if dither_type == "bayer" and dither_scale > 0 and VIDEO_SUPPORT:
    arr = np.array(img).astype(np.float32)
    # Bayer 8x8 matrix per dithering ordinato
    bayer_8x8 = np.array([
        [ 0, 32,  8, 40,  2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44,  4, 36, 14, 46,  6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [ 3, 35, 11, 43,  1, 33,  9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47,  7, 39, 13, 45,  5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ], dtype=np.float32) / 64.0 - 0.5  # Normalizza a [-0.5, 0.5]

    # Tile il pattern sulla dimensione dell'immagine
    h, w = arr.shape[:2]
    tiled = np.tile(bayer_8x8, (h // 8 + 1, w // 8 + 1))[:h, :w]
    tiled = tiled[:, :, np.newaxis]  # Broadcast su 3 canali RGB

    # Applica con intensita proporzionale a dither_scale
    strength = dither_scale * 1.5  # 1.5 = fattore empirico per 8-bit
    arr = arr + tiled * strength
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
```

### File da modificare

- `main.py`: funzione `_apply_image_processing()`, area ~2005-2010 (dopo sharpen)

---

## FIX-3 CRITICO: Color metadata bt709 mancanti

### Problema

Il comando FFmpeg in `_build_ffmpeg_video_command()` (riga ~3014) non include mai
i flag di color metadata. Senza questi, il player/media server interpreta il color space
a caso (spesso bt601 per SD, non specificato per HD).

### Impatto LED wall

- **Resolume Arena**: interpreta il colore dal container; senza tag, puo applicare la matrice sbagliata
- **vMix**: conferma che esporta Rec.709 per tutti i formati, ma in INPUT si aspetta tag bt709 corretti
- **NovaStar A8/A10**: supportano Rec.709, DCI-P3, Rec.2020 - il tag determina quale usare
- **Sintomi**: neri schiacciati (limited vs full range), colori desaturati, highlight bruciati

### Fonte tecnica

- FFmpeg docs: `-color_primaries bt709 -color_trc bt709 -colorspace bt709` sono metadata, non conversioni
- Per HAP (sRGB/RGB): usare `-color_trc iec61966-2-1` (sRGB transfer) + `-color_primaries bt709`
- Per DNxHR/ProRes/H.264/H.265 (YUV): usare bt709 su tutti e tre i flag
- NovaStar scheda tecnica: supporto Rec.709 nativo con gamma individuale per R/G/B

### Soluzione

Aggiungere i flag DOPO la sezione codec e PRIMA del filepath finale:

```python
# Color metadata bt709 (prima di cmd.append(filepath))
if codec == "hap" or v.get("format_name") in ("hap", "hap_q"):
    # HAP usa RGB/sRGB - tag con sRGB transfer function
    cmd.extend(["-color_primaries", "bt709",
                "-color_trc", "iec61966-2-1",
                "-colorspace", "rgb"])
else:
    # YUV codecs: DNxHR, ProRes, H.264, H.265
    cmd.extend(["-color_primaries", "bt709",
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-color_range", "tv"])
```

### Nota su `-color_range tv`

- `tv` = limited range (16-235) - standard broadcast, DNxHR, ProRes
- `pc` = full range (0-255) - NON usare per broadcast LED wall
- HAP usa RGB full range, quindi NON aggiungere `-color_range` per HAP

### File da modificare

- `main.py`: funzione `_build_ffmpeg_video_command()`, area ~3055-3057 (prima di `cmd.append(filepath)`)

---

## FIX-4 IMPORTANTE: HAP senza Snappy e Chunks

### Problema

I profili definiscono `hap_chunks: 8` ma il comando FFmpeg non li usa.
Manca anche la compressione Snappy.

### Impatto LED wall

- **Senza chunks**: Resolume decodifica ogni frame con un singolo thread CPU.
  A 3840x1152 (Holiday Inn) o 4K, il playback puo perdere frame
- **Senza Snappy**: file 20-30% piu grandi del necessario, piu I/O dal disco
- **Resolume nota**: il numero di chunks non deve superare i core CPU del sistema di playback

### Fonte tecnica

- hap.video: "For 8K+ video, chunking splits each frame for parallel CPU decoding"
- hap.video: "Use -chunks 4 or more for high-res depending on CPU core count"
- hap.video: "Snappy reduces file size with minimal decode performance impact"
- Resolume: HAP Q con chunks = decodifica parallela multi-core

### Soluzione

Modificare la sezione HAP in `_build_ffmpeg_video_command()`:

```python
# DA (riga ~3029):
if codec == "hap" or v.get("format_name") in ("hap", "hap_q"):
    fmt_hap = v.get("format_name", "hap")
    cmd.extend(["-c:v", "hap", "-format", fmt_hap, "-an"])

# A:
if codec == "hap" or v.get("format_name") in ("hap", "hap_q"):
    fmt_hap = v.get("format_name", "hap")
    chunks = v.get("hap_chunks", 8)
    cmd.extend(["-c:v", "hap", "-format", fmt_hap,
                "-compressor", "snappy", "-chunks", str(chunks), "-an"])
```

### Nota su chunks

- 8 chunks e un buon default per sistemi con 8+ core (standard nel 2025-2026)
- Per HD (1920x1080): 4 chunks sono sufficienti
- Per 4K+: 8 chunks ottimali
- Il valore e gia nel profilo (`hap_chunks: 8`) ma non viene usato

### File da modificare

- `main.py`: funzione `_build_ffmpeg_video_command()`, riga ~3029

---

## FIX-5 IMPORTANTE: H.265 non e CBR reale

### Problema

Il comando x265 usa solo `vbv-maxrate` e `vbv-bufsize` ma manca `-b:v` per il bitrate target.
Senza `-b:v`, x265 usa CRF (Constant Rate Factor) di default, che e VBR.

### Impatto LED wall

- **Qualita variabile**: scene scure avranno bitrate basso, scene complesse bitrate alto
- **Contraddice la regola "CBR per broadcast"**: la receiving card e il processor si aspettano
  un flusso costante per evitare stuttering
- NovaStar: il segnale HDMI ha bitrate fisso; il video player deve fornire dati costanti

### Soluzione

```python
# DA (riga ~3043):
elif codec == "libx265":
    denom = max(1920 * 1080, 1)
    br = int(v.get("bitrate_1080p_mbps", 140) * (output_w * output_h) / denom)
    cmd.extend(["-c:v", "libx265", "-preset", v.get("preset", "medium"),
                "-x265-params", f"vbv-maxrate={br}:vbv-bufsize={br}"])

# A:
elif codec == "libx265":
    denom = max(1920 * 1080, 1)
    br_mbps = int(v.get("bitrate_1080p_mbps", 140) * (output_w * output_h) / denom)
    br_kbps = br_mbps * 1000
    cmd.extend(["-c:v", "libx265", "-preset", v.get("preset", "medium"),
                "-b:v", f"{br_kbps}k",
                "-maxrate", f"{br_kbps}k", "-bufsize", f"{br_kbps * 2}k",
                "-x265-params", f"vbv-maxrate={br_mbps * 1000}:vbv-bufsize={br_mbps * 2000}:strict-cbr=1"])
```

### Nota: `strict-cbr=1`

Il parametro x265 `strict-cbr=1` forza CBR reale (padding se necessario).
Questo e il comportamento corretto per broadcast.

### File da modificare

- `main.py`: funzione `_build_ffmpeg_video_command()`, righe ~3043-3049

---

## FIX-6 UTILE: H.264 bitrate calcolo sospetto

### Problema

Riga ~3053: il calcolo del bitrate H.264 e:
```python
br = int(v.get("bitrate_1080p_mbps", 200) * (output_w * output_h) / denom) * 1000
```

Il `* 1000` e fuori dall'`int()`, il che significa:
- Prima calcola il rapporto proporzionale alla risoluzione (risultato in Mbps)
- Poi tronca a intero
- Poi moltiplica x1000 per ottenere kbps

Se il risultato della divisione e 0.5, `int(0.5) = 0`, e `0 * 1000 = 0` -> bitrate zero.

### Soluzione

```python
# DA:
br = int(v.get("bitrate_1080p_mbps", 200) * (output_w * output_h) / denom) * 1000

# A:
br_mbps = v.get("bitrate_1080p_mbps", 200) * (output_w * output_h) / denom
br_kbps = max(1000, int(br_mbps * 1000))  # Minimo 1 Mbps
cmd.extend(["-c:v", "libx264", "-preset", v.get("preset", "fast"),
            "-profile:v", "high", "-b:v", f"{br_kbps}k",
            "-maxrate", f"{br_kbps}k", "-bufsize", f"{br_kbps * 2}k"])
```

### File da modificare

- `main.py`: funzione `_build_ffmpeg_video_command()`, righe ~3051-3055

---

## Verifica finale: checklist per test

Dopo ogni FIX, verificare:

### Test FIX-1 (processing video)
- [ ] Esporta video con preset NovaStar A5 (entry) -> i filtri devono essere applicati
- [ ] Esporta video con preset NovaStar A10 (broadcast) -> filtri piu leggeri ma presenti
- [ ] Confronta frame estratto dal video con export immagine -> processing simile

### Test FIX-2 (dither)
- [ ] Esporta immagine con gradiente scuro (nero -> grigio 10%)
- [ ] Verificare che il gradiente non abbia banding a gradini
- [ ] Confrontare con/senza dither su monitor calibrato

### Test FIX-3 (color metadata)
- [ ] Esporta video HAP Q -> verifica con `ffprobe -show_streams` che color_primaries=bt709
- [ ] Esporta video DNxHR -> verifica color_range=tv, colorspace=bt709
- [ ] Esporta video H.264 -> verifica tutti i tag presenti
- [ ] Caricare in Resolume e verificare che i colori siano corretti

### Test FIX-4 (HAP chunks/snappy)
- [ ] Esporta video HAP Q -> verifica con `ffprobe` che il file abbia chunks
- [ ] Confronta dimensione file con/senza snappy
- [ ] Caricare in Resolume e verificare playback fluido a 3840x1152

### Test FIX-5 (H.265 CBR)
- [ ] Esporta video H.265 -> verifica con `ffprobe` il bitrate medio
- [ ] Il bitrate deve essere costante (varianza < 5%)

### Test FIX-6 (H.264 bitrate)
- [ ] Esporta video H.264 a risoluzione 800x600 -> verificare che il bitrate non sia 0
- [ ] Esporta video H.264 a 4K -> verificare bitrate proporzionale

---

## Ordine di implementazione consigliato

1. **FIX-3** (color metadata) - 5 minuti, rischio zero, impatto massimo
2. **FIX-4** (HAP snappy/chunks) - 2 minuti, rischio zero
3. **FIX-6** (H.264 bitrate) - 3 minuti, rischio basso
4. **FIX-5** (H.265 CBR) - 5 minuti, rischio basso
5. **FIX-2** (dither Bayer) - 15 minuti, rischio medio (testare su gradienti)
6. **FIX-1** (processing video) - 20 minuti, rischio medio (testare performance)

**Implementati tutti il 16 Feb 2026.** Vedi sezione "Stato implementazione" in cima al documento.

---

*Documento generato da analisi di: main.py (3386 righe), GUIDE.md, rules/project.mdc, rules/main-py.mdc,
specifiche NovaStar A8s-N / A10s Plus-N, docs Resolume Arena, vMix forums, Millumin help,
FFmpeg codec documentation, hap.video, Academy Software Foundation Encoding Guidelines.*
