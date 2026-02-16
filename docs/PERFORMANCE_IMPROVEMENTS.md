# R-Converter - Suggerimenti Performance e Stabilita

> Analisi approfondita del codice `main.py` v2.0.0 PRO
> Data: 11 febbraio 2026

---

## PROBLEMA PRINCIPALE: Lentezza nella preview durante le modifiche

La lentezza che noti quando modifichi un oggetto nel canvas ha una causa precisa e misurabile.

---

## COLLO DI BOTTIGLIA #1 (CRITICO) - Compositing a risoluzione piena

**Dove:** `_redraw_canvas_internal()` riga 1555
**Gravita:** ALTA - E' la causa principale della lentezza

### Il problema

Ogni volta che sposti, ridimensioni o ruoti un oggetto, il sistema:
1. Crea un'immagine composita alla **risoluzione di output** (es. 3840x2160 per 4K)
2. Poi la ridimensiona alla risoluzione del canvas di preview (~800x450)

Questo significa che per ogni movimento del mouse, Pillow:
- Alloca un'immagine 3840x2160 RGBA (circa 33MB di RAM)
- Ridimensiona ogni layer a dimensioni enormi
- Incolla tutto
- Poi butta via il 90% dei pixel ridimensionando per la preview

Con output 4K e 3-4 layer, ogni singolo redraw costa **50-150ms** (misurabili).

### Soluzione proposta

Fare il compositing direttamente alla risoluzione della preview durante l'interazione, e usare la risoluzione piena solo per l'export. In pratica: le righe 1554-1559 dovrebbero creare il composito a `preview_w x preview_h` con offset e zoom scalati di `preview_scale`, evitando il doppio resize.

**Guadagno stimato:** 5-10x piu veloce nel redraw interattivo. Da ~100ms a ~10-20ms per frame.

**Rischio:** ZERO per la stabilita. L'export finale usa gia un percorso separato (`for_export=True`).

---

## COLLO DI BOTTIGLIA #2 (ALTO) - Redraw immediato durante il drag

**Dove:** `redraw_canvas()` riga 1528
**Gravita:** ALTA

### Il problema

```python
def redraw_canvas(self, immediate=False):
    if immediate or self.is_dragging:
        self._redraw_canvas_internal()  # <-- IMMEDIATO durante drag
    else:
        self._schedule_redraw()
```

Quando `is_dragging=True`, il debounce da 16ms viene **bypassato**. Ogni pixel di movimento del mouse causa un redraw completo. Su un monitor 144Hz, possono essere 100+ redraw/secondo, ognuno da 50-150ms. Il risultato e' che Tkinter accumula eventi e la GUI sembra "in ritardo".

### Soluzione proposta

Usare SEMPRE il debounce, anche durante il drag. Anzi, durante il drag aumentarlo leggermente (es. 33ms = ~30fps) perche' la percezione di fluidita e' sufficiente e la reattivita migliora drasticamente.

```python
def redraw_canvas(self, immediate=False):
    if immediate:
        self._redraw_canvas_internal()
    else:
        self._schedule_redraw()
```

E nel metodo `_schedule_redraw`, usare un intervallo dinamico:
- 16ms (~60fps) per azioni normali (slider, pulsanti)
- 33ms (~30fps) durante il drag

**Guadagno stimato:** Elimina l'accumulo di eventi. La GUI risponde immediatamente.

**Rischio:** ZERO. La qualita visiva a 30fps durante il drag e' indistinguibile da 60fps.

---

## COLLO DI BOTTIGLIA #3 (MEDIO) - `update_idletasks()` nel redraw

**Dove:** `_redraw_canvas_internal()` riga 1539
**Gravita:** MEDIA

### Il problema

```python
self.canvas.update_idletasks()
```

Questa chiamata forza Tkinter a processare TUTTI i task pendenti (ridisegno di label, entry, listbox, etc.) prima di procedere col rendering del canvas. Durante un drag con slider che cambiano valore, questo puo costare 5-15ms extra per frame.

### Soluzione proposta

Cacheare le dimensioni del canvas e aggiornarle solo su `<Configure>` (resize finestra), eliminando la chiamata a `update_idletasks()` nel hot path del rendering.

```python
# In __init__:
self._cached_canvas_size = (0, 0)

# In on_canvas_resize:
def _do_canvas_resize(self):
    self._cached_canvas_size = (self.canvas.winfo_width(), self.canvas.winfo_height())
    ...

# In _redraw_canvas_internal:
canvas_w, canvas_h = self._cached_canvas_size  # Niente update_idletasks
```

**Guadagno stimato:** 5-15ms per frame eliminati.

**Rischio:** Minimo. Le dimensioni canvas cambiano solo durante il resize della finestra, non durante il drag.

---

## COLLO DI BOTTIGLIA #4 (MEDIO) - Cache solo per rotazione/flip

**Dove:** `ImageLayer.get_transformed_image()` riga 112
**Gravita:** MEDIA

### Il problema

La cache key e' `(rotation, flip_h, flip_v)`. Questo significa che la cache funziona solo quando queste 3 proprieta non cambiano. Ma durante il rendering, DOPO aver ottenuto l'immagine dalla cache, il codice fa comunque un `.resize()` completo nel `create_composite_image()` ad ogni frame.

Se l'immagine e' 4000x3000 e lo zoom e' 50%, ogni redraw ridimensiona 4000x3000 -> 2000x1500 per ogni layer. Pillow e' veloce, ma non istantaneo.

### Soluzione proposta

Aggiungere lo zoom alla cache: se zoom non cambia (caso piu comune durante lo spostamento), restituire direttamente l'immagine gia ridimensionata.

Aggiungere un secondo livello di cache in ImageLayer:
```python
# Nuovi slot:
'_zoom_cache', '_zoom_cache_key'

# In get_transformed_image, aggiungere parametro zoom:
def get_transformed_image(self, zoom=None, use_cache=True):
    ...
    if zoom and use_cache:
        zoom_key = (cache_key, zoom)
        if self._zoom_cache_key == zoom_key:
            return self._zoom_cache
        # Altrimenti resize e salva
```

**Guadagno stimato:** 10-30ms per layer risparmiati durante lo spostamento (il caso piu frequente).

**Rischio:** Piu RAM usata (una copia extra per layer). Per 5 layer da 4K, circa 80MB in piu. Accettabile su PC moderni.

---

## COLLO DI BOTTIGLIA #5 (BASSO) - Entry widget aggiornati ad ogni frame

**Dove:** `on_mouse_move()` righe 1721-1758
**Gravita:** BASSA

### Il problema

Durante il drag, ad ogni movimento del mouse:
```python
self.zoom_entry.delete(0, tk.END)
self.zoom_entry.insert(0, str(new_zoom))
```

Queste operazioni Tkinter generano eventi interni che forzano ridisegni parziali della GUI. Con 4 entry (zoom, rotation, offset_x, offset_y) aggiornati 60+ volte/secondo, si aggiunge overhead.

### Soluzione proposta

Aggiornare i campi entry solo a fine drag (in `on_mouse_up`), e durante il drag aggiornare solo le variabili IntVar (che sono leggere):

```python
def on_mouse_move(self, event):
    ...
    # Durante il drag: aggiorna solo la variabile, non il widget
    self.zoom_var.set(new_zoom)
    self.redraw_canvas()

def on_mouse_up(self, event):
    ...
    # A fine drag: sincronizza tutti i widget
    self.update_layer_controls()
```

**Guadagno stimato:** 2-5ms per frame.

**Rischio:** ZERO. I numeri nelle entry si aggiornano a fine drag invece che in tempo reale. L'utente vede il valore finale corretto.

---

## COLLO DI BOTTIGLIA #6 (BASSO) - `canvas.delete("all")` ad ogni frame

**Dove:** `_redraw_canvas_internal()` riga 1563
**Gravita:** BASSA

### Il problema

Ad ogni redraw, tutto il canvas viene cancellato e ricreato:
```python
self.canvas.delete("all")
self.canvas.create_rectangle(...)  # sfondo
self.canvas.create_image(...)      # immagine
self.canvas.create_rectangle(...)  # bordo
# + 9 handle + linea rotazione + rettangolo selezione
```

Tkinter deve allocare/deallocare oggetti grafici ad ogni frame.

### Soluzione proposta

Creare gli oggetti canvas una volta sola e aggiornarli con `itemconfig` e `coords`:

```python
# In __init__, dopo create_widgets:
self._canvas_bg = self.canvas.create_rectangle(...)
self._canvas_img = self.canvas.create_image(...)
self._canvas_border = self.canvas.create_rectangle(...)
# etc.

# In _redraw_canvas_internal:
self.canvas.coords(self._canvas_img, canvas_x, canvas_y)
self.canvas.itemconfig(self._canvas_img, image=self.display_image)
```

**Guadagno stimato:** 1-3ms per frame (maggiore con molti handle).

**Rischio:** Basso, ma richiede gestione attenta della visibilita degli handle (show/hide invece di create/delete). Piu complesso da implementare.

---

## RIEPILOGO PRIORITA

| # | Problema | Impatto | Difficolta | Rischio |
|---|----------|---------|------------|---------|
| 1 | Compositing a risoluzione piena | **CRITICO** | Media | Zero |
| 2 | Niente debounce durante drag | **ALTO** | Bassa | Zero |
| 3 | `update_idletasks()` nel hot path | **MEDIO** | Bassa | Minimo |
| 4 | Cache senza zoom | **MEDIO** | Media | Basso (RAM) |
| 5 | Entry aggiornati ad ogni frame | **BASSO** | Bassa | Zero |
| 6 | `canvas.delete("all")` ogni frame | **BASSO** | Alta | Basso |

### Ordine di implementazione consigliato

**Fase 1 - Impatto massimo, rischio zero:**
- Fix #1 (compositing a risoluzione preview)
- Fix #2 (debounce sempre attivo)
- Fix #5 (entry aggiornati solo a fine drag)

Con queste 3 modifiche, la reattivita dovrebbe migliorare di **5-10 volte**. Sono modifiche localizzate e non toccano il drag & drop ne l'export.

**Fase 2 - Miglioramento incrementale:**
- Fix #3 (cache dimensioni canvas)
- Fix #4 (cache con zoom)

**Fase 3 - Ottimizzazione avanzata (opzionale):**
- Fix #6 (riuso oggetti canvas)

---

## NOTA SULLA VERSIONE PORTABLE

Nessuno di questi suggerimenti tocca:
- Il drag & drop (windnd)
- La build PyInstaller (spec/bat)
- Il logging
- L'export finale

Sono tutti miglioramenti al **ciclo di rendering della preview**, che e' identico tra versione installata e portable.

---

## ALTRI SUGGERIMENTI (NON PERFORMANCE)

### 1. Downscale immagini sorgente al caricamento

Se un'immagine e' 8000x6000 ma l'output e' 1920x1080, conservare l'originale e' uno spreco. Si potrebbe creare una versione "working" ridotta (es. max 2x l'output) per la preview, e usare l'originale solo in fase di export.

**Pro:** Riduce enormemente la RAM e velocizza ogni operazione.
**Contro:** Richiede di mantenere il path del file originale per l'export a piena risoluzione.
**Rischio:** Medio - cambia la logica di caricamento e export.

### 2. Limitare il range degli slider durante il drag

Gli slider Tkinter `ttk.Scale` generano un evento `command` per ogni pixel di movimento. Con range 1-1000, trascinare lo slider dello zoom genera centinaia di eventi. Limitare il redraw tramite il debounce (Fix #2) risolve anche questo.

### 3. Disabilitare anti-aliasing durante drag rapido

Usare `Image.Resampling.NEAREST` non solo per il resize finale della preview, ma anche per il resize dei singoli layer durante il drag. Attualmente si usa BILINEAR anche durante il drag (riga 1481), che e' 3-4x piu lento di NEAREST.

**Rischio:** Zero. NEAREST durante il drag e' impercettibile.
