<!-- Teil des Swiss Public Data MCP Portfolios · https://github.com/malkreide -->

# swiss-efv-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-model--context--protocol-black)

> MCP-Server für die Schweizer Bundesfinanzen (EFV): Haushalt, Schulden, Prognosen sowie Ausgaben nach Aufgabengebiet und Institution.

[🇬🇧 English Version](README.md)

---

## Übersicht

Dieser Server schliesst die Fiskal-Lücke im Economics-&-Finance-Cluster des
Portfolios. `swiss-snb-mcp` deckt die Geldpolitik ab; `swiss-efv-mcp` ergänzt den
**Staatshaushalt** — Einnahmen, Ausgaben, Saldo und Schuldenquoten des Bundes
(inkl. Prognosen bis 2029), einen hierarchischen Haushalts-Drill-down sowie
Ausgaben nach Departement. Datenquelle ist die Eidgenössische Finanzverwaltung
(EFV) via opendata.swiss (OGD Schweiz).

Es handelt sich um ein **privates, institutionell unabhängiges** Projekt ohne Mandat.

## 🎯 Anchor Demo Query

> *«Wie hat sich der Bundessaldo seit der SNB-Zinswende 2022 entwickelt — und in
> welche Aufgabengebiete floss das Ausgabenwachstum?»*

```
fiscal_headline(variable="saldo", household="bund", year_from=2021)
fiscal_budget_breakdown(topic="Ausgaben nach Aufgabengebiet", level=2)
```

Quergelesen mit `swiss-snb-mcp` verbindet das den Zinszyklus mit dem
Bunddefizit — etwas, das keiner der beiden Server allein beantworten kann.

## Funktionen

- **`fiscal_headline`** — Einnahmen / Ausgaben / Saldo / Schuldenquoten über
  1990–2029, nach Haushalt (bund, ktn, gdn, staat, sv) und Modell (FS / GFS).
  Jeder Punkt trägt `is_projection`, damit Rechnung und Plan/Prognose eindeutig
  unterscheidbar sind.
- **`fiscal_budget_breakdown`** — hierarchischer Bundeshaushalt nach Thema
  (Ausgaben nach Art / nach Aufgabengebiet, Einnahmen, Bilanz, …).
- **`fiscal_by_institution`** — Ausgaben nach Departement / Verwaltungseinheit
  seit 2007 (Personalausgaben, Informatik, externe Dienstleistungen, Vollzeitstellen).
- **`fiscal_list_dimensions`** — gültige Parameterwerte entdecken.
- **`dump_status`** — Cache-Aktualität und Upstream-Zustand (Graceful Degradation).

## Voraussetzungen

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) / `uvx` (empfohlen) oder `pip`

## Installation

```bash
uvx swiss-efv-mcp            # Zero-Install (sobald auf PyPI publiziert)
# oder
pip install swiss-efv-mcp
```

## Verwendung / Quickstart

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "swiss-efv": {
      "command": "uvx",
      "args": ["swiss-efv-mcp"]
    }
  }
}
```

Cloud (SSE, z. B. Railway / Render):

```bash
TRANSPORT=sse PORT=8000 swiss-efv-mcp
```

## Konfiguration

| Env-Variable | Default   | Zweck                                     |
|--------------|-----------|-------------------------------------------|
| `TRANSPORT`  | `stdio`   | `stdio` (Claude Desktop) oder `sse` (Cloud) |
| `HOST`       | `0.0.0.0` | Bind-Host für SSE                         |
| `PORT`       | `8000`    | Bind-Port für SSE                         |

## Architektur-Entscheid

Dieser Server nutzt **Architektur C (Dump-first)**.

Begründung (live geprüft am 24.07.2026):
- Das FS/GFS-Dashboard der EFV hat **keine gefilterte Query-API**; es liefert
  statische CSV-Dumps, die das Frontend im Browser filtert.
- Drei kuratierte Files sind klein genug, um sie ganz zu holen und zu cachen
  (516 KB / 5 MB / 1 MB). Sie decken die Hauptaggregate, den hierarchischen
  Haushalt und die Institutionen-Sicht ab — also die beantwortbaren Fragen.
- Die Voll-Cubes (`standardauswertung.csv` 157 MB, `fir_art_funk.csv` 1,23 GB)
  sind für v0.1.0 **out of scope**; ein Laden pro Request ist nicht praktikabel.
  Eine spätere Phase 2 würde sie nach SQLite/Parquet vorverarbeiten.

Konsequenzen:
- Files werden mit 24-h-TTL im Speicher gecacht; ein veralteter Cache wird einer
  leeren Antwort vorgezogen, wenn der Upstream ausfällt.
- Retry mit exponentiellem Backoff für alle HTTP-Aufrufe; `dump_status` liefert
  immer einen auswertbaren Zustand.

```
                      ┌──────────────────────────────┐
   Claude / Agent ──▶ │  swiss-efv-mcp (FastMCP)      │
                      │  5 Tools · Pydantic-v2-Env.   │
                      └───────────────┬──────────────┘
                                      │ fetch + retry + TTL-Cache
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
   data.finance.admin.ch                          efv.admin.ch/dam
   fs_dashboard/main_extern.csv                   bundeshaushalt_de.csv
   (Hauptaggregate, 1990–2029)                    institutionen_de.csv
```

## Bekannte Einschränkungen

Live-Probe-Befunde (24.07.2026), ebenfalls in `CHANGELOG.md → Known findings`:

| Befund | Auswirkung |
|---|---|
| Endpoints liefern **HTTP 403 ohne Browser-User-Agent** | UA wird vom Client gesetzt; nicht entfernen |
| opendata.swiss-«CSV»-Links zeigen bei 2 Datensätzen auf eine **HTML-Landing-Page** | echte Files via DAM-Pfad (`/dam/de/sd-web/{id}/…`) aufgelöst; die opake ID kann bei Re-Upload rotieren |
| `NA` als Literal-String in `hh`/`model`/`source` | zentral zu `None` bereinigt |
| «Vorausschauend» ist **kein einzelnes Label**: Bund nutzt «Budget/financial plans», `staat` nutzt «Forecasts» | via `is_projection` abstrahiert |
| **Buchhaltungs-Naht 2022/2023** (Themen «bis 2022» vs. «ab 2023») | Zeitreihe hat einen Bruch; ein `note` markiert betroffene Themen |
| Detail-Cubes (157 MB / 1,23 GB) werden nicht ausgeliefert | Phase 2; vorerst die kuratierten Files nutzen |

## Projektstruktur

```
swiss-efv-mcp/
├── src/swiss_efv_mcp/
│   ├── client.py      # Dump-first-Datenschicht: Retry, UA, NA-Cleaning, TTL-Cache
│   ├── models.py      # Pydantic-v2-Envelopes (source + provenance)
│   ├── server.py      # 5 FastMCP-Tools + testbare *_impl-Funktionen
│   └── __main__.py    # duales stdio-/sse-Transport
└── tests/             # respx-Mock-Tests + @pytest.mark.live
```

## Testing

```bash
PYTHONPATH=src pytest -m "not live"   # CI: schnell, ohne Netzwerk
PYTHONPATH=src pytest -m live         # gegen die echten EFV-Endpoints
```

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

## Credits & Verwandte Projekte

- Daten: **Eidgenössische Finanzverwaltung EFV** via opendata.swiss (OGD Schweiz, frei nutzbar)
- Companion: [`swiss-snb-mcp`](https://github.com/malkreide) (Geldpolitik) — das Fiskal-/Geld-Paar
- Teil des **Swiss Public Data MCP Portfolios**

## Lizenz

MIT License — siehe [LICENSE](LICENSE)

## Autor

malkreide · [github.com/malkreide](https://github.com/malkreide)

> Disclaimer: privates Projekt, unabhängig von Arbeitgeber oder Institution. Keine Gewähr; die Zahlen sind nicht amtlich — für den offiziellen Gebrauch die EFV-Originale konsultieren.
