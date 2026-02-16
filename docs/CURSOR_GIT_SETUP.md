# Cursor - Setup Git Autonomo

Per permettere all'AI di eseguire `git add`, `commit` e `push` in autonomia senza intervento manuale.

## Configurazione richiesta

### 1. Permessi CLI (già configurati)

Il file `.cursor/cli.json` contiene già i permessi per `Shell(git)`.

### 2. Impostazioni Cursor

Apri **File → Preferenze → Impostazioni** (o `Ctrl+,`) e cerca:

| Impostazione | Valore | Scopo |
|--------------|--------|-------|
| **Cursor: Allow Git Writes Without Approval** | `true` | Permette commit senza conferma |
| **Cursor: Enable Auto Run** | `true` | Esegue comandi senza chiedere ogni volta |

Se non trovi queste voci, potrebbero essere in **Cursor Settings** (icona Cursor in basso a sinistra).

### 3. Approvazione manuale (prima volta)

La prima volta che l'AI esegue `git push`, Cursor potrebbe chiedere di approvare l'accesso alla rete. Clicca **Allow** o **Approva** per memorizzare la scelta.

### 4. Estensioni

Nessuna estensione aggiuntiva richiesta. Git deve essere installato e nel PATH di sistema.

## Verifica

Dopo la configurazione, l'AI dovrebbe poter:
- `git add -A`
- `git commit -m "messaggio"`
- `git push origin master`

senza richiedere la tua interazione.
