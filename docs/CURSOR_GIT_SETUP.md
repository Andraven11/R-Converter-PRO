# Cursor - Setup Git Autonomo

## Comando standard (quando l'AI fa commit e push)

```bash
git add -A && git commit -m "chore: descrizione" && git push
```

## Configurazione

1. **Permessi CLI**: `.cursor/cli.json` contiene `Shell(git)`
2. **Impostazioni Cursor**: "Allow Git Writes Without Approval" = true
3. **Prima volta**: approvare l'accesso rete quando richiesto
4. **Estensioni**: nessuna. Git nel PATH.
