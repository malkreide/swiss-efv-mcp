#!/usr/bin/env python3
"""Wie lange ist die Live-Suite schon nicht mehr gruen — und ist das ein Dauerausfall?

WOZU
----
Seit dem 17.8.2026 macht ein Ausfall der Quelle kein Issue mehr auf: Sind alle
Fehlschlaege Transportfehler, ist der Lauf `unknown`, und `unknown` oeffnet
nichts (siehe `classify_live_run.py`). Das ist richtig fuer die zwei Minuten, in
denen `data.finance.admin.ch` mal nicht antwortet.

Es ist falsch fuer die Quelle, die seit einer Woche weg ist. Die faellt dann
naemlich in genau die Luecke, die `unknown` aufmacht: taeglich ein roter Job,
den niemand oeffnet, und kein Thread, der es sagt. Ein Server, der seine Daten
nicht mehr laden kann, ist kaputt — auch wenn nicht er der Schuldige ist.

Also: ab dem dritten Lauf ohne Gruen wird es doch ein Issue.

WOHER DER ZAEHLER KOMMT
-----------------------
Nirgends — er wird nicht gefuehrt. Ein Zaehler braeuchte einen Ort (Cache,
Artefakt, Repo-Datei), und jeder dieser Orte kann verschwinden, veralten oder
zwei Laeufe gleichzeitig sehen.

Stattdessen wird die Antwort aus etwas abgeleitet, das GitHub ohnehin fuehrt:
der Lauf-Historie von `live.yml`. Der Workflow endet genau dann mit `success`,
wenn die Einordnung `clear` war — der letzte Schritt macht bei `finding` und
`unknown` beides `exit 1`. `conclusion == "success"` ist damit ein exaktes
Synonym fuer «die Suite war gruen», und die Strecke bis zum letzten gruenen
Lauf ist die gesuchte Serie.

Kein Zustand, keine Migration, nichts, was kaputtgehen kann, ohne dass es
auffaellt.

Aufruf:
    python scripts/live_streak.py runs.json --state unknown

`runs.json` ist die Antwort von `actions.listWorkflowRuns` (oder nur deren
`workflow_runs`-Liste). Gibt `streak=N` und `dauerausfall=true|false` aus und
haengt beides an `$GITHUB_OUTPUT` an. Exit-Code ist immer 0: Ueber rot oder
gruen entscheidet der Workflow, nicht dieser Reporter.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Ab dem dritten Lauf ohne Gruen. Zwei ist zu frueh — die Quelle hat nachts
# Wartungsfenster, und zwei Laeufe koennen dasselbe Fenster treffen. Vier waere
# zu spaet: Bei taeglicher Kadenz waere ein Ausfall dann vier Tage unsichtbar.
SCHWELLE = 3


def streak(runs: list[dict], state: str, eigene_run_id: int | None = None) -> int:
    """Laeufe ohne Gruen, diesen mitgezaehlt.

    `runs` ist absteigend nach Alter, so wie GitHub sie liefert. Gezaehlt wird
    vom neuesten weg, bis der erste gruene Lauf kommt; der beendet die Serie.

    Laeufe, die noch laufen oder abgebrochen wurden, sagen nichts ueber die
    Quelle und werden uebersprungen — nicht als Ausfall gezaehlt und nicht als
    Ende der Serie gelesen. Sonst haette ein abgebrochener Lauf die Serie still
    zurueckgesetzt, und der Dauerausfall waere nie gemeldet worden.
    """
    if state == "clear":
        return 0
    gezaehlt = 1  # dieser Lauf
    for run in runs:
        if eigene_run_id is not None and run.get("id") == eigene_run_id:
            continue
        if run.get("status") != "completed":
            continue
        schluss = run.get("conclusion")
        if schluss == "success":
            break
        if schluss in (None, "cancelled", "skipped"):
            continue
        gezaehlt += 1
    return gezaehlt


def lies_runs(pfad: Path) -> list[dict]:
    """Die Lauf-Liste aus der API-Antwort — als Huelle oder als blosse Liste."""
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    if isinstance(roh, dict):
        roh = roh.get("workflow_runs", [])
    return [r for r in roh if isinstance(r, dict)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="live_streak")
    ap.add_argument("runs", type=Path, help="JSON von actions.listWorkflowRuns")
    ap.add_argument("--state", required=True, help="clear, finding oder unknown")
    ap.add_argument("--run-id", type=int, default=None, help="eigene run_id, wird uebersprungen")
    args = ap.parse_args(argv)

    try:
        runs = lies_runs(args.runs)
    except (OSError, ValueError) as exc:
        # Ohne Historie wird nichts behauptet: `streak=1` heisst «dieser Lauf»,
        # und ein Dauerausfall wird nicht gemeldet. Lieber keine Meldung als
        # eine, die auf einer ungelesenen Datei steht.
        print(f"runs nicht lesbar ({exc}) — ohne Historie kein Dauerausfall")
        runs = []

    n = streak(runs, args.state, args.run_id)
    dauerausfall = args.state == "unknown" and n >= SCHWELLE

    print(f"streak={n}")
    print(f"dauerausfall={str(dauerausfall).lower()}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"streak={n}\n")
            fh.write(f"dauerausfall={str(dauerausfall).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
