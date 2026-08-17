"""Haelt die Transport-Typen in `classify_live_run.py` gegen `client.py`.

Die Einordnung erkennt einen Transportfehler am voll qualifizierten
Exception-Namen im JUnit-XML. Dieser Name ist damit eine Schnittstelle zwischen
zwei Dateien, die nichts voneinander importieren — und solche Kopplungen laufen
still auseinander.

Beide Richtungen tun weh, in verschiedene Richtungen:

* Wird `UpstreamError` umbenannt, matcht die Regex nie mehr. Nichts wird rot,
  keine Zeile aendert sich — nur jeder Ausfall der Quelle macht wieder ein
  Issue auf, so wie am 17.8.2026. Ein Fehler, der sich als Normalbetrieb tarnt.
* Kommt eine neue Unterklasse von `UpstreamError` dazu und niemand traegt sie
  ein, faellt der Lauf zurueck auf `finding`. Das ist die harmlose Richtung —
  ein Issue zu viel — aber gemeint war es trotzdem nicht.

Deshalb wird hier beides festgenagelt. Kein Netz: nur Klassen anschauen.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import classify_live_run as clr  # noqa: E402

from swiss_efv_mcp import client  # noqa: E402


def _unterklassen(wurzel: type) -> set[type]:
    gefunden = {wurzel}
    for sub in wurzel.__subclasses__():
        gefunden |= _unterklassen(sub)
    return gefunden


class TransportTypenTest(unittest.TestCase):
    def test_jeder_gelistete_typ_existiert_im_client(self):
        """Gegen die stille Umbenennung: der Name muss eine echte Klasse treffen."""
        for qualifiziert in clr._TRANSPORT_EXCEPTIONS:
            modul, _, name = qualifiziert.rpartition(".")
            self.assertEqual(modul, client.__name__, f"{qualifiziert} zeigt nicht auf client")
            self.assertTrue(
                hasattr(client, name),
                f"{qualifiziert} steht in classify_live_run, aber nicht mehr in client.py — "
                "die Transport-Erkennung greift ab jetzt ins Leere",
            )

    def test_jeder_gelistete_typ_ist_ein_upstream_fehler(self):
        for qualifiziert in clr._TRANSPORT_EXCEPTIONS:
            klasse = getattr(client, qualifiziert.rpartition(".")[2])
            self.assertTrue(issubclass(klasse, client.UpstreamError))

    def test_jede_upstream_unterklasse_ist_gelistet(self):
        """`UpstreamError` heisst «konnte nicht erreicht werden» — das gilt auch fuer Erben.

        Wer einen Typ fuer einen gebrochenen Vertrag braucht, leitet ihn nicht
        von `UpstreamError` ab: Ein Vertragsbruch ist kein Transportproblem.
        """
        gelistet = {q.rpartition(".")[2] for q in clr._TRANSPORT_EXCEPTIONS}
        im_modul = {
            k.__name__
            for k in _unterklassen(client.UpstreamError)
            if k.__module__ == client.__name__
        }
        self.assertEqual(
            im_modul,
            gelistet,
            "client.py und classify_live_run.py sind auseinandergelaufen",
        )


if __name__ == "__main__":
    unittest.main()
