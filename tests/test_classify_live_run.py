#!/usr/bin/env python3
"""Tests fuer scripts/classify_live_run.py — die drei Antworten eines Live-Laufs.

Die Einordnung entscheidet, ob ein Issue aufgeht oder zugeht. Genau deshalb
steht sie in einem Skript und nicht in einem `run:`-Block: So kann jemand sie
gegen die Faelle halten, aus denen sie entstanden ist.

Der wichtigste Fall ist `test_alle_uebersprungen_ist_nicht_gruen`. Gemessen am
7.8.2026 an `swiss-transport-mcp`: Ohne `TRANSPORT_API_KEY` ueberspringt die
Live-Suite alle sechs Tests und pytest endet mit 0. Ein Job, der das als gruen
bucht, schliesst ein offenes Issue mit einem Vergleich, den es nie gab.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from xml.sax.saxutils import quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import classify_live_run as clr  # noqa: E402


def write(tmp: Path, xml: str) -> Path:
    path = tmp / "live-report.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def suite(tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuites><testsuite name="pytest" tests="{tests}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}"></testsuite></testsuites>'
    )


# Wortlaut aus echten pytest-Laeufen, am 17.8.2026 nachgemessen (pytest 8):
# der voll qualifizierte Typ steht vorne, bei Fixtures in `failed on setup with`
# verpackt. Handgeschrieben waere hier nur die eigene Annahme kodiert.
TRANSPORT_MSG = (
    "swiss_efv_mcp.client.UpstreamError: Upstream unreachable after 1 attempt(s), "
    "25s budget spent: TimeoutError: no further detail (host=www.data.finance.admin.ch)"
)
NICHT_ATTEMPTED_MSG = (
    "swiss_efv_mcp.client.UpstreamNotAttemptedError: Upstream not attempted: "
    "25s budget already spent (host=www.data.finance.admin.ch)"
)
FIXTURE_TRANSPORT_MSG = f'failed on setup with "{TRANSPORT_MSG}"'
# Im XML steht der Umbruch als `&#10;`; nach dem Parsen ist es ein Newline, und
# genau das sieht die Einordnung.
VERTRAGSBRUCH_MSG = (
    "AssertionError: Spalte Saldo fehlt im Dump\nassert 'Saldo' in {'Kopfzeile_neu': '1'}"
)
# Die Falle: ein ECHTER Fehlschlag, der den Transporttyp nur beim Namen nennt.
DID_NOT_RAISE_MSG = "Failed: DID NOT RAISE UpstreamError"


def faelle(tests: int, failures: list[str] = [], errors: list[str] = []) -> str:  # noqa: B006
    """XML mit einzeln ausgewiesenen `<failure>`/`<error>`, wie pytest es schreibt.

    `quoteattr` ist hier nicht Kosmetik. Die Fixture-Meldung enthaelt selbst
    Anfuehrungszeichen (`failed on setup with "..."`); roh eingesetzt zerbricht
    sie das XML, und die Einordnung antwortet `unknown` — weil der Report
    unlesbar ist, nicht weil sie den Transportfehler erkannt haette. Der Test
    war damit gruen, ohne irgendetwas zu pruefen: aufgefallen erst in der
    Gegenprobe, als die Erkennung ausgebaut wurde und er gruen blieb.
    """
    cases = "".join(
        f'<testcase name="test_{i}"><failure message={quoteattr(m)}></failure></testcase>'
        for i, m in enumerate(failures)
    ) + "".join(
        f'<testcase name="test_e{i}"><error message={quoteattr(m)}></error></testcase>'
        for i, m in enumerate(errors)
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuites><testsuite name="pytest" tests="{tests}" '
        f'failures="{len(failures)}" errors="{len(errors)}" skipped="0">'
        f"{cases}</testsuite></testsuites>"
    )


class ClassifyTest(unittest.TestCase):
    def _state(self, xml: str) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            return clr.classify(write(Path(tmp), xml))

    def test_alles_gruen_ist_clear(self):
        state, reason = self._state(suite(tests=3))
        self.assertEqual(state, clr.CLEAR)
        self.assertIn("3 von 3", reason)

    def test_ein_fehlschlag_ist_ein_finding(self):
        state, _ = self._state(suite(tests=3, failures=1))
        self.assertEqual(state, clr.FINDING)

    def test_ein_fehler_ist_ein_finding(self):
        state, _ = self._state(suite(tests=3, errors=1))
        self.assertEqual(state, clr.FINDING)

    def test_alle_uebersprungen_ist_nicht_gruen(self):
        """swiss-transport-mcp ohne TRANSPORT_API_KEY: 6 von 6 uebersprungen."""
        state, reason = self._state(suite(tests=6, skipped=6))
        self.assertEqual(state, clr.UNKNOWN)
        self.assertIn("uebersprungen", reason)

    def test_teilweise_uebersprungen_ist_gruen(self):
        """Ein einzelner Skip ist eine Entscheidung im Test, kein Ausfall."""
        state, reason = self._state(suite(tests=6, skipped=5))
        self.assertEqual(state, clr.CLEAR)
        self.assertIn("1 von 6", reason)

    def test_null_tests_ist_kein_erfolg(self):
        """Die Marke umbenannt, die Dateien verschoben — pytest meldet trotzdem 0."""
        state, reason = self._state(suite(tests=0))
        self.assertEqual(state, clr.UNKNOWN)
        self.assertIn("null Tests", reason)

    def test_ein_fehlschlag_schlaegt_uebersprungene(self):
        state, _ = self._state(suite(tests=6, skipped=5, failures=1))
        self.assertEqual(state, clr.FINDING)

    def test_mehrere_testsuites_werden_summiert(self):
        xml = (
            "<testsuites>"
            '<testsuite tests="2" failures="0" errors="0" skipped="2"/>'
            '<testsuite tests="3" failures="0" errors="0" skipped="0"/>'
            "</testsuites>"
        )
        state, _ = self._state(xml)
        self.assertEqual(state, clr.CLEAR)

    def test_eine_einzelne_testsuite_ohne_huelle(self):
        xml = '<testsuite tests="2" failures="0" errors="0" skipped="0"/>'
        state, _ = self._state(xml)
        self.assertEqual(state, clr.CLEAR)


class TransportfehlerTest(unittest.TestCase):
    """Nicht erreichbar ist kein Befund.

    Am 17.8.2026 um 06:00 UTC: vier Fehlschlaege, alle `UpstreamError` nach
    einem TLS-Handshake-Timeout, ein Issue mit dem Titel «rot» — und beim
    direkten Abruf danach antwortete die Quelle mit 200 in 2,2s. «Der Vertrag
    hat sich geaendert» will einen Fix, «die Quelle war zwei Minuten aus» will
    nichts; wer beides gleich meldet, bringt sich das Melden ab.
    """

    def _state(self, xml: str) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            return clr.classify(write(Path(tmp), xml))

    def test_lauf_vom_17_8_ist_kein_finding(self):
        """4 Transport-Fehlschlaege, 2 gruen — genau die Verteilung des Laufs."""
        state, reason = self._state(faelle(tests=6, failures=[TRANSPORT_MSG] * 4))
        self.assertEqual(state, clr.UNKNOWN)
        self.assertIn("Transportfehler", reason)

    def test_budget_vor_dem_ersten_request_ist_auch_transport(self):
        state, _ = self._state(faelle(tests=2, failures=[NICHT_ATTEMPTED_MSG]))
        self.assertEqual(state, clr.UNKNOWN)

    def test_gefallene_fixture_ist_transport(self):
        """Faellt die session-weite Fixture, meldet pytest `error`, nicht `failure`."""
        state, _ = self._state(faelle(tests=6, errors=[FIXTURE_TRANSPORT_MSG] * 6))
        self.assertEqual(state, clr.UNKNOWN)

    def test_ein_inhaltlicher_fehlschlag_schlaegt_alle_transportfehler(self):
        """Der eine sagt etwas ueber den Vertrag. Der gehoert gesehen."""
        state, reason = self._state(
            faelle(tests=6, failures=[TRANSPORT_MSG, TRANSPORT_MSG, VERTRAGSBRUCH_MSG])
        )
        self.assertEqual(state, clr.FINDING)
        self.assertIn("1 inhaltlich", reason)

    def test_did_not_raise_ist_ein_befund_kein_transport(self):
        """Erwaehnt den Typnamen — eine Suche im Text wuerde den Befund fressen."""
        state, _ = self._state(faelle(tests=3, failures=[DID_NOT_RAISE_MSG]))
        self.assertEqual(state, clr.FINDING)

    def test_kurzer_typname_zaehlt_nicht(self):
        """Ohne Modulpfad ist es irgendein Text, kein Urteil von `EFVClient`."""
        state, _ = self._state(faelle(tests=3, failures=["UpstreamError: irgendwas"]))
        self.assertEqual(state, clr.FINDING)

    def test_transporttyp_muss_vorne_stehen(self):
        state, _ = self._state(
            faelle(
                tests=3, failures=["AssertionError: erwartet swiss_efv_mcp.client.UpstreamError: x"]
            )
        )
        self.assertEqual(state, clr.FINDING)

    def test_fehlschlag_ohne_message_ist_kein_transport(self):
        """Unlesbar heisst Befund, nicht Entwarnung."""
        xml = (
            '<testsuite tests="2" failures="1" errors="0" skipped="0">'
            '<testcase name="test_x"><failure></failure></testcase></testsuite>'
        )
        state, _ = self._state(xml)
        self.assertEqual(state, clr.FINDING)

    def test_mehr_gezaehlte_als_ausgewiesene_fehler_bleibt_finding(self):
        """Ueber die ungesehenen ist nichts bekannt — Unbekanntes unterdrueckt nichts."""
        xml = (
            '<testsuite tests="6" failures="4" errors="0" skipped="0">'
            f'<testcase name="test_x"><failure message="{TRANSPORT_MSG}"></failure></testcase>'
            "</testsuite>"
        )
        state, _ = self._state(xml)
        self.assertEqual(state, clr.FINDING)


class MissingReportTest(unittest.TestCase):
    """Kein Report heisst: pytest kam nicht bis zum Schreiben. Nie clear."""

    def test_fehlender_report_ist_unknown(self):
        state, reason = clr.classify(Path("/nonexistent/live-report.xml"), pytest_exit=4)
        self.assertEqual(state, clr.UNKNOWN)
        self.assertIn("Exit 4", reason)

    def test_kaputtes_xml_ist_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp), "<testsuite tests=")
            state, _ = clr.classify(path)
        self.assertEqual(state, clr.UNKNOWN)

    def test_xml_ohne_testsuite_ist_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp), "<irgendwas/>")
            state, _ = clr.classify(path)
        self.assertEqual(state, clr.UNKNOWN)


class GithubOutputTest(unittest.TestCase):
    """Der Workflow liest state und reason ueber $GITHUB_OUTPUT."""

    def test_beide_werte_werden_angehaengt(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            report = write(Path(tmp), suite(tests=2))
            out = Path(tmp) / "gh-output"
            out.write_text("", encoding="utf-8")
            os.environ["GITHUB_OUTPUT"] = str(out)
            try:
                rc = clr.main([str(report)])
            finally:
                del os.environ["GITHUB_OUTPUT"]
            written = out.read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn("state=clear", written)
        self.assertIn("reason=", written)


if __name__ == "__main__":
    unittest.main()
