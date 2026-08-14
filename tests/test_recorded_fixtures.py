"""Jeder externe Datensatz, gefahren aus einer aufgezeichneten Antwort.

Die handgeschriebenen CSVs in `conftest.py` bleiben: sie kodieren bewusste
Szenarien, an denen die uebrigen Tests konkrete Werte pruefen. Was sie nicht
koennen, ist belegen, dass ihre Satzform noch die der Quelle ist — ein Stub
stimmt mit dem ueberein, was sein Autor annahm.

`test_die_handgeschriebenen_koepfe_stimmen_mit_der_quelle` schliesst genau diese
Luecke: er bindet die erfundenen Kopfzeilen an die aufgezeichneten. Benennt die
EFV eine Spalte um, faellt er — und damit auch die Szenario-Fixtures, statt
still weiterzulaufen.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re

import httpx
import pytest
import respx

from swiss_efv_mcp.client import DATASETS, EFVClient
from swiss_efv_mcp.server import budget_impl, headline_impl, institution_impl
from tests.conftest import BUDGET_CSV, HEADLINE_CSV, INSTITUTIONS_CSV
from tests.fixture_data import (
    fixture_header,
    fixture_rows,
    fixture_text,
    provenance,
    recorded_names,
)

# Jeder Datensatz, den dieser Server laedt, und die Aufzeichnung dazu.
DATENSAETZE = {
    "headline": "headline.csv",
    "budget": "budget.csv",
    "institutions": "institutions.csv",
}

# Die handgeschriebenen Gegenstuecke, an deren Kopfzeile die uebrigen Tests haengen.
HANDGESCHRIEBEN = {
    "headline": HEADLINE_CSV,
    "budget": BUDGET_CSV,
    "institutions": INSTITUTIONS_CSV,
}


def mount(key: str) -> None:
    """Serviert die Aufzeichnung unter der echten URL des Datensatzes."""
    respx.get(DATASETS[key].url).mock(
        return_value=httpx.Response(200, text=fixture_text(DATENSAETZE[key]))
    )


# --------------------------------------------------------------------------
# Herkunft
# --------------------------------------------------------------------------


def test_provenance_nennt_ein_brauchbares_aufnahmedatum():
    """Eine Aufzeichnung ohne Datum ist eine undatierte Behauptung ueber die Quelle."""
    match = re.search(r"Aufgezeichnet am \*\*(\d{4}-\d{2}-\d{2})\*\*", provenance())
    assert match, "PROVENANCE.md nennt kein Aufnahmedatum im erwarteten Format"
    when = dt.date.fromisoformat(match.group(1))
    assert when <= dt.datetime.now(dt.UTC).date(), "Aufnahmedatum liegt in der Zukunft"


def test_jede_fixture_steht_in_der_provenance():
    """Sonst waechst der Ordner und der Nachweis bleibt zurueck."""
    text = provenance()
    fehlend = [n for n in recorded_names() if f"## `{n}`" not in text]
    assert not fehlend, f"ohne Eintrag in PROVENANCE.md: {fehlend}"


def test_jeder_datensatz_hat_eine_aufzeichnung():
    """Bewacht die Regel selbst: eine aufgezeichnete Antwort je externem Datensatz."""
    fehlend = sorted(set(DATENSAETZE.values()) - set(recorded_names()))
    assert not fehlend, f"Datensaetze ohne Aufzeichnung: {fehlend}"
    assert set(DATENSAETZE) == set(DATASETS), "Registry und Aufzeichnungen laufen auseinander"


# --------------------------------------------------------------------------
# Die Bruecke zu den handgeschriebenen Szenario-Fixtures
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(DATENSAETZE))
def test_die_handgeschriebenen_koepfe_stimmen_mit_der_quelle(key):
    """Bindet die erfundenen Kopfzeilen an die aufgezeichneten.

    Ohne diese Zusicherung koennte die EFV eine Spalte umbenennen, ohne dass
    irgendetwas rot wird: die Szenario-Fixtures brachten ihre eigene Kopfzeile
    mit und stimmten damit sich selbst zu. Genau so blieb in `i14y-mcp` eine
    ganze Suite gruen, waehrend drei Tools leere Titel lieferten.
    """
    erfunden = next(csv.reader(io.StringIO(HANDGESCHRIEBEN[key])))
    aufgezeichnet = fixture_header(DATENSAETZE[key])
    assert erfunden == aufgezeichnet, (
        f"{key}: die handgeschriebene Kopfzeile weicht von der Quelle ab. "
        f"Nur erfunden: {[c for c in erfunden if c not in aufgezeichnet]}; "
        f"nur in der Quelle: {[c for c in aufgezeichnet if c not in erfunden]}"
    )


# --------------------------------------------------------------------------
# Die Datensaetze durch die echten Tools
# --------------------------------------------------------------------------


@respx.mock
async def test_headline_aus_der_aufzeichnung():
    rows = fixture_rows("headline.csv")
    # Abfrage aus der Aufzeichnung ableiten, nicht hineinschreiben: welche
    # Variable dort steht, entscheidet die Auswahlregel des Recorders.
    echte = next(r for r in rows if r["hh"] not in {"NA", ""})
    mount("headline")
    c = EFVClient()
    result = await headline_impl(
        c, variable=echte["variable"], household=echte["hh"], model=echte["model"]
    )
    assert result.points, "die Aufzeichnung liefert Datenpunkte"
    assert all(pt.year for pt in result.points)
    # `NA` steht in der Quelle fuer «fehlt» und wird von `_NULLISH` geraeumt.
    # Die Auswahlregel nimmt diese Zeile ausdruecklich mit; in den ersten
    # tausend Zeilen der Quelldatei kommt sie nicht vor.
    assert any(r["hh"] == "NA" or r["model"] == "NA" for r in rows), (
        "die Aufzeichnung soll den NA-Fall enthalten — Auswahlregel pruefen"
    )


@respx.mock
async def test_budget_deckt_alle_hierarchie_ebenen_ab():
    """Die Quelldatei beginnt ausschliesslich mit Ebene 1; die Auswahl nicht."""
    rows = fixture_rows("budget.csv")
    ebenen = sorted(int(r["category_level"]) for r in rows)
    assert ebenen[0] == 1
    assert ebenen[-1] == 8, "der Client parst bis Ebene 8 — die Aufzeichnung muss sie zeigen"
    erste = rows[0]
    mount("budget")
    c = EFVClient()
    result = await budget_impl(c, topic=erste["topic"], year=int(erste["year"]))
    assert result.items, "die Aufzeichnung liefert Positionen"


@respx.mock
async def test_institutions_aus_der_aufzeichnung():
    rows = fixture_rows("institutions.csv")
    assert len({r["departement"] for r in rows}) > 1, "mehr als ein Departement gehoert dazu"
    erste = rows[0]
    mount("institutions")
    c = EFVClient()
    result = await institution_impl(c, variable=erste["variable_name"])
    assert result.points, "die Aufzeichnung liefert Datenpunkte"
    assert {pt.departement for pt in result.points} - {None}, "Departemente sind abgebildet"
