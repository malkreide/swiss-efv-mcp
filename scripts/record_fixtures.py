#!/usr/bin/env python3
"""Zeichnet echte EFV-Antworten nach `tests/fixtures/` auf.

Warum: eine handgeschriebene Fixture kodiert die Annahme ihres Autors und kann
sie deshalb nicht widerlegen. In `i14y-mcp` blieb genau deshalb eine ganze Suite
gruen, waehrend drei Tools produktiv leere Titel lieferten — die Stubs hatten
einen Schluessel erfunden und stimmten dem Mapper zu statt der Quelle.

Die Quelldateien sind 0.5 bis 5 MB gross. Aufgezeichnet werden deshalb
Ausschnitte: **Kopfzeile unveraendert, Zeilen gewaehlt statt genommen.** Die
ersten Zeilen jeder Datei zeigen naemlich immer nur eine Variante — bei
`bundeshaushalt_de.csv` ausschliesslich Hierarchie-Ebene 1, obwohl der Client
bis Ebene 8 parst, und bei `main_extern.csv` keine einzige der `NA`-Zeilen, auf
die `_NULLISH` reagiert.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei schreibt dieses Skript nach
`tests/fixtures/PROVENANCE.md`. Neu aufzeichnen:

    python scripts/record_fixtures.py

Braucht Netzzugang zu `data.finance.admin.ch` und `efv.admin.ch`.
Entwicklungswerkzeug; weder das Paket noch die Testsuite importieren es.
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

DATA_FINANCE = "https://www.data.finance.admin.ch/static/assets/datasets"
DAM = "https://www.efv.admin.ch/dam/de/sd-web"

HEADLINE_URL = f"{DATA_FINANCE}/fs_dashboard/main_extern.csv"
BUDGET_URL = f"{DAM}/m9aWXSnsRvNO/bundeshaushalt_de.csv"
INSTITUTIONS_URL = f"{DAM}/LheAU2Ioeux7/institutionen_de.csv"


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "swiss-efv-mcp-recorder"})
    with urlopen(req, timeout=180) as resp:
        return resp.read().decode("utf-8")


def to_csv(fieldnames: list[str], rows: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def one_per(rows: list[dict[str, str]], key: str) -> list[dict[str, str]]:
    """Je eine Zeile pro vorkommendem Wert von `key`, in Reihenfolge des Auftretens."""
    seen: dict[str, dict[str, str]] = {}
    for row in rows:
        seen.setdefault(row.get(key, ""), row)
    return [seen[k] for k in sorted(seen)]


def richest(rows: list[dict[str, str]], group: tuple[str, ...], spread: str) -> tuple:
    """Die Gruppe, die die meisten verschiedenen `spread`-Werte traegt.

    Eine Auswahl quer durch alle Themen und Jahre deckt zwar jede Ebene ab, ist
    aber nicht abfragbar: die Tools filtern auf Thema und Jahr, und eine
    zusammengewuerfelte Menge liefert dann nichts. Gesucht ist deshalb die eine
    Gruppe, in der die ganze Bandbreite *zusammenhaengend* vorkommt.
    """
    buckets: dict[tuple, set[str]] = {}
    for row in rows:
        key = tuple(row.get(g, "") for g in group)
        buckets.setdefault(key, set()).add(row.get(spread, ""))
    return sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0]))[0][0]


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")
    entries: list[dict[str, Any]] = []
    print("Zeichne auf von data.finance.admin.ch und efv.admin.ch")

    def write(name: str, text: str, url: str, rule: str, total: int) -> None:
        (FIXTURES / name).write_text(text, encoding="utf-8")
        blob = text.encode("utf-8")
        entries.append(
            {
                "name": name,
                "url": url,
                "rule": rule,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "total": total,
            }
        )
        print(f"  ok  {name:<28} {len(blob):>7} B  (aus {total} Zeilen)")

    # --- headline: Hauptaggregate ---------------------------------------
    # Je eine Zeile pro `hh`-Wert. Das schliesst `NA` ein, auf das `_NULLISH`
    # reagiert und das in den ersten tausend Zeilen gar nicht vorkommt.
    raw = fetch(HEADLINE_URL)
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    variable, model = richest(rows, ("variable", "model"), "hh")
    kohaerent = [r for r in rows if r["variable"] == variable and r["model"] == model]
    picked = one_per(kohaerent, "hh")
    # Die NA-Zeile steht ausserhalb jeder Variable und muss eigens dazu.
    picked += [r for r in one_per(rows, "hh") if r["hh"] == "NA" and r not in picked]
    write(
        "headline.csv",
        to_csv(list(reader.fieldnames or []), picked),
        HEADLINE_URL,
        f"Kopfzeile unveraendert, {len(picked)} von {len(rows)} Zeilen: variable="
        f"{variable!r}, model={model!r} mit je einer Zeile je `hh`-Wert — zusammen"
        " abfragbar —, dazu die `NA`-Zeile, auf die `_NULLISH` reagiert",
        len(rows),
    )

    # --- budget: Gesamthaushalt, hierarchisch ---------------------------
    # Je eine Zeile pro `category_level`. Die ersten Zeilen der Datei sind
    # ausnahmslos Ebene 1; eine Kopfauswahl belegte die Tiefe also nie.
    raw = fetch(BUDGET_URL)
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    topic, year = richest(rows, ("topic", "year"), "category_level")
    kohaerent = [r for r in rows if r["topic"] == topic and r["year"] == year]
    picked = one_per(kohaerent, "category_level")
    write(
        "budget.csv",
        to_csv(list(reader.fieldnames or []), picked),
        BUDGET_URL,
        f"Kopfzeile unveraendert, {len(picked)} von {len(rows)} Zeilen: topic="
        f"{topic!r}, year={year} mit je einer Zeile je Hierarchie-Ebene — zusammen"
        " abfragbar; die Datei beginnt ausschliesslich mit Ebene 1",
        len(rows),
    )

    # --- institutions: Ausgaben nach Departement ------------------------
    raw = fetch(INSTITUTIONS_URL)
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    variable, year = richest(rows, ("variable_name", "year"), "departement")
    kohaerent = [r for r in rows if r["variable_name"] == variable and r["year"] == year]
    picked = one_per(kohaerent, "departement")
    picked += [r for r in one_per(kohaerent, "category_level") if r not in picked]
    write(
        "institutions.csv",
        to_csv(list(reader.fieldnames or []), picked),
        INSTITUTIONS_URL,
        f"Kopfzeile unveraendert, {len(picked)} von {len(rows)} Zeilen: variable_name="
        f"{variable!r}, year={year} mit je einer Zeile je Departement und je "
        "Hierarchie-Ebene — zusammen abfragbar",
        len(rows),
    )

    _write_provenance(recorded_at, entries)
    print(f"\nPROVENANCE.md geschrieben, Aufzeichnungsdatum {recorded_at}")
    return 0


def _write_provenance(recorded_at: str, entries: list[dict[str, Any]]) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}** von den beiden Quellen dieses Servers:",
        f"`{DATA_FINANCE}` und `{DAM}`.",
        "",
        "Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht",
        "mehr zu unterscheiden — die Datei sieht gleich aus.",
        "",
        "**Es sind Ausschnitte, keine Vollabzuege.** Die Quelldateien sind 0.5 bis",
        "5 MB gross. Aufgezeichnet ist je Datei die **unveraenderte Kopfzeile**",
        "und eine Auswahl Datenzeilen; keine Spalte wurde entfernt. Eine Fixture",
        "belegt damit die *Form* der Antwort und einen datierten Ausschnitt ihres",
        "Inhalts — nicht den Bestand. Aussagen ueber Vollstaendigkeit gehoeren in",
        "Live-Tests.",
        "",
        "**Die Zeilen sind gewaehlt, nicht genommen.** Die ersten Zeilen jeder",
        "Datei zeigen immer nur eine Variante: `budget.csv` beginnt ausschliesslich",
        "mit Hierarchie-Ebene 1, obwohl der Client bis Ebene 8 parst, und",
        "`headline.csv` enthaelt in den ersten tausend Zeilen keine einzige der",
        "`NA`-Zeilen, auf die `_NULLISH` reagiert. Eine Kopfauswahl haette beide",
        "Faelle nie belegt.",
        "",
        "Fehlerpfade — 404, Timeouts, maskierte 4xx — bleiben handgeschrieben.",
        "Die lassen sich nicht auf Zuruf aufzeichnen.",
        "",
    ]
    for e in entries:
        lines += [
            f"## `{e['name']}`",
            "",
            f"- **Quelle:** `{e['url']}`",
            f"- **Aufgezeichnet:** {recorded_at}",
            f"- **Auswahl:** {e['rule']}",
            f"- **Groesse:** {e['bytes']} B (Quelle: {e['total']} Datenzeilen)",
            f"- **SHA-256:** `{e['sha256']}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
