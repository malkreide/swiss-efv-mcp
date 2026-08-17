#!/usr/bin/env python3
"""Tests fuer scripts/live_streak.py — wann aus «Quelle aus» ein Befund wird.

Die Schwelle entscheidet, ob ein Dauerausfall sichtbar wird oder in der Luecke
verschwindet, die `unknown` aufmacht. Sie steht deshalb in einem Skript und
nicht in einem `run:`-Block, und hier stehen die Faelle, gegen die sie gebaut
ist.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import live_streak as ls  # noqa: E402


def run(conclusion: str | None, status: str = "completed", id: int = 0) -> dict:
    """Ein Lauf, wie ihn `actions.listWorkflowRuns` liefert (gekuerzt)."""
    return {"id": id, "status": status, "conclusion": conclusion}


GRUEN = run("success")
ROT = run("failure")


class StreakTest(unittest.TestCase):
    def test_gruener_lauf_hat_keine_serie(self):
        self.assertEqual(ls.streak([ROT, ROT, ROT], "clear"), 0)

    def test_erster_roter_lauf_zaehlt_sich_selbst(self):
        self.assertEqual(ls.streak([GRUEN, GRUEN], "unknown"), 1)

    def test_ohne_historie_zaehlt_nur_dieser_lauf(self):
        self.assertEqual(ls.streak([], "unknown"), 1)

    def test_der_gruene_lauf_beendet_die_serie(self):
        self.assertEqual(ls.streak([ROT, GRUEN, ROT, ROT], "unknown"), 2)

    def test_serie_ueber_mehrere_laeufe(self):
        self.assertEqual(ls.streak([ROT, ROT, ROT], "unknown"), 4)

    def test_abgebrochener_lauf_setzt_die_serie_nicht_zurueck(self):
        """Ein `cancelled` sagt nichts ueber die Quelle — weder Ausfall noch Gruen.

        Als Ende gelesen haette er die Serie still zurueckgesetzt, und der
        Dauerausfall waere nie gemeldet worden.
        """
        self.assertEqual(ls.streak([run("cancelled"), ROT, ROT], "unknown"), 3)

    def test_laufender_lauf_wird_uebersprungen(self):
        self.assertEqual(ls.streak([run(None, status="in_progress"), ROT], "unknown"), 2)

    def test_eigener_lauf_wird_nicht_doppelt_gezaehlt(self):
        """Ist der eigene Lauf schon in der Liste, zaehlt er trotzdem einmal."""
        self.assertEqual(ls.streak([run("failure", id=99), ROT], "unknown", eigene_run_id=99), 2)


class SchwelleTest(unittest.TestCase):
    """`dauerausfall` nur bei `unknown` — ein `finding` hat sein Issue schon."""

    def _out(self, runs: list[dict], state: str) -> dict[str, str]:
        import os

        with tempfile.TemporaryDirectory() as tmp:
            pfad = Path(tmp) / "runs.json"
            pfad.write_text(json.dumps({"workflow_runs": runs}), encoding="utf-8")
            out = Path(tmp) / "gh-output"
            out.write_text("", encoding="utf-8")
            os.environ["GITHUB_OUTPUT"] = str(out)
            try:
                ls.main([str(pfad), "--state", state])
            finally:
                del os.environ["GITHUB_OUTPUT"]
            zeilen = out.read_text(encoding="utf-8").strip().splitlines()
        return dict(z.split("=", 1) for z in zeilen)

    def test_zwei_laeufe_sind_noch_kein_dauerausfall(self):
        """Die Quelle hat nachts Wartungsfenster; zwei Laeufe treffen dasselbe."""
        werte = self._out([ROT, GRUEN], "unknown")
        self.assertEqual(werte["streak"], "2")
        self.assertEqual(werte["dauerausfall"], "false")

    def test_ab_dem_dritten_lauf_ist_es_einer(self):
        werte = self._out([ROT, ROT, GRUEN], "unknown")
        self.assertEqual(werte["streak"], "3")
        self.assertEqual(werte["dauerausfall"], "true")

    def test_finding_meldet_keinen_dauerausfall(self):
        """Ein inhaltlicher Fehlschlag oeffnet seinen Thread ohnehin."""
        werte = self._out([ROT, ROT, ROT], "finding")
        self.assertEqual(werte["dauerausfall"], "false")

    def test_gruen_meldet_keinen_dauerausfall(self):
        werte = self._out([ROT, ROT, ROT], "clear")
        self.assertEqual(werte["streak"], "0")
        self.assertEqual(werte["dauerausfall"], "false")

    def test_blosse_liste_ohne_huelle_wird_gelesen(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = Path(tmp) / "runs.json"
            pfad.write_text(json.dumps([ROT, ROT]), encoding="utf-8")
            self.assertEqual(len(ls.lies_runs(pfad)), 2)


class KaputteHistorieTest(unittest.TestCase):
    """Ohne lesbare Historie wird nichts behauptet — kein Issue auf Verdacht."""

    def test_fehlende_datei_meldet_keinen_dauerausfall(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gh-output"
            out.write_text("", encoding="utf-8")
            os.environ["GITHUB_OUTPUT"] = str(out)
            try:
                rc = ls.main([str(Path(tmp) / "fehlt.json"), "--state", "unknown"])
            finally:
                del os.environ["GITHUB_OUTPUT"]
            geschrieben = out.read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn("streak=1", geschrieben)
        self.assertIn("dauerausfall=false", geschrieben)

    def test_kaputtes_json_meldet_keinen_dauerausfall(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = Path(tmp) / "runs.json"
            pfad.write_text("{kaputt", encoding="utf-8")
            rc = ls.main([str(pfad), "--state", "unknown"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
