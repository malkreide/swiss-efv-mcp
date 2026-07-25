# Mitwirken

[🇬🇧 English Version](CONTRIBUTING.md)

Danke für dein Interesse an `swiss-efv-mcp`. Dies ist ein Read-only-MCP-Server
über die öffentlichen EFV-Dump-Files; Beiträge sollen das so belassen.

## Grundregeln

- **Read-only.** Jedes Tool bleibt read-only by design (nur HTTP GET). Keine
  Schreib-, Sende- oder Dateisystem-Fähigkeit.
- **Fixer Egress.** Anfragen gehen ausschliesslich an die fest kodierten
  EFV-Datensatz-URLs auf `data.finance.admin.ch` und `efv.admin.ch`;
  Tool-Argumente filtern gecachte Zeilen, sie bauen nie eine URL.
- **Keine Secrets.** Die Endpoints sind unauthentifiziertes öffentliches OGD;
  keine Credential-Verarbeitung hinzufügen.

## Entwicklung

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

PYTHONPATH=src pytest tests/ -m "not live"   # offline, respx-gemockt
PYTHONPATH=src pytest tests/ -m live         # gegen die echten EFV-Endpoints
ruff check src tests
```

## Pull Requests

- Tests für nutzersichtbare Änderungen ergänzen; `ruff check` und die
  Offline-Suite grün halten.
- Einen `CHANGELOG.md`-Eintrag unter `[Unreleased]` hinzufügen.
- Bei Doku-Änderungen sowohl `README.md` als auch `README.de.md` aktualisieren.
- Für Release/Publishing siehe [`PUBLISHING.md`](PUBLISHING.md).

## Sicherheitsprobleme melden

Siehe [`SECURITY.md`](SECURITY.md) — bitte privat melden, keine öffentlichen Issues.
