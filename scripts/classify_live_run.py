#!/usr/bin/env python3
"""Was hat der geplante Live-Lauf festgestellt — clear, finding oder unknown?

WARUM DAS EIN SKRIPT IST UND KEIN YAML-BLOCK
--------------------------------------------
`if: failure()` kennt zwei Antworten: rot und nicht rot. Ein Live-Lauf hat
drei, und die dritte ist die, die zaehlt:

  clear    Die Suite ist gelaufen und war gruen.
  finding  Die Suite ist gelaufen und etwas ist gefallen.
  unknown  Die Suite ist NICHT gelaufen — und niemand weiss, ob der Vertrag
           mit der Quelle noch haelt.

Ein gescheitertes `pip install`, ein Timeout, eine umbenannte Marke: alles
`unknown`, alles sieht unter `if: failure()` aus wie ein gebrochener Vertrag.
Und ein Lauf, in dem jeder Test uebersprungen wurde, sieht unter jedem
Exit-Code-Check aus wie Erfolg.

DER TRANSPORTFEHLER
-------------------
Ein Timeout gehoert nach `unknown` — aber nur der Job-Timeout landete dort, weil
dann kein XML entsteht. Erreicht die Suite die Quelle nicht, laufen die Tests
und fallen um, das XML zaehlt Fehlschlaege, und die Einordnung las daraus einen
gebrochenen Vertrag. Am 17.8.2026 gemessen: vier Fehlschlaege, alle
`UpstreamError` nach einem TLS-Handshake-Timeout, ein Issue mit dem Titel «rot»
— und die Quelle antwortete beim direkten Abruf danach mit 200 in 2,2s.

Der Unterschied ist keine Nuance. «Der Vertrag hat sich geaendert» will einen
Fix, «die Quelle war zwei Minuten aus» will nichts. Wer beides gleich meldet,
bringt sich das Melden ab.

Deshalb wird gefragt, WORAN die Tests gestorben sind. `EFVClient` wirft dafuer
einen eigenen Typ (`UpstreamError`, «a caller can branch on»); genau darauf wird
hier verzweigt. Sind ALLE Fehlschlaege Transportfehler, hat der Lauf ueber den
Vertrag nichts festgestellt — `unknown`. Ist auch nur einer ein echter
Fehlschlag, bleibt es `finding`: Der sagt etwas, das gesehen gehoert.

Gelesen wird nur das `message`-Attribut, und der Typ muss dort vorne stehen.
Eine Suche im Traceback waere gefaehrlich: `Failed: DID NOT RAISE UpstreamError`
ist ein *echter* Fehlschlag, der den Namen nur erwaehnt. Ihn als Transport zu
lesen hiesse, genau den Vertragsbruch zu verschlucken, fuer den es diese Suite
gibt.

Diese Einordnung entscheidet, ob ein Issue aufgeht oder zugeht. Sie in einen
`run:`-Block zu schreiben hiesse, den einzigen Teil des Workflows, der etwas
behauptet, an die einzige Stelle zu legen, an der ihn niemand testen kann.
Deshalb steht sie hier, neben ihrem Test.

DER UEBERSPRUNGENE LAUF
-----------------------
Gemessen am 7.8.2026 an `swiss-transport-mcp`: Ohne `TRANSPORT_API_KEY`
ueberspringt die Live-Suite alle sechs Tests, und pytest endet mit 0. Ein
woechentlicher Job haette gemeldet: gruen. Geprueft haette er nichts — und ein
offenes Issue haette er zugemacht, mit einem Vergleich, den es nie gab.

`tests - skipped == 0` ist deshalb `unknown` und nicht `clear`. Ein Secret, das
niemand gesetzt hat, ist kein gruener Vertrag mit der Quelle; es ist gar keiner.

DIE QUELLE IST DAS JUNIT-XML, NICHT DER EXIT-CODE
-------------------------------------------------
Der Exit-Code von pytest sagt 0 fuer «alles gruen» und fuer «alles
uebersprungen» dasselbe. Das XML zaehlt Tests, Fehler, Fehlschlaege und
Uebersprungene getrennt, also wird es gelesen. Fehlt es, ist pytest gar nicht
bis zum Schreiben gekommen — auch das ist `unknown`, und zwar mit Grund.

Aufruf:
    python scripts/classify_live_run.py live-report.xml
    python scripts/classify_live_run.py live-report.xml --pytest-exit 1

Gibt `state=...` und `reason=...` auf stdout aus und haengt beides an
`$GITHUB_OUTPUT` an, wenn die Variable gesetzt ist. Der Exit-Code ist immer 0:
Ueber rot oder gruen entscheidet der Workflow, nicht dieser Reporter.
"""

from __future__ import annotations

import argparse
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

CLEAR = "clear"
FINDING = "finding"
UNKNOWN = "unknown"

# Die Exceptions aus `swiss_efv_mcp.client`, die «nicht erreicht» heissen — und
# damit: ueber den Vertrag ist nichts festgestellt. BEWUSST eine Liste und kein
# `Upstream\w*Error`: Ein kuenftiger Typ, der einen Vertragsbruch benennt, wuerde
# sonst still als Transportfehler durchgehen und das Issue unterdruecken, das er
# ausloesen soll. Wer hier nichts eintraegt, bekommt `finding` — ein Issue zu
# viel, nicht einen verschluckten Befund. `test_transport_typen.py` haelt die
# Liste gegen `client.py` und faellt, sobald dort ein Typ dazukommt.
_TRANSPORT_EXCEPTIONS = (
    "swiss_efv_mcp.client.UpstreamError",
    "swiss_efv_mcp.client.UpstreamNotAttemptedError",
)

# pytest schreibt den voll qualifizierten Typ an den ANFANG von `message`:
#   <failure message="swiss_efv_mcp.client.UpstreamError: Upstream unreachable …">
# Faellt eine Fixture, verpackt pytest dasselbe in:
#   <error message='failed on setup with "swiss_efv_mcp.client.UpstreamError: …"'>
# Beide Formen am 17.8.2026 gegen pytest 8 nachgemessen, nicht geraten. Der
# Anker vorne ist die Sicherung gegen `Failed: DID NOT RAISE UpstreamError`.
_TRANSPORT = re.compile(
    r'^(?:failed on \w+ with ")?(?:'
    + "|".join(re.escape(t) for t in _TRANSPORT_EXCEPTIONS)
    + r"): "
)


def _fehlermeldungen(suites: list[ET.Element]) -> list[str]:
    """Eine Meldung je `<failure>`/`<error>`, in XML-Reihenfolge.

    Nur das `message`-Attribut, nie der Traceback-Text — siehe `DID NOT RAISE`
    im Modul-Docstring. Fehlt das Attribut, steht hier `""`: unlesbar zaehlt als
    nicht-Transport und damit als Befund, nicht als Entwarnung.
    """
    return [
        el.get("message") or ""
        for suite in suites
        for case in suite.iter("testcase")
        for el in (*case.findall("failure"), *case.findall("error"))
    ]


def classify(report: Path, pytest_exit: int | None = None) -> tuple[str, str]:
    """(state, reason) aus einem JUnit-XML und optional dem pytest-Exit-Code."""
    if not report.is_file():
        return (
            UNKNOWN,
            f"kein Report unter {report} — pytest ist nicht bis zum Schreiben "
            "gekommen" + (f" (Exit {pytest_exit})" if pytest_exit is not None else ""),
        )
    try:
        root = ET.parse(report).getroot()
    except (ET.ParseError, OSError) as exc:
        return UNKNOWN, f"{report} ist nicht lesbar: {exc}"

    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        return UNKNOWN, f"{report} enthaelt keine testsuite"

    def total(attr: str) -> int:
        return sum(int(s.get(attr) or 0) for s in suites)

    tests, failures, errors, skipped = (
        total("tests"),
        total("failures"),
        total("errors"),
        total("skipped"),
    )

    if failures or errors:
        gezaehlt = failures + errors
        gemeldet = _fehlermeldungen(suites)
        transport = [m for m in gemeldet if _TRANSPORT.search(m)]
        # `len(gemeldet) == gezaehlt` ist die Vorsichtsklausel: Zaehlen die
        # Attribute mehr Fehler, als einzeln im XML stehen, ist ueber die
        # ungesehenen nichts bekannt — und Unbekanntes darf ein Issue nicht
        # unterdruecken. Dann bleibt es `finding`.
        if gezaehlt and len(gemeldet) == gezaehlt and len(transport) == gezaehlt:
            return (
                UNKNOWN,
                f"alle {gezaehlt} Fehlschlag/Fehlschlaege sind Transportfehler — die "
                "Quelle war nicht erreichbar, ueber den Vertrag sagt dieser Lauf nichts",
            )
        rest = gezaehlt - len(transport)
        woran = f"{failures} Fehlschlag/Fehlschlaege und {errors} Fehler von {tests} Test(s)"
        if transport:
            woran += f" (davon {len(transport)} Transport, {rest} inhaltlich)"
        return FINDING, woran
    if tests == 0:
        return (
            UNKNOWN,
            "null Tests eingesammelt — die Marke oder die Dateien haben sich "
            "bewegt, und ein Erfolg ohne Test ist kein Erfolg",
        )
    if tests - skipped == 0:
        return (
            UNKNOWN,
            f"alle {tests} Test(s) uebersprungen — meist ein fehlendes Secret oder "
            "eine nicht erfuellte Vorbedingung. Geprueft wurde nichts",
        )
    return CLEAR, f"{tests - skipped} von {tests} Test(s) ausgefuehrt, alle gruen"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="classify_live_run")
    ap.add_argument("report", type=Path, help="Pfad zum JUnit-XML von pytest")
    ap.add_argument("--pytest-exit", type=int, default=None)
    args = ap.parse_args(argv)

    state, reason = classify(args.report, args.pytest_exit)
    print(f"state={state}")
    print(f"reason={reason}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        # Zeilenumbruch raus, bevor der Grund in `$GITHUB_OUTPUT` geht: Die
        # `key=value`-Form endet an der ersten neuen Zeile, und was danach
        # steht, liest der Runner als naechstes Output. Ein Grund koennte so
        # ein `state=clear` nachschieben und den roten Lauf gruen faerben.
        flat = " ".join(reason.split())
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"state={state}\n")
            fh.write(f"reason={flat}\n")
    # Immer 0: Ueber rot oder gruen entscheidet der Workflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
