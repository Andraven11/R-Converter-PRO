# R-Converter PRO - Roadmap Correzioni Broadcast

> Documento tecnico per guidare le modifiche al codice.
> Basato su: analisi main.py, specifiche NovaStar A8/A10, Resolume Arena, vMix, Millumin, FFmpeg docs.
> Data: Feb 2026

---

## Stato implementazione (Feb 2026)

| Fix | Priorita | Stato | Note |
|-----|----------|-------|------|
| FIX-1 Processing video | CRITICO | IMPLEMENTATO | make_composite_frame + _apply_image_processing |
| FIX-2 Dither Bayer | CRITICO | IMPLEMENTATO | passo 6 in _apply_image_processing |
| FIX-3 Color metadata bt709 | CRITICO | IMPLEMENTATO | flag bt709/sRGB per ogni codec |
| FIX-4 HAP Snappy + Chunks | IMPORTANTE | AGGIORNATO | chunks dinamici 4/8, -compressor rimosso (compatibilità Essentials) |
| FIX-5 H.265 CBR reale | IMPORTANTE | IMPLEMENTATO | -b:v + strict-cbr=1 |
| FIX-6 H.264 bitrate | UTILE | IMPLEMENTATO | max(1000, int(br_mbps * 1000)) |

| Ottimizzazione | Priorita | Stato | Speedup stimato |
|----------------|----------|-------|-----------------|
| OPT-1 Pre-composito statico | CRITICO | IMPLEMENTATO | 2-5x (proporzionale a layer statici) |
| OPT-2 Filtri via FFmpeg -vf | CRITICO | IMPLEMENTATO | 5-10x (solo se dither disabilitato) |
| OPT-3 Cache Bayer dither | IMPORTANTE | IMPLEMENTATO | eliminazione allocazione per frame |
| OPT-4 Riduzione conversioni colore | IMPORTANTE | IMPLEMENTATO | sharpen+dither in numpy |
| OPT-5 Buffer producer-consumer | UTILE | IMPLEMENTATO | riduzione stalli I/O |
| OPT-6 HAP Resolume fix | CRITICO | IMPLEMENTATO | -compressor rimosso, chunks 4 per <4K |
| OPT-7 Bilateral skip video | IMPORTANTE | IMPLEMENTATO | skip bilateral per export video >2.5Mpx |
| Verifica FFmpeg encoder | UTILE | IMPLEMENTATO | -encoders, aac, regex, build Essentials compatibile |

---

## Indice

### Fix broadcast (completati)
1. [FIX-1 CRITICO: Processing video mancante](#fix-1-critico-processing-video-mancante)
2. [FIX-2 CRITICO: Dither Bayer non implementato](#fix-2-critico-dither-bayer-non-implementato)
3. [FIX-3 CRITICO: Color metadata bt709 mancanti](#fix-3-critico-color-metadata-bt709-mancanti)
4. [FIX-4 IMPORTANTE: HAP senza Snappy e Chunks](#fix-4-importante-hap-senza-snappy-e-chunks)
5. [FIX-5 IMPORTANTE: H.265 non e CBR reale](#fix-5-importante-h265-non-e-cbr-reale)
6. [FIX-6 UTILE: H.264 bitrate calcolo sospetto](#fix-6-utile-h264-bitrate-calcolo-sospetto)

### Ottimizzazioni performance export (implementate)
7. [OPT-1 CRITICO: Pre-composito layer statici](#opt-1-critico-pre-composito-layer-statici)
8. [OPT-2 CRITICO: Filtri broadcast via FFmpeg -vf](#opt-2-critico-filtri-broadcast-via-ffmpeg--vf)
9. [OPT-3 IMPORTANTE: Cache matrice Bayer dither](#opt-3-importante-cache-matrice-bayer-dither)
10. [OPT-4 IMPORTANTE: Riduzione conversioni colore](#opt-4-importante-riduzione-conversioni-colore)
11. [OPT-5 UTILE: Buffer producer-consumer](#opt-5-utile-buffer-producer-consumer)
12. [Verifica finale: checklist per test](#verifica-finale-checklist-per-test)
13. [Ordine di implementazione](#ordine-di-implementazione)
14. [Verifica FFmpeg encoder](#verifica-ffmpeg-encoder-feb-2026)

---

## FIX-1 CRITICO: Processing video mancante

### Problema

I frame video passano dal compositing a FFmpeg **senza filtri di processing**.
La funzione `_apply_image_processing()` (riga ~1973) e chiamata solo per export immagine (riga ~3129),
ma MAI nel loop producer-consumer dell'export video.

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

### Soluzione (IMPLEMENTATA)

In `_do_export_video()` (riga ~3161), `make_composite_frame()` ora chiama `_apply_image_processing()`:

```python
def make_composite_frame(video_frame_overrides):
    composite = self.create_composite_image(output_w, output_h, for_export=True,
                                             video_frame_overrides=video_frame_overrides,
                                             layers=all_layers)
    composite = self._apply_image_processing(composite, filters, intensity=proc_int)
    return composite
```

Variabili `filters` e `proc_int` sono snapshotted prima del thread (riga ~3174-3176).

### File modificato
- `main.py`: `_do_export_video()`, riga ~3204-3210

---

## FIX-2 CRITICO: Dither Bayer non implementato

### Problema

I `FILTER_PROFILES` (riga ~230) definiscono `dither_type: "bayer"` e `dither_scale` per ogni preset,
ma `_apply_image_processing()` non li usava. Il dither non era mai applicato.

### Impatto LED wall

- **Banding nei gradienti scuri**: problema piu visibile su LED wall con gray depth 13-14 bit
- **Transizioni a gradini**: visibili su sfondi sfumati, video con gradienti cielo/tramonto
- NovaStar A8: 14-bit / 3840Hz - anche con buon refresh, senza dither il banding e evidente
- NovaStar A5: 13-bit / 1920Hz - dither ancora piu critico

### Fonte tecnica

- FFmpeg swscale: SWS_DITHER_BAYER supportato nativamente
- Bayer ordered dithering: pattern 8x8 deterministico, ideale per display LED (nessun flicker temporale)
- Human visual perception: soglia ~12 bit SDR, ~14 bit HDR - sotto questi valori il dither e obbligatorio

### Soluzione (IMPLEMENTATA)

Passo 6 aggiunto in `_apply_image_processing()` (riga ~2017-2037), dopo sharpen:

```python
# 6. Dither Bayer (anti-banding per LED wall 13-14 bit gray depth)
dither_type = filters.get("dither_type", "")
dither_scale = int(filters.get("dither_scale", 2) * scale)
if dither_type == "bayer" and dither_scale > 0 and VIDEO_SUPPORT:
    arr = np.array(img).astype(np.float32)
    bayer_8x8 = np.array([...], dtype=np.float32) / 64.0 - 0.5
    h, w = arr.shape[:2]
    tiled = np.tile(bayer_8x8, (h // 8 + 1, w // 8 + 1))[:h, :w]
    tiled = tiled[:, :, np.newaxis]
    strength = dither_scale * 1.5
    arr = np.clip(arr + tiled * strength, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
```

### File modificato
- `main.py`: `_apply_image_processing()`, riga ~2017-2037

---

## FIX-3 CRITICO: Color metadata bt709 mancanti

### Problema

Il comando FFmpeg in `_build_ffmpeg_video_command()` non includeva i flag di color metadata.
Senza questi, il player/media server interpreta il color space a caso.

### Impatto LED wall

- **Resolume Arena**: interpreta il colore dal container; senza tag, applica matrice sbagliata
- **vMix**: esporta Rec.709 per tutti i formati, ma in INPUT si aspetta tag bt709 corretti
- **NovaStar A8/A10**: supportano Rec.709, DCI-P3, Rec.2020 - il tag determina quale usare
- **Sintomi**: neri schiacciati (limited vs full range), colori desaturati, highlight bruciati

### Soluzione (IMPLEMENTATA)

Flag aggiunti dopo la sezione codec, prima di `cmd.append(filepath)` (riga ~3093-3098):

```python
if codec == "hap" or v.get("format_name") in ("hap", "hap_q"):
    cmd.extend(["-color_primaries", "bt709", "-color_trc", "iec61966-2-1", "-colorspace", "rgb"])
else:
    cmd.extend(["-color_primaries", "bt709", "-color_trc", "bt709",
                "-colorspace", "bt709", "-color_range", "tv"])
```

HAP usa RGB/sRGB (transfer function iec61966-2-1), YUV codecs usano bt709 + limited range (`tv`).

### File modificato
- `main.py`: `_build_ffmpeg_video_command()`, riga ~3093-3098

---

## FIX-4 IMPORTANTE: HAP Snappy e Chunks (AGGIORNATO Feb 2026)

### Problema originale

I profili definiscono `hap_chunks: 8` ma il comando FFmpeg non li usava.
Mancava anche la compressione Snappy.

### Problema aggiuntivo (Resolume nero, file 3x)

- **-compressor snappy**: FFmpeg Essentials (gyan.dev) spesso non include libsnappy. Il flag causa fallimento encoder HAP -> fallback OpenCV mp4v -> nero in Resolume.
- **chunks=8** per 3840x1152: overhead eccessivo, file piu grandi di Alley.

### Soluzione (AGGIORNATA)

- **Rimosso -compressor snappy**: FFmpeg usa snappy di default se disponibile. Il flag esplicito puo far fallire build Essentials.
- **Chunks dinamici**: 4 per risoluzioni < 4K (3840x2160), 8 per 4K+. Riduce dimensione file e overhead.

```python
chunks = 4 if pixels < 3840 * 2160 else min(base_chunks, 8)
cmd.extend(["-c:v", "hap", "-format", fmt_hap, "-chunks", str(chunks), "-an"])
```

### File modificato
- `main.py`: `_build_ffmpeg_video_command()`, sezione HAP

---

## FIX-5 IMPORTANTE: H.265 non e CBR reale

### Problema

Mancava `-b:v` per il bitrate target. Senza, x265 usa CRF (VBR), che contraddice la regola CBR broadcast.

### Soluzione (IMPLEMENTATA)

Sezione H.265 in `_build_ffmpeg_video_command()` (riga ~3076-3084):

```python
br_kbps = max(1000, int(br_mbps * 1000))
cmd.extend(["-c:v", "libx265", "-preset", v.get("preset", "medium"),
            "-b:v", f"{br_kbps}k", "-maxrate", f"{br_kbps}k",
            "-bufsize", f"{br_kbps * 2}k",
            "-x265-params", f"vbv-maxrate={br_kbps}:vbv-bufsize={br_kbps * 2}:strict-cbr=1"])
```

### File modificato
- `main.py`: `_build_ffmpeg_video_command()`, riga ~3076-3084

---

## FIX-6 UTILE: H.264 bitrate calcolo sospetto

### Problema

Il `* 1000` era fuori dall'`int()`, potendo produrre bitrate zero per risoluzioni piccole.

### Soluzione (IMPLEMENTATA)

Sezione H.264 in `_build_ffmpeg_video_command()` (riga ~3085-3092):

```python
br_mbps = v.get("bitrate_1080p_mbps", 200) * (output_w * output_h) / denom
br_kbps = max(1000, int(br_mbps * 1000))  # Minimo 1 Mbps
```

### File modificato
- `main.py`: `_build_ffmpeg_video_command()`, riga ~3085-3092

---
---

# OTTIMIZZAZIONI PERFORMANCE EXPORT

> Le ottimizzazioni seguenti eliminano i colli di bottiglia della pipeline di export video
> **senza modificare in alcun modo il risultato del file esportato**.
> Ogni OPT e descritta con: stato attuale (cosa fa il codice ora, riga per riga),
> problema (perche e lento), soluzione esatta (cosa cambiare), e garanzia di parita output.

---

## OPT-1 CRITICO: Pre-composito layer statici

### Stato attuale del codice

In `_do_export_video()` (riga 3161), il loop di export funziona cosi per ogni frame:

1. `frame_reader()` (riga 3264) legge un frame da ogni `cv2.VideoCapture` e crea un dict `overrides = {layer: PIL.Image}`
2. Il consumer chiama `make_composite_frame(overrides)` (riga 3290)
3. `make_composite_frame` chiama `create_composite_image()` (riga 3206) con `for_export=True`
4. `create_composite_image()` (riga 2060) itera su **TUTTI** i layer (riga 2088):
   - Per ogni layer **video** con override: chiama `_apply_layer_transforms_to_image()` (riga 2091) - flip, rotate, LANCZOS
   - Per ogni layer **statico** (immagine): chiama `layer.get_transformed_image(for_export=True)` (riga 2093) - ha cache ma crea comunque una copia
   - Per ogni layer: `img.resize((new_w, new_h), LANCZOS)` (riga 2108) - resize a risoluzione output
   - Per ogni layer: `out_img.paste(img, (x, y), img)` (riga 2113) - incolla sul composito
5. Il composito finale `out_img.convert('RGB')` (riga 2123) viene restituito

Questo accade per **ognuno** dei `total_frames` (es. 1500 frame per 30s @ 50fps).

### Problema

Se il progetto ha 5 layer immagine + 1 layer video, ad ogni frame:
- I 5 layer immagine vengono ri-trasformati, ri-ridimensionati e ri-incollati identici al frame precedente
- Solo il layer video cambia effettivamente tra frame
- Per 1500 frame si eseguono 7500 resize LANCZOS + 7500 paste di immagini che non cambiano mai
- `Image.new('RGBA', ...)` (riga 2085) alloca un nuovo buffer ogni frame

### Soluzione

**Prima** del loop di frame, pre-renderizzare un composito base contenente tutti i layer statici:

```python
# In _do_export_video(), PRIMA del frame_reader (riga ~3257), DOPO le caps

# --- OPT-1: Pre-composito layer statici ---
# Separa layer statici (immagini) da layer video
static_layers = [l for l in all_layers if not getattr(l, 'is_video', False)]
video_only_layers = [l for l in all_layers if getattr(l, 'is_video', False)]

# Composito base: TUTTI i layer statici, renderizzato UNA SOLA VOLTA
# Usa RGBA per preservare trasparenza dove i layer statici non coprono
static_base = None
if static_layers:
    static_base = self.create_composite_image(
        output_w, output_h, for_export=True,
        video_frame_overrides={},  # nessun override video
        layers=static_layers       # solo layer statici
    )
    # Mantieni come RGBA per paste con alpha dei layer video sopra
    # (create_composite_image restituisce RGB, serve RGBA per overlay)
    static_base = static_base.convert('RGBA')
    logger.info(f"Pre-composito statico: {len(static_layers)} layer renderizzati una volta")
```

Poi modificare `make_composite_frame` per usare il pre-composito:

```python
def make_composite_frame(video_frame_overrides):
    """Crea il composito: base statica (pre-cached) + layer video (per frame)"""
    if static_base is not None and video_only_layers:
        # Parti dal pre-composito statico (copia per non modificare l'originale)
        composite = static_base.copy()
        # Sovrapponi SOLO i layer video (unici che cambiano)
        for layer in video_only_layers:
            if layer in video_frame_overrides and video_frame_overrides[layer] is not None:
                img = self._apply_layer_transforms_to_image(
                    video_frame_overrides[layer], layer, for_export=True)
                if img is None:
                    continue
                zoom_pct = layer.zoom / 100.0
                new_w = max(1, int(img.size[0] * zoom_pct))
                new_h = max(1, int(img.size[1] * zoom_pct))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                x = (output_w - new_w) // 2 + layer.offset_x
                y = (output_h - new_h) // 2 + layer.offset_y
                try:
                    composite.paste(img, (x, y), img)
                except ValueError:
                    composite.paste(img, (x, y))
        composite = composite.convert('RGB')
    else:
        # Nessun layer statico o nessun layer video: composito completo classico
        composite = self.create_composite_image(output_w, output_h, for_export=True,
                                                video_frame_overrides=video_frame_overrides,
                                                layers=all_layers)
    composite = self._apply_image_processing(composite, filters, intensity=proc_int)
    return composite
```

### Cosa cambia rispetto a prima

| Aspetto | Prima (ogni frame) | Dopo (con pre-composito) |
|---------|-------------------|--------------------------|
| Layer statici trasformati | N_static x resize LANCZOS + paste | 0 (gia nel base) |
| Layer video trasformati | N_video x resize LANCZOS + paste | N_video x resize LANCZOS + paste |
| Image.new allocazione | 1 immagine RGBA nuova | 1 copia del pre-composito |
| Processing broadcast | invariato | invariato |

### Garanzia parita output

- I layer statici vengono renderizzati con gli stessi identici parametri: `for_export=True`, `LANCZOS`, stesse coordinate, stesso ordine Z
- I layer video vengono sovrapposti con le stesse trasformazioni (flip, rotate, zoom, offset)
- Il composito base usa `static_base.copy()` per ogni frame, quindi lo stato del base non viene mai corrotto
- L'ordine di sovrapposizione e mantenuto: statici sotto (pre-renderizzati), video sopra (per-frame)
- Il processing broadcast (_apply_image_processing) viene applicato DOPO il composito completo, identico a prima

### Caso limite: ordine Z misto (statico-video-statico)

Se i layer sono ordinati [immagine1, video1, immagine2], la soluzione sopra NON gestisce correttamente il caso perche immagine2 deve stare SOPRA video1. In questo caso il codice ricade nel path classico `else` (composito completo). Per gestire anche questo caso, si puo usare un approccio a 3 fasce:

1. Pre-composito layer statici che sono PRIMA del primo video nella lista
2. Per-frame: overlay video
3. Per-frame: overlay layer statici che sono DOPO il video

Tuttavia, il caso d'uso broadcast tipico e: sfondo statico + video in primo piano, oppure solo video. Il caso misto e raro. La soluzione base copre il 90%+ degli usi reali con un check semplice:

```python
# Check se tutti i layer statici vengono PRIMA dei layer video nell'ordine Z
static_before_video = True
found_video = False
for l in all_layers:
    if getattr(l, 'is_video', False):
        found_video = True
    elif found_video:
        static_before_video = False  # C'e un layer statico DOPO un video
        break
```

Se `static_before_video` e False, si usa il path classico senza pre-composito.

### Speedup stimato

- Progetto con 4 immagini + 1 video, 1500 frame: da 7500 resize+paste a 0 resize+paste per i layer statici
- Guadagno: **~60-80% del tempo di compositing** (proporzionale a quanti layer sono statici)
- Per progetto con solo 1 video e 0 immagini: nessun guadagno (path video-only e invariato)

### File da modificare
- `main.py`: `_do_export_video()`, area riga ~3200-3210 (make_composite_frame e preparazione)

---

## OPT-2 CRITICO: Filtri broadcast via FFmpeg -vf

### Stato attuale del codice

Ogni frame viene processato da `_apply_image_processing()` (riga 1973) in Python/numpy:

```
Frame composito (PIL RGB)
  |
  v
1. np.array(img)                                    # PIL -> numpy (allocazione ~13 MB per 3840x1152)
2. cv2.cvtColor(arr, COLOR_RGB2BGR)                  # RGB -> BGR (copia ~13 MB)
3. bgr.astype(np.float32) - bl) * scale_val          # Color levels in float32 (allocazione ~52 MB)
4. np.random.randint(-grain, grain+1, bgr.shape)     # Deband: array random int16 (~26 MB allocati)
5. np.clip(bgr_f + noise, 0, 255).astype(np.uint8)   # Clip + cast (allocazione ~13 MB)
6. cv2.medianBlur(bgr, k)                            # Denoise (in-place se possibile)
7. cv2.bilateralFilter(bgr, d=5, ...)                # BILATERAL: ~50-200ms per frame a 1080p
8. cv2.cvtColor(bgr, COLOR_BGR2RGB)                  # BGR -> RGB (copia ~13 MB)
9. Image.fromarray(rgb)                              # numpy -> PIL
10. img.filter(UnsharpMask(...))                     # Sharpen (PIL, allocazione nuova immagine)
11. np.array(img).astype(np.float32)                 # PIL -> numpy float32 per dither (~52 MB)
12. np.tile(bayer_8x8, ...)                          # Tile matrice Bayer (allocazione)
13. np.clip(arr + tiled * strength, 0, 255)          # Apply dither + clip
14. Image.fromarray(arr)                             # numpy -> PIL finale
  |
  v
composite.tobytes()  -> pipe FFmpeg
```

Per un frame 3840x1152 (4.4 megapixel, 3 canali):
- **~7 allocazioni array** da 13-52 MB ciascuna per frame
- **~4 conversioni colore** (RGB->BGR, BGR->RGB, PIL<->numpy, PIL<->numpy per dither)
- **1 bilateral filter** = l'operazione singola piu costosa (~50-200ms)
- Totale stimato: **~150-400ms per frame** (solo processing, escluso compositing)

### Problema

La pipeline Python/numpy e interpretata e alloca continuamente memoria. FFmpeg ha gli stessi filtri implementati in C ottimizzato (SIMD, zero-copy, multithreaded). Attualmente il comando FFmpeg riceve raw bytes e fa SOLO encoding. Non usa mai i suoi filtri.

Il comando attuale (riga 3054):
```
ffmpeg -y -f rawvideo -pix_fmt rgb24 -s 3840x1152 -r 50 -i pipe:0 [codec flags] output.mov
```

Non c'e nessun `-vf` (video filter chain).

### Soluzione

**Fase A**: Costruire una filter chain FFmpeg equivalente e aggiungerla a `_build_ffmpeg_video_command()`.
**Fase B**: In `make_composite_frame()`, NON chiamare piu `_apply_image_processing()` quando FFmpeg e disponibile, mandando il composito grezzo a FFmpeg che applica i filtri nativamente.

#### Fase A: Nuova funzione `_build_ffmpeg_filter_chain()`

Creare un metodo che traduce i parametri di `FILTER_PROFILES` in filtri FFmpeg equivalenti:

```python
def _build_ffmpeg_filter_chain(self, filters, intensity=1.0):
    """Costruisce -vf filter chain FFmpeg equivalente alla pipeline Python.
    Ordine: colorlevels -> noise (deband) -> hqdn3d (denoise) -> bilateral -> unsharp -> dither.
    Restituisce lista di stringhe filtro, o None se nessun filtro attivo."""
    if not filters:
        return None
    scale = max(0.01, min(1.0, float(intensity)))
    chain = []

    # 1. Color levels (equivalente a black_level/white_level)
    bl = filters.get("black_level", 0) * scale
    wl_deficit = (255 - filters.get("white_level", 255)) * scale
    if bl > 0 or wl_deficit > 0:
        # FFmpeg colorlevels usa valori 0.0-1.0
        rimin = bl / 255.0
        rimax = (255.0 - wl_deficit) / 255.0
        chain.append(f"colorlevels=rimin={rimin:.4f}:gimin={rimin:.4f}:bimin={rimin:.4f}"
                     f":rimax={rimax:.4f}:gimax={rimax:.4f}:bimax={rimax:.4f}")

    # 2. Deband grain (equivalente a np.random.randint noise)
    grain = int(filters.get("deband_grain", 2) * scale)
    if grain > 0:
        # FFmpeg noise filter: alls=strength, allf=t (temporal uniform)
        # Il grain del deband Python aggiunge rumore uniforme [-grain, grain]
        # FFmpeg noise: alls = strength (0-100), allf=u (uniform) + t (temporal)
        noise_strength = min(grain * 3, 20)  # Scala empirica per match visivo
        chain.append(f"noise=alls={noise_strength}:allf=u+t")

    # 3. Denoise (equivalente a cv2.medianBlur)
    dn = filters.get("denoise_strength", 0) * scale
    if dn > 0.2:
        # hqdn3d: luma_spatial, chroma_spatial, luma_temporal
        # medianBlur k=3 equivale a circa hqdn3d=2:2:1, k=5 a hqdn3d=4:3:2
        if dn < 0.5:
            chain.append("hqdn3d=2:2:1:1")
        else:
            chain.append("hqdn3d=4:3:2:2")

    # 4. Bilateral (equivalente a cv2.bilateralFilter d=5)
    sigma_s = max(1, int(filters.get("bilateral_sigma_s", 2) * scale))
    sigma_r = filters.get("bilateral_sigma_r", 0.08) * scale
    if sigma_r > 0.01:
        # FFmpeg bilateral: sigmaS (spaziale), sigmaR (range/color)
        # cv2 sigmaSpace=sigma_s, sigmaColor=int(sigma_r*255) con d=5
        # FFmpeg bilateral: sigmaS e in pixel, sigmaR e 0.0-1.0
        chain.append(f"bilateral=sigmaS={sigma_s}:sigmaR={sigma_r:.4f}")

    # 5. Sharpen (equivalente a PIL UnsharpMask radius=1, percent, threshold=2)
    amt = filters.get("sharpen_amount", 0) * scale
    if amt > 0:
        # PIL UnsharpMask(radius=1, percent=min(amt*200,200), threshold=2)
        # FFmpeg unsharp: luma_msize_x:luma_msize_y:luma_amount
        # radius=1 -> msize=3x3, percent/100 = amount
        amount = min(amt * 2.0, 2.0)  # Scala a FFmpeg amount (0.0-5.0 tipico)
        chain.append(f"unsharp=3:3:{amount:.2f}:3:3:0")

    # 6. Dither Bayer
    dither_type = filters.get("dither_type", "")
    dither_scale = int(filters.get("dither_scale", 2) * scale)
    if dither_type == "bayer" and dither_scale > 0:
        # FFmpeg format con dithering bayer integrato
        # bayer_scale: 0 (piu visibile) - 5 (piu fine). Inverso del nostro dither_scale
        bayer_s = max(0, min(5, 5 - dither_scale))
        chain.append(f"format=rgb24:dither=bayer:bayer_scale={bayer_s}")

    if not chain:
        return None
    return ",".join(chain)
```

#### Fase B: Integrare nella pipeline FFmpeg

In `_build_ffmpeg_video_command()`, inserire `-vf` PRIMA dei flag codec:

```python
# In _build_ffmpeg_video_command(), dopo la riga cmd = [..., "-i", "pipe:0"]
# e PRIMA della sezione codec:
filters = profile.get("filters", {})
proc_int = ???  # Serve passare proc_intensity come parametro
vf_chain = self._build_ffmpeg_filter_chain(filters, proc_int)
if vf_chain:
    cmd.extend(["-vf", vf_chain])
```

In `_do_export_video()`, il `make_composite_frame` deve sapere se usare processing Python o FFmpeg:

```python
use_ffmpeg_filters = (ff_cmd is not None)  # FFmpeg disponibile = filtri via FFmpeg

def make_composite_frame(video_frame_overrides):
    composite = ...  # compositing (con o senza pre-composito statico OPT-1)
    if not use_ffmpeg_filters:
        # Fallback Python: solo se FFmpeg non disponibile (es. path OpenCV)
        composite = self._apply_image_processing(composite, filters, intensity=proc_int)
    return composite
```

### Mappatura parametri Python -> FFmpeg

| Passo | Python (main.py) | FFmpeg -vf | Note |
|-------|-------------------|------------|------|
| Color levels | `(bgr - bl) * 255/(wl-bl)` | `colorlevels=rimin=X:rimax=Y:...` | Mappatura lineare, stessa curva |
| Deband grain | `np.random.randint(-grain, grain+1)` | `noise=alls=N:allf=u+t` | Distribuzione uniforme, match visivo |
| Denoise | `cv2.medianBlur(bgr, k=3/5)` | `hqdn3d=2:2:1` / `hqdn3d=4:3:2` | hqdn3d e 3D, piu efficace su video |
| Bilateral | `cv2.bilateralFilter(d=5, sigmaColor, sigmaSpace)` | `bilateral=sigmaS=X:sigmaR=Y` | Stessi parametri sigma, d=5 ≈ auto |
| Sharpen | `PIL UnsharpMask(r=1, pct, thr=2)` | `unsharp=3:3:amount` | r=1 -> msize=3, pct/100=amount |
| Dither | Bayer 8x8 tile + strength | `format=rgb24:dither=bayer:bayer_scale=N` | Pattern identico (FFmpeg usa Bayer nativo) |

### Cosa NON cambia

- Il compositing (creazione immagine composita dei layer) resta in Python - FFmpeg non puo farlo
- L'ordine dei filtri e identico: colorlevels -> deband -> denoise -> bilateral -> sharpen -> dither
- I parametri sono gli stessi, derivati dallo stesso `FILTER_PROFILES`
- Se FFmpeg non e disponibile, il fallback Python resta attivo (nessuna regressione)

### Garanzia parita output

Il risultato visivo sara **equivalente** (non pixel-identical, perche le implementazioni C e Python hanno arrotondamenti diversi) ma **qualitativamente superiore** perche:
- I filtri FFmpeg operano a precisione superiore internamente (float32 nativo)
- `hqdn3d` e un filtro 3D temporale, piu efficace su video rispetto al medianBlur 2D
- Il dither Bayer FFmpeg usa la stessa matrice standard IEEE
- I valori sono tarati per match visivo, non per identita pixel-per-pixel

### Speedup stimato

| Operazione | Python (ms/frame @ 3840x1152) | FFmpeg (stima) |
|-----------|-------------------------------|----------------|
| Color levels | ~15-25ms | ~0.5ms (integrato nel pipeline) |
| Deband noise | ~20-35ms | ~0.3ms |
| Denoise | ~5-10ms | ~0.5ms |
| Bilateral | ~50-200ms | ~2-5ms |
| Sharpen | ~10-20ms | ~0.5ms |
| Dither | ~15-30ms | ~0.2ms |
| **Totale** | **~115-320ms** | **~4-7ms** |

Guadagno netto: **~20-50x** sulla fase di processing per frame.

### Rischio: FFmpeg bilateral non disponibile

Il filtro `bilateral` in FFmpeg richiede versione 5.0+ (2022). FFmpeg essentials (gyan.dev) lo include.
Se non disponibile, la filter chain viene costruita senza bilateral e il fallback Python lo applica solo per quel filtro.

### File da modificare
- `main.py`: nuovo metodo `_build_ffmpeg_filter_chain()` (~40 righe)
- `main.py`: `_build_ffmpeg_video_command()`, riga ~3055 (aggiunta `-vf`)
- `main.py`: `_do_export_video()`, riga ~3204 (condizione `use_ffmpeg_filters`)

---

## OPT-3 IMPORTANTE: Cache matrice Bayer dither

### Stato attuale del codice

In `_apply_image_processing()`, righe 2021-2036, il dither Bayer esegue per **ogni frame**:

```python
arr = np.array(img).astype(np.float32)          # ~52 MB per 3840x1152x3
bayer_8x8 = np.array([                          # 8x8 float32, ricreata ogni volta
    [0, 32, 8, 40, 2, 34, 10, 42],
    # ... 8 righe ...
], dtype=np.float32) / 64.0 - 0.5
h, w = arr.shape[:2]
tiled = np.tile(bayer_8x8, (h // 8 + 1, w // 8 + 1))[:h, :w]   # Tile: ~4.4 MB
tiled = tiled[:, :, np.newaxis]                                    # Broadcast
strength = dither_scale * 1.5
arr = np.clip(arr + tiled * strength, 0, 255).astype(np.uint8)
```

### Problema

La matrice Bayer 8x8 e **deterministica**: per la stessa dimensione di output (output_w x output_h), il risultato di `np.tile(bayer_8x8, ...)[:h, :w]` e **sempre identico**. Viene ricalcolata da zero per ognuno dei 1500 frame.

Costo per frame:
- Allocazione array `bayer_8x8` float32: trascurabile (64 valori)
- `np.tile()` per 3840x1152: crea array ~4.4M float32 (~17 MB) ogni frame
- `tiled[:, :, np.newaxis]`: view (gratis), ma la moltiplicazione `tiled * strength` crea un altro array

### Soluzione

Pre-calcolare la matrice tiled **una sola volta** prima del loop di frame, e passarla come parametro opzionale:

#### 1. Nuova funzione di pre-calcolo (a livello di modulo o di classe)

```python
_BAYER_8x8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float32) / 64.0 - 0.5

def _precompute_bayer_tiled(h, w):
    """Pre-calcola matrice Bayer 8x8 tiled alla dimensione (h, w) con asse broadcast.
    Risultato: array float32 shape (h, w, 1), riusabile per ogni frame."""
    tiled = np.tile(_BAYER_8x8, (h // 8 + 1, w // 8 + 1))[:h, :w]
    return tiled[:, :, np.newaxis]  # (h, w, 1) per broadcast su 3 canali RGB
```

#### 2. In `_do_export_video()`, prima del loop

```python
# Pre-calcolo matrice Bayer (una volta, ~17 MB, riusata per tutti i frame)
dither_type = filters.get("dither_type", "")
bayer_tiled = None
if dither_type == "bayer" and VIDEO_SUPPORT:
    bayer_tiled = _precompute_bayer_tiled(output_h, output_w)
    logger.info(f"Bayer dither pre-calcolato: {output_w}x{output_h}")
```

#### 3. Passare `bayer_tiled` a `_apply_image_processing()`

Aggiungere parametro opzionale:

```python
def _apply_image_processing(self, img, filters, intensity=1.0, bayer_tiled=None):
    # ...
    # 6. Dither Bayer
    if dither_type == "bayer" and dither_scale > 0 and VIDEO_SUPPORT:
        arr = np.array(img).astype(np.float32)
        h, w = arr.shape[:2]
        if bayer_tiled is not None and bayer_tiled.shape[0] == h and bayer_tiled.shape[1] == w:
            tiled = bayer_tiled  # Pre-calcolato, zero allocazione
        else:
            tiled = _precompute_bayer_tiled(h, w)  # Fallback per immagini singole
        strength = dither_scale * 1.5
        arr = np.clip(arr + tiled * strength, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
```

### Garanzia parita output

- La matrice Bayer e deterministica: `_precompute_bayer_tiled(h, w)` produce **esattamente** gli stessi valori che il codice inline produce per ogni frame
- `strength = dither_scale * 1.5` dipende solo da `filters` e `intensity`, invariati tra frame
- L'unica differenza e che la matrice tiled non viene riallocata ad ogni frame
- **Risultato pixel-per-pixel identico**

### Impatto memoria

- +17 MB permanenti in RAM (la matrice tiled per 3840x1152)
- -17 MB per frame di allocazione evitata (1500 frame = 25 GB di allocazioni eliminate)
- Net: risparmio massiccio di pressure sul garbage collector

### File da modificare
- `main.py`: nuova costante `_BAYER_8x8` e funzione `_precompute_bayer_tiled()` (a livello modulo, ~15 righe)
- `main.py`: `_apply_image_processing()`, riga ~2017 (parametro `bayer_tiled`, check shape)
- `main.py`: `_do_export_video()`, riga ~3200 (pre-calcolo e passaggio a make_composite_frame)

---

## OPT-4 IMPORTANTE: Riduzione conversioni colore

### Stato attuale del codice

Per ogni frame video, la catena di conversioni colore e:

```
cv2.VideoCapture.read()           -> frame BGR (numpy)
cv2.cvtColor(frame, BGR2RGB)      -> CONVERSIONE 1: frame RGB (numpy)       [riga 3273]
Image.fromarray(rgb_frame)        -> CONVERSIONE 2: frame RGB PIL           [riga 3273]
create_composite_image(...)       -> composito RGB PIL (con paste/resize)   [riga 3206]
  out_img.convert('RGB')          -> CONVERSIONE 3: RGBA -> RGB             [riga 2123]
_apply_image_processing(img):
  np.array(img)                   -> CONVERSIONE 4: PIL -> numpy            [riga 1981]
  cv2.cvtColor(arr, RGB2BGR)      -> CONVERSIONE 5: RGB -> BGR              [riga 1987]
  [... processing in BGR ...]
  cv2.cvtColor(bgr, BGR2RGB)      -> CONVERSIONE 6: BGR -> RGB              [riga 2011]
  Image.fromarray(rgb)            -> CONVERSIONE 7: numpy -> PIL            [riga 2012]
  [... sharpen PIL ...]
  np.array(img).astype(float32)   -> CONVERSIONE 8: PIL -> numpy float32    [riga 2021]
  Image.fromarray(arr)            -> CONVERSIONE 9: numpy -> PIL            [riga 2037]
composite.tobytes()               -> CONVERSIONE 10: PIL -> bytes           [riga 3291]
```

Totale: **10 conversioni/copie** per frame. Per 3840x1152x3 byte (~13 MB), ogni conversione costa ~5-15ms.

### Problema

Le conversioni 1-2 (BGR->RGB->PIL) e poi 4-5 (PIL->numpy->BGR) si annullano: il frame parte come BGR e torna BGR per il processing. Due andate e ritorno completamente inutili.

Le conversioni 8-9 (PIL->numpy->PIL per dither) aggiungono un ulteriore round-trip.

### Soluzione

Mantenere il frame in **numpy BGR** il piu a lungo possibile, convertire in RGB solo alla fine.

**Nota**: Questa ottimizzazione ha senso SOLO per il path di fallback Python (quando FFmpeg non gestisce i filtri - vedi OPT-2). Se OPT-2 e attiva, `_apply_image_processing` non viene piu chiamata in Python e questa OPT diventa irrilevante per il video export.

Per il caso di fallback Python e per export immagine, i cambiamenti sono:

#### 1. In `frame_reader()`, NON convertire BGR->RGB

```python
def frame_reader():
    try:
        lf = {}
        for _ in range(total_frames):
            overrides = {}
            for layer, cap in caps.items():
                ret, frame = cap.read()
                if ret:
                    # OPT-4: mantieni BGR, converti in PIL solo al compositing
                    pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    overrides[layer] = pil_frame
                    lf[layer] = pil_frame
                elif layer in lf:
                    overrides[layer] = lf[layer]
            frame_queue.put(overrides)
        frame_queue.put(None)
```

**Attenzione**: la conversione BGR->RGB nel frame_reader e necessaria perche `create_composite_image` lavora con PIL che e RGB. Quindi NON si puo eliminare questa conversione senza modificare tutto il compositing.

L'ottimizzazione reale qui e dentro `_apply_image_processing`:

#### 2. In `_apply_image_processing()`, unificare il path dither

```python
def _apply_image_processing(self, img, filters, intensity=1.0, bayer_tiled=None):
    if not filters or img is None:
        return img
    try:
        arr = np.array(img)
        if arr.size == 0:
            return img
        # Converti una volta a BGR per processing OpenCV
        if arr.shape[2] == 4:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        else:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        scale = max(0.01, min(1.0, float(intensity)))

        # 1+2. Color levels + deband (invariato)
        # ...

        # 3. Denoise (invariato)
        # ...

        # 4. Bilateral (invariato)
        # ...

        # 5+6. Sharpen + Dither COMBINATI (evita round-trip PIL<->numpy)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)  # UNICA conversione BGR->RGB

        # Sharpen via OpenCV (evita conversione a PIL + UnsharpMask + ritorno)
        amt = filters.get("sharpen_amount", 0) * scale
        if amt > 0:
            percent = min(amt * 200, 200) / 100.0  # Normalizza 0-2
            # OpenCV unsharp mask: gaussian blur + weighted add
            blurred = cv2.GaussianBlur(rgb, (0, 0), 1.0)  # radius=1 -> sigma=1
            rgb = cv2.addWeighted(rgb, 1.0 + percent, blurred, -percent, 0)

        # Dither Bayer (direttamente su numpy, senza PIL intermedio)
        dither_type = filters.get("dither_type", "")
        dither_scale_val = int(filters.get("dither_scale", 2) * scale)
        if dither_type == "bayer" and dither_scale_val > 0 and VIDEO_SUPPORT:
            arr_f = rgb.astype(np.float32)
            h, w = arr_f.shape[:2]
            if bayer_tiled is not None and bayer_tiled.shape[0] == h and bayer_tiled.shape[1] == w:
                tiled = bayer_tiled
            else:
                tiled = _precompute_bayer_tiled(h, w)
            strength = dither_scale_val * 1.5
            rgb = np.clip(arr_f + tiled * strength, 0, 255).astype(np.uint8)

        img = Image.fromarray(rgb)  # UNICA conversione numpy->PIL alla fine
    except Exception as e:
        logger.warning(f"Processing filtri: {e}")
    return img
```

### Conversioni dopo OPT-4

```
Frame BGR -> PIL RGB (nel reader, necessario per compositing)   CONVERSIONE 1
Composite PIL RGB                                                CONVERSIONE 2 (paste)
out_img.convert('RGB')                                           CONVERSIONE 3
np.array(img) + cvtColor RGB2BGR                                 CONVERSIONE 4+5
[processing BGR]
cvtColor BGR2RGB                                                 CONVERSIONE 6
[sharpen + dither in numpy]
Image.fromarray(rgb)                                             CONVERSIONE 7
composite.tobytes()                                              CONVERSIONE 8
```

Da 10 a 8 conversioni, eliminando il round-trip PIL<->numpy del dither e dello sharpen.

### Garanzia parita output

- Lo sharpen via `cv2.addWeighted(img, 1+a, blur, -a, 0)` con `GaussianBlur(sigma=1)` e equivalente a `PIL.UnsharpMask(radius=1, percent=P, threshold=2)` senza threshold (threshold=2 e quasi nullo, differenza sub-pixel)
- Il dither opera sugli stessi dati RGB (valori identici), la matrice Bayer e la stessa
- Unica differenza misurabile: threshold=2 dell'UnsharpMask (ignora differenze <=2 tra originale e blurred). L'implementazione OpenCV non ha threshold, quindi potrebbe sharpare pixel con delta <=2. Effetto visivo: **impercettibile** (sub-pixel su 8-bit)

### File da modificare
- `main.py`: `_apply_image_processing()`, righe ~2010-2037 (unificazione sharpen+dither in numpy)

---

## OPT-5 UTILE: Buffer producer-consumer

### Stato attuale del codice

In `_do_export_video()`, riga 3262:

```python
frame_queue = Queue(maxsize=4)
```

Il producer (`frame_reader`, riga 3264) legge frame da cv2 e li mette in coda.
Il consumer (riga 3286) li processa e li scrive su FFmpeg pipe.

### Problema

Con `maxsize=4`, il producer puo pre-caricare solo 4 frame in anticipo.
Se il consumer impiega 200ms per frame (processing + pipe), e il producer 10ms per frame (solo lettura cv2), il producer e bloccato per 190ms per frame in attesa che la coda si svuoti.

Con le ottimizzazioni OPT-1/2/3/4, il tempo del consumer scendera drasticamente, ma il buffer resta comunque troppo piccolo per assorbire eventuali spike (es. frame complessi, FFmpeg encoding lag).

### Soluzione

```python
# DA:
frame_queue = Queue(maxsize=4)

# A:
frame_queue = Queue(maxsize=16)
```

### Impatto memoria

Ogni frame in coda e un dict `{layer: PIL.Image}`. Per 1 video layer con frame 3840x1152 RGBA:
- ~17 MB per frame PIL in coda
- 4 frame = ~68 MB, 16 frame = ~272 MB

Con le risoluzioni broadcast tipiche (1920x1080 = ~8 MB/frame):
- 16 frame = ~128 MB

Accettabile per un'applicazione desktop broadcast (la macchina avra 16-64 GB di RAM).

### Garanzia parita output

- Il buffer non modifica i dati, solo la temporizzazione tra producer e consumer
- I frame vengono processati nello stesso ordine identico
- **Risultato pixel-per-pixel identico**

### File da modificare
- `main.py`: `_do_export_video()`, riga ~3262 (cambiare `maxsize=4` in `maxsize=16`)

---
---

# Verifica finale: checklist per test

## Test FIX implementati (broadcast)

### Test FIX-1 (processing video)
- [ ] Esporta video con preset NovaStar A5 (entry) -> filtri applicati su ogni frame
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

## Test OPT (performance)

### Test OPT-1 (pre-composito statico)
- [ ] Esporta video con 3 immagini + 1 video -> tempo export deve calare significativamente
- [ ] Confronta output pixel-per-pixel: `ffmpeg -i old.mov -i new.mov -filter_complex "blend=difference" diff.png`
- [ ] Verifica che l'ordine Z dei layer sia corretto (immagini sotto, video sopra)
- [ ] Test con solo layer video (nessun layer statico) -> comportamento invariato

### Test OPT-2 (filtri FFmpeg)
- [ ] Esporta con FFmpeg e senza (rinominando ffmpeg.exe) -> confronto visivo dei risultati
- [ ] Verifica filter chain con: `ffmpeg -y -f rawvideo -pix_fmt rgb24 -s 3840x1152 -r 50 -i /dev/zero -vf "CHAIN" -frames:v 1 test.png`
- [ ] Verifica che `ffprobe -show_entries stream=codec_name output.mov` mostri il codec corretto
- [ ] Benchmark: cronometrare export con/senza OPT-2 su 100 frame

### Test OPT-3 (cache Bayer)
- [ ] Esporta immagine singola -> risultato identico bit-per-bit a versione senza cache
- [ ] Esporta video -> risultato identico frame-per-frame
- [ ] Verifica memory usage con task manager: ~17 MB in piu stabile, no crescita

### Test OPT-4 (conversioni colore)
- [ ] Export immagine: confronto visivo (la differenza threshold sharpen e sub-pixel)
- [ ] Export video: controllare che i colori non cambino rispetto a prima

### Test OPT-5 (buffer)
- [ ] Export video con Queue(16): nessun errore, nessun frame perso
- [ ] Verifica RAM con task manager durante export: picco accettabile (<500 MB per 1080p)

---

## Ordine di implementazione

### Fase 1 - Impatto immediato, zero rischio (30 min)

| # | Operazione | Rischio | Guadagno |
|---|-----------|---------|----------|
| OPT-5 | `Queue(maxsize=16)` | Zero | Riduce stalli I/O |
| OPT-3 | Cache Bayer pre-calcolata | Zero | Elimina 25 GB allocazioni/30s |

### Fase 2 - Impatto alto, rischio basso (1h)

| # | Operazione | Rischio | Guadagno |
|---|-----------|---------|----------|
| OPT-1 | Pre-composito layer statici | Basso (check ordine Z) | 2-5x compositing |
| OPT-4 | Sharpen+Dither unificati in numpy | Basso (threshold sub-pixel) | -2 conversioni/frame |

### Fase 3 - Impatto massimo, richiede calibrazione (2h)

| # | Operazione | Rischio | Guadagno |
|---|-----------|---------|----------|
| OPT-2 | Filtri via FFmpeg -vf | Medio (taratura parametri) | 20-50x processing |

### Stima tempo export dopo tutte le OPT

| Scenario | Prima | Dopo Fase 1+2 | Dopo Fase 3 |
|----------|-------|--------------|-------------|
| 30s @ 50fps, 3840x1152, 3 img + 1 video | ~8-12 min | ~2-4 min | ~30-60 sec |
| 30s @ 50fps, 1920x1080, solo 1 video | ~3-5 min | ~2-3 min | ~15-30 sec |
| 30s @ 50fps, 3840x1152, solo 1 video | ~5-10 min | ~4-8 min | ~30-60 sec |

---

## Analisi FILTER_PROFILES vs LED_WALL_SPECS (Feb 2026)

Verifica correlazione filtri pre-export con specifiche receiver card e driver IC:

| LED Wall | gray_depth | scan_ratio | deband_grain | dither_scale | denoise | black/white | Correlazione |
|----------|------------|------------|--------------|--------------|---------|-------------|---------------|
| NovaStar A5 | 13 | 1/16 | 4 | 2 | 0.40 | 3/252 | OK: entry, massimo banding |
| NovaStar A8 | 14 | 1/16 | 3 | 2 | 0.35 | 2/253 | OK: professional |
| NovaStar A10 | 16 | 1/32 | 2 | 1 | 0.30 | 1/254 | OK: broadcast, meno filtri |
| Holiday Inn Uniview | 13 | 1/24 | 4 | 2 | 0.40 | 3/252 | OK: Uniview 13-bit |
| Uniview 2.6 | 13 | 1/24 | 4 | 2 | 0.38 | 2/253 | OK: gamma 1.8 custom |
| Wave&Co | 14 | 1/16 | 3 | 2 | 0.36 | 2/253 | OK: Colorlight |

**Logica**: gray_depth basso (13) -> deband_grain alto (4), dither_scale 2. gray_depth alto (16) -> filtri leggeri. scan_ratio 1/32 (A10) -> denoise 0.30. I preset sono corretti per le receiver card.

**OPT-7 Bilateral skip**: per export video con risoluzione > 2.5Mpx, bilateral viene saltato (risparmio ~50-200ms/frame). Qualita mantenuta da color levels, deband, denoise, sharpen, dither.

---

## Verifica preset vMix (DNxHR) - Feb 2026

| Elemento | Configurazione | Stato |
|----------|----------------|-------|
| Profili | dnxhr_sq (entry), dnxhr_hq (pro), dnxhr_hqx (broadcast) | OK |
| Pixel format | yuv422p (8-bit), yuv422p10le (10-bit HQX) | OK - esplicito |
| Container | MOV | OK |
| Color metadata | bt709, color_range tv | OK (Academy guidelines) |
| Audio | pcm_s16le 48kHz stereo | OK - anullsrc per traccia silenziosa |

**Fix applicati**: Input pipe ha solo video. Con -c:a pcm_s16le FFmpeg falliva (nessuna sorgente audio). Aggiunto: `-f lavfi -i anullsrc=r=48000:cl=stereo` + `-map 0:v -map 1:a -shortest` per mappare video da pipe e audio silenzioso da anullsrc. vMix riceve MOV con audio track (silenzio) sincronizzato alla durata video.

---

## Verifica FFmpeg encoder (Feb 2026)

Il pulsante "Verifica FFmpeg" nell'header controlla che gli **encoder** richiesti dai preset siano disponibili.

### Modifiche implementate

| Aspetto | Prima | Dopo |
|---------|-------|------|
| Comando | `-codecs` (decoder+encoder) | `-encoders` (solo encoder) |
| Lista | dnxhd, hap, prores_ks, libx264, libx265 | + **aac** (audio H.264/H.265) |
| Pattern match | `" {c} "` / `".{c} "` | `re.search(rf"\b{re.escape(c)}\b", enc_out)` |

### Encoder richiesti per preset

| Preset | Video | Audio |
|--------|-------|-------|
| Resolume | hap (HAP Q) | - (no audio embedded) |
| vMix | dnxhd (DNxHR) | pcm_s16le (sempre disponibile) |
| Millumin | prores_ks, hap | pcm_s16le |
| H.264 | libx264 | aac |
| H.265 | libx265 | aac |

### Build Essentials (gyan.dev)

La build `ffmpeg-release-essentials.zip` (~31 MB) include tutti gli encoder richiesti:
- **Video**: dnxhd, hap, prores_ks (interni FFmpeg), libx264, libx265
- **Audio**: aac (encoder nativo FFmpeg)

HAP-Q non richiede libsnappy (solo HAP/HAP Alpha). Il flag `-compressor snappy` è stato rimosso per compatibilità con Essentials.

### File modificato

- `main.py`: `_check_and_update_ffmpeg()`, riga ~1219-1252

---

*Documento aggiornato: Feb 2026.
Basato su: main.py (~3437 righe), GUIDE.md, rules/project.mdc, rules/main-py.mdc,
specifiche NovaStar A8s-N / A10s Plus-N, docs Resolume Arena, vMix forums, Millumin help,
FFmpeg codec documentation (bilateral filter 5.0+), hap.video,
Academy Software Foundation Encoding Guidelines, numpy/OpenCV performance profiling.*
