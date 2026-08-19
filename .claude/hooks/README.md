# SessionStart-Hook: Klon-Aktualitaet

`klon-aktualitaet.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<Default-Branch>` liegt. Sind es null,
schweigt er.

## Grund

Ein veralteter Klon hat am 3.8.2026 **zweimal** eine rote CI erzeugt, deren
Ursache nicht im Diff stand: Die fehlenden Commits waren jeweils genau die,
die das Gate einfuehrten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den Dateien, die man selbst geaendert hat — und der liegt in denen,
die man nicht hat. Die Pruefung kostet eine Sekunde und ersetzt eine
Fehlersuche in den falschen Dateien.

`CLAUDE.md` verlangt diese Pruefung unter «Vor der Arbeit». Ein Schritt, an
den man sich erinnern muss, ist ein Schritt, den man vergisst — deshalb der
Hook.

## Er blockiert nie

Das ist die erste Anforderung, nicht die letzte: Ein Hook, der bei
Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal abgeschaltet und
schuetzt danach gar nichts. Umgesetzt ist das so:

- **Kein `set -e`.** Jeder Fehlerpfad endet ausdruecklich in `exit 0`;
  stderr wird verworfen.
- **Harte Zeitgrenze** (5 s, ueber `KLON_CHECK_TIMEOUT` verstellbar) auf
  `ls-remote` und `fetch` — bei flatterndem DNS haengt der Sessionstart
  nicht, er schweigt. `timeout`/`gtimeout` wird benutzt, wenn vorhanden;
  sonst greift ein eigener Rueckfall (macOS ohne coreutils).
  In `settings.json` steht zusaetzlich `"timeout": 15` als zweites Netz.
- **Kein interaktiver git-Prompt**: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS`,
  `ssh -o BatchMode=yes`. Eine Passwortabfrage waere genau das Blockieren,
  das ausgeschlossen sein soll.
- **Still bei**: fehlendem git, keinem Repo, keinem `origin`, leerem HEAD
  (frischer Klon ohne Commit), fehlgeschlagenem `ls-remote` oder `fetch`,
  unlesbarem Zaehlergebnis — und bei Abstand 0.
- **Detached HEAD**: still. Wer dort steht, hat einen Stand bewusst
  angesteuert (bisect, Tag, alter Commit); ein Abstand zum Default-Branch
  ist dann keine Aussage ueber veraltete Arbeit, sondern Rauschen -- und
  Rauschen entwertet genau die eine Meldung, auf die es ankommt. Die
  Pruefung steht **vor** dem fetch: kein Netz fuer einen Fall, in dem
  ohnehin geschwiegen wird.

## Der Default-Branch wird ermittelt, nicht angenommen

Drei Server im Portfolio (`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`)
nennen ihren Default-Branch `master`. Ein fest verdrahtetes `origin/main`
scheitert dort mit «couldn't find remote ref main» — das sieht aus wie ein
Netzproblem, und man arbeitet weiter auf genau dem veralteten Klon, vor dem
die Pruefung warnen sollte. Genau diese Annahme hat schon einmal einen Branch
15 Commits alt werden lassen.

Reihenfolge:

1. `git ls-remote --symref origin HEAD` → `ref: refs/heads/<X>`
2. Rueckfall ohne Netz: der zwischengespeicherte `refs/remotes/origin/HEAD`
3. Beides leer → **still raus**. Hier wird *nicht* auf `main` geraten; ein
   Rateschritt ist genau der Fehler, den der Hook verhindern soll.

## Wann er laeuft

Nur bei `source` = `startup` oder `resume`. `SessionStart` feuert auch bei
`compact` und `clear` mitten in der Sitzung — dort ist die Pruefung bereits
gelaufen und ein erneutes fetch kostet nur Zeit.

Der Hook laeuft lokal wie in Claude Code on the web. Soll er nur remote
laufen, genuegen zwei Zeilen am Anfang:

```bash
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
```

## Von Hand pruefen

```bash
# meldet den Abstand, wenn welcher besteht
CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/klon-aktualitaet.sh </dev/null

# so, wie Claude Code ihn aufruft
echo '{"hook_event_name":"SessionStart","source":"startup"}' |
  CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/klon-aktualitaet.sh
```

`tests/test_klon_aktualitaet_hook.py` fahrt das Verhalten gegen echte
Wegwerf-Repositories: veralteter Klon meldet, aktueller schweigt, kaputtes
Remote geht still durch.
