"""Die `source`-Spalte der EFV und ihre Abbildung auf `is_projection`.

Am 27.8.2026 veroeffentlichte die EFV `main_extern.csv` neu (Last-Modified
07:06 UTC) und stellte dabei die ganze Spalte von Englisch auf Deutsch um:
`Financial statements` wurde `Rechnung`, `Forecasts` wurde `Prognosen`,
`Data available` wurde `Vorhandene Daten`. Sonst aenderte sich nichts — gleiche
URL, gleiche Kopfzeile, gleiche sieben Spalten.

Damit fiel `is_projection` fuer **jede** der 6110 Zeilen auf `None` zurueck und
`fiscal_headline` kennzeichnete keinen Punkt mehr als Prognose. Kein einziger
Unit-Test sah es: Sie fahren auf handgeschriebenen und aufgezeichneten Zeilen,
beide englisch. Genau die Klasse, vor der `CLAUDE.md` warnt — produktiv kaputt,
alles gruen.

Diese Datei haelt beide Wortschaetze fest. Der englische ist kein Ballast: Die
Aufzeichnung vom 14.8.2026 traegt ihn noch, und eine Quelle, die einmal die
Sprache gewechselt hat, kann zurueckwechseln.

Was hier **nicht** steht, ist ebenso Absicht. Fuer vier der englischen Marken
ist die deutsche Entsprechung heute nicht in der Datei; sie wird deshalb auch
nicht erfunden. Ein ausgedachter String sieht aus wie ein gemessener und
behauptet eine Abdeckung, die niemand geprueft hat. Die naechste unbekannte
Marke benennt `test_live_source_vocabulary_is_fully_mapped` an dem Tag, an dem
sie auftaucht.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from swiss_efv_mcp.client import DATASETS, EFVClient, is_projection
from swiss_efv_mcp.server import headline_impl

# Gemessen am 29.8.2026 gegen
# `https://www.data.finance.admin.ch/static/assets/datasets/fs_dashboard/main_extern.csv`
# (413'725 B, Last-Modified 27.8.2026 07:06 UTC): genau vier verschiedene Werte
# stehen in der Spalte, `NA` mitgezaehlt.
#
#     Rechnung           5457 Zeilen
#     NA                  550
#     Prognosen            75
#     Vorhandene Daten     28
#
# Die Zahlen stehen als Datum der Messung dabei, nicht als Zusicherung: Ein
# Bestand gehoert in einen Live-Test, nicht in einen Unit-Test.
DEUTSCH_VORAUSSCHAUEND = ["Prognosen"]
DEUTSCH_ABGESCHLOSSEN = ["Rechnung", "Vorhandene Daten"]

# Der Wortschatz bis zum 27.8.2026, belegt durch `tests/fixtures/headline.csv`
# (aufgezeichnet am 14.8.2026) und die Live-Proben davor.
ENGLISCH_VORAUSSCHAUEND = ["Budget/financial plans", "Forecasts", "Survey budget"]
ENGLISCH_ABGESCHLOSSEN = [
    "Financial statements",
    "Provisional financial statements",
    "Data available",
    "Survey financial statements",
]


# --------------------------------------------------------------------------
# Die Abbildung selbst
# --------------------------------------------------------------------------


@pytest.mark.parametrize("marke", DEUTSCH_VORAUSSCHAUEND + ENGLISCH_VORAUSSCHAUEND)
def test_vorausschauende_marken_sind_prognosen(marke):
    assert is_projection(marke) is True, f"{marke!r} gilt als vorausschauend"


@pytest.mark.parametrize("marke", DEUTSCH_ABGESCHLOSSEN + ENGLISCH_ABGESCHLOSSEN)
def test_abgeschlossene_marken_sind_keine_prognosen(marke):
    assert is_projection(marke) is False, f"{marke!r} gilt als abgeschlossen"


def test_beide_wortschaetze_gelten_gleichzeitig():
    """Der englische darf beim Aufraeumen nicht mitgehen.

    Ohne diese Zusicherung koennte jemand die englischen Marken als «veraltet»
    entfernen — und damit die Aufzeichnung vom 14.8.2026 und jeden Rueckwechsel
    der Quelle stillschweigend unlesbar machen. Ein einzelner Test, der das
    Nebeneinander benennt, faellt dann sofort und mit dem Grund.
    """
    deutsch = {is_projection(m) for m in DEUTSCH_VORAUSSCHAUEND + DEUTSCH_ABGESCHLOSSEN}
    englisch = {is_projection(m) for m in ENGLISCH_VORAUSSCHAUEND + ENGLISCH_ABGESCHLOSSEN}
    assert None not in deutsch, "der deutsche Wortschatz ist nicht vollstaendig abgebildet"
    assert None not in englisch, "der englische Wortschatz ist verloren gegangen"


def test_unbekannte_marke_bleibt_none():
    """Dokumentiert die Luecke, die den Live-Waechter noetig macht.

    `None` heisst hier «diese Zeile sagt nichts» — und sagt genau deshalb nicht,
    ob die Quelle geschwiegen oder ihre Taxonomie verschoben hat. Der Unterschied
    ist von hier aus nicht zu sehen; er wird gegen die echte Datei entschieden,
    in `test_live_source_vocabulary_is_fully_mapped`.
    """
    assert is_projection("Voranschlag/Finanzplan") is None
    assert is_projection("") is None  # `_NULLISH`
    assert is_projection("NA") is None  # `_NULLISH`
    assert is_projection(None) is None


# --------------------------------------------------------------------------
# Durch das echte Tool, nicht nur durch die Funktion
# --------------------------------------------------------------------------

# Satzform woertlich aus der Quelle vom 29.8.2026: gleiche Kopfzeile wie die
# Aufzeichnung, nur die Marken auf Deutsch. `staat` traegt heute die einzige
# `Prognosen`-Zeile der Reihe, `bund` ausschliesslich `Rechnung`.
DEUTSCHES_HEADLINE_CSV = (
    '"","hh","model","variable","jahr","value","source"\n'
    '"1","bund","fs","saldo","2023","1000.0","Rechnung"\n'
    '"2","bund","fs","saldo","2024","-500.0","Rechnung"\n'
    '"3","staat","fs","einnahmen","2024","800.0","Rechnung"\n'
    '"4","staat","fs","einnahmen","2025","250.0","Prognosen"\n'
    '"5","ktn","fs","einnahmen","2025","99.0","Vorhandene Daten"\n'
)


def _mount_headline(csv_text: str) -> None:
    respx.get(DATASETS["headline"].url).mock(return_value=httpx.Response(200, text=csv_text))


@respx.mock
async def test_headline_kennzeichnet_deutsche_prognosezeile():
    """Die Zusicherung, die am 27.8.2026 gefehlt hat.

    Nicht gegen `is_projection` direkt, sondern durch `headline_impl` — das ist
    der Weg, den ein MCP-Aufrufer nimmt, und die Stelle, an der der Ausfall
    tatsaechlich sichtbar wurde.
    """
    _mount_headline(DEUTSCHES_HEADLINE_CSV)
    res = await headline_impl(EFVClient(), variable="einnahmen", household="staat", model="fs")
    nach_jahr = {p.year: p for p in res.points}
    assert nach_jahr[2024].is_projection is False, "«Rechnung» ist abgeschlossen"
    assert nach_jahr[2025].is_projection is True, "«Prognosen» ist vorausschauend"
    # Die rohe Marke wird durchgereicht, nicht uebersetzt: Wer sie sehen will,
    # soll sehen, was die Quelle schrieb.
    assert nach_jahr[2025].kind == "Prognosen"


@respx.mock
async def test_headline_laesst_keine_deutsche_zeile_unklassifiziert():
    """Kein Punkt der deutschen Fassung faellt auf `None` zurueck.

    Das ist der Ausfall vom 27.8.2026 in seiner allgemeinen Form: nicht «eine
    Marke fehlt», sondern «die ganze Reihe kommt ohne Kennzeichnung heraus».
    """
    _mount_headline(DEUTSCHES_HEADLINE_CSV)
    c = EFVClient()
    for haushalt, variable in (("bund", "saldo"), ("staat", "einnahmen"), ("ktn", "einnahmen")):
        res = await headline_impl(c, variable=variable, household=haushalt, model="fs")
        assert res.points, f"{haushalt}/{variable} liefert Punkte"
        offen = [p.year for p in res.points if p.is_projection is None]
        assert not offen, f"{haushalt}/{variable}: Jahre ohne Kennzeichnung {offen}"
