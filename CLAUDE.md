# CLAUDE.md

## Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.
Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

## Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.
Zwei Fallen, die beide grün blieben:
- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
asyncio selbst und entschärft die Mechanik im ganzen Prozess. Patche
einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

## Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.
PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.
Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

---

## Dieses Repo

**ruff:** genau eine Quelle — `ruff==0.16.1` im `dev`-Extra von
`pyproject.toml`. `pip install -e ".[dev]"` reicht also, lokal wie in der CI.
Keine zweite Version in die Workflows schreiben: ein solcher Schritt läuft
nach dem dev-Install und überstimmt den Pin still (`ci.yml` hatte einen;
`test_werkzeug_versionen.py` hält beides fest). Ein `.pre-commit-config.yaml`
gibt es nicht.

Lokal `python -m ruff` aufrufen, nicht `ruff` — ein `ruff` auf dem PATH
kann eine ältere Version sein und meldet dann genau die Abweichungen,
die niemand verursacht hat.

Gates, wörtlich aus `ci.yml` (Matrix: Python 3.11 / 3.12 / 3.13):

```
PYTHONPATH=src pytest tests/ -m "not live"
python scripts/check_ruff_pin.py
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python scripts/check_version_sync.py
```

Alle vier laufen in einem Job auf allen drei Feldern — keine
`if: matrix.python-version`-Ausnahme, kein zweiter lint-Job. Ein grünes 3.13
heisst hier also wirklich, dass alles auf 3.13 lief; im Portfolio ist das
nicht durchgehend so. Ein `fail-fast: false` steht **nicht** da: Eine rote
3.11 bricht 3.12 und 3.13 ab, bevor sie etwas sagen.

**Live-Tests: geplanter Workflow vorhanden** — `.github/workflows/live.yml`,
cron `27 5 * * *` plus `workflow_dispatch`, mit Einordnung über
`scripts/classify_live_run.py` und automatischem Issue. DRIFT-005 ist damit
erfüllt; die PR-CI schliesst Live-Tests weiterhin per `-m "not live"` aus,
und das bleibt so. `schedule` greift nur auf dem Default-Branch — Änderungen
an `live.yml` erst nach dem Merge wirksam, vorher von Hand auslösen.
