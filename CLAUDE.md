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

Seit diesem Vorfall läuft die Prüfung als SessionStart-Hook
(`.claude/hooks/klon-aktualitaet.sh`, Begründung in `.claude/hooks/README.md`):
Er meldet den Abstand beim Sessionstart und schweigt bei 0. Er blockiert nie —
kein Netz, kein Remote, detached HEAD gehen still durch. Er ersetzt das Rezept
oben also nicht, er erinnert nur daran.

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

## Wenn zwei Agenten dasselbe tun

Vor dem Anlegen eines Branches mit vorgegebenem Namen prüfen, ob es ihn schon
gibt:

```bash
git ls-remote --heads origin claude/<name> | wc -l
```

Steht dort `1`, arbeitet jemand anderes daran — mit Schreibrecht auf denselben
Ref.

Ein PR mit leerem Diff wird geschlossen, nicht gemergt. Der Test ist
`get_files` auf dem PR: kommt `[]` zurück, ändert er nichts. Ein grüner Check
sagt dazu nichts — die CI prüft den Head, nicht die Differenz zur Basis.

Am 21.8.2026 liefen zwei Sessions dieselbe Aufgabe über 45 Repos, auf den
Branches `claude/codex-review-audit-templates-9sn6mx` und
`claude/codex-review-audit-7ioh56`. Wo die eine zuerst nach `main` kam, wurde
`main` in den Branch der anderen gemergt und der add/add-Konflikt zugunsten
von `main` aufgelöst. Übrig blieben 14 PRs, die durch sämtliche Gates grün
liefen und nichts enthielten; sie wurden gemergt und hinterliessen leere
Merge-Commits. Mit den zwei Folge-PRs, die aus demselben Grund gegenstandslos
waren, waren 16 der 59 PRs jenes Tages reine Reibung.

Dieselbe Klasse wie der handgeschriebene Stub, der denselben Feldnamen annahm
wie der Code: Nichts ist rot, weil nichts geprüft wird, worauf es ankommt.

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

Alle fünf laufen in einem Job auf allen drei Feldern — keine
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

**Die Live-Suite hat ihr eigenes Budget** — 15 s je Versuch, 75 s für den
ganzen Aufruf (`live_client()` in `tests/test_live.py`). Die Produktion fährt
25/25, und dass beide Zahlen dort gleich sind, ist der Grund: Fällt die
httpx-Zeitgrenze des ersten Versuchs mit der Budgetfrist zusammen, gewinnt
das Budget und `_fetch_with_retry` bricht ab, statt zu wiederholen. Am
18.8.2026 kostete das vier Tests — `Upstream unreachable after 1 attempt(s),
25s budget spent`, während die Quelle direkt danach mit 200 in 2,6 s
antwortete. Für die Produktion ist der enge Etat richtig (ein Retry nach dem
Aufgeben des MCP-Aufrufers bringt nichts); auf einen Cron-Job wartet niemand.
Die 75 s sind gerechnet: vier Versuche samt Backoff-Leiter bei weitester
Streuung, `4×15 + (1,5+3+6) = 70,5 s`.

Wer daran dreht, muss `timeout-minutes` in `live.yml` mit ansehen. Ein
fehlgeschlagener Fetch wird nicht gecacht, also fährt **jeder** Test die
Leiter erneut — am 1.8.2026 waren das vier Tests und 17 Minuten. Budget mal
Anzahl Live-Tests muss deshalb deutlich unter dem Job-Timeout bleiben;
`test_live_budget_fits_the_job_timeout` hält die beiden Zahlen zusammen und
liest sie dort, wo sie stehen.
