---
name: browse
description: "Browser automation via ptbrowse CLI. Use for E2E testing and web interaction."
---

# /browse — PocketTeam Browser

Öffne einen echten headless Chromium für E2E-Tests und visuelle Prüfung.
Token-effizient: nutzt Accessibility-Tree Snapshots statt Screenshots (~100-300 Tokens pro Call).

## Quick Start

```bash
# Seite öffnen (startet Daemon automatisch)
bun run pocketteam/browse/index.ts goto http://localhost:3848

# Interaktive Elemente anzeigen
bun run pocketteam/browse/index.ts snapshot -i

# Element klicken
bun run pocketteam/browse/index.ts click @e3

# Warten + Prüfen
bun run pocketteam/browse/index.ts wait text "Dashboard"
bun run pocketteam/browse/index.ts assert text "PocketTeam Dashboard"

# Screenshot machen
bun run pocketteam/browse/index.ts screenshot

# Browser schließen
bun run pocketteam/browse/index.ts close
```

## Commands

### Navigation
| Command | Beschreibung |
|---|---|
| `goto <url>` | Navigiere zu URL |
| `back` | Browser zurück |
| `forward` | Browser vorwärts |
| `reload` | Seite neu laden |

### Snapshots
| Command | Beschreibung |
|---|---|
| `snapshot` | Vollständiger Accessibility-Tree mit @e Refs |
| `snapshot -i` | Nur interaktive Elemente (kompakt) |
| `snapshot -D` | Diff seit letztem Snapshot |
| `snapshot -c` | Kompakt einzeilig pro Element |

### Interaktion
| Command | Beschreibung |
|---|---|
| `click @e<n>` | Element per Ref klicken |
| `fill @e<n> "text"` | Input-Feld ausfüllen |
| `type @e<n> "text"` | Keystroke by keystroke tippen |
| `select @e<n> "value"` | Dropdown-Wert wählen |
| `key <Enter/Escape/Tab>` | Taste drücken |
| `hover @e<n>` | Element hovern |
| `scroll @e<n> down <px>` | Scrollen |

### Warten
| Command | Beschreibung |
|---|---|
| `wait text "string"` | Warte bis Text auf Seite erscheint |
| `wait selector "css"` | Warte bis DOM-Element existiert |
| `wait idle [ms]` | Warte bis Netzwerk ruhig (default 2000ms) |
| `wait url "pattern"` | Warte auf Navigation |

### Assertions
| Command | Beschreibung |
|---|---|
| `assert text "string"` | Exit 1 wenn Text nicht gefunden |
| `assert no-text "string"` | Exit 1 wenn Text gefunden |
| `assert visible @e<n>` | Exit 1 wenn nicht sichtbar |
| `assert enabled @e<n>` | Exit 1 wenn disabled |
| `assert url "pattern"` | Exit 1 wenn URL nicht matcht |

### Lesen
| Command | Beschreibung |
|---|---|
| `text` | Seitentext extrahieren (max 8k chars) |
| `screenshot [path]` | PNG Screenshot speichern |
| `console` | Browser-Console Logs |
| `eval "expression"` | JS im Page-Kontext ausführen |

### Meta
| Command | Beschreibung |
|---|---|
| `viewport <w> <h>` | Viewport-Größe ändern |
| `status` | Daemon-Status |
| `close` | Browser + Daemon beenden |

## Exit-Codes
- `0` — Erfolg
- `1` — Assertion fehlgeschlagen
- `2` — Element-Ref nicht gefunden (stale)
- `3` — Daemon nicht erreichbar / Timeout

## Tipps
- Nach `click`/`fill` immer `snapshot` für frische Refs aufrufen
- `snapshot -i` ist am token-günstigsten für Interaktions-Checks
- `snapshot -D` zeigt nur Änderungen — ideal nach Aktionen
- Screenshots gehen nach `.pocketteam/screenshots/`
- Daemon startet automatisch beim ersten Command, stoppt nach 30min Idle
