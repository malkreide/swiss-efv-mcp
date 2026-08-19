#!/usr/bin/env bash
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# origin/<Default-Branch> liegt.
#
# GRUND
# -----
# Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
# Ursache nicht im Diff stand: Es fehlten jeweils genau die Commits, die das
# Gate einfuehrten, an dem der Branch scheiterte. Die Pruefung kostet eine
# Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.
#
# ERSTE REGEL: NIEMALS BLOCKIEREN
# ------------------------------
# Kein Netz, kein Remote, detached HEAD, flatterndes DNS, fehlendes git —
# jeder dieser Faelle geht still durch. Ein Hook, der bei Netzproblemen die
# Arbeit anhaelt, wird nach dem zweiten Mal abgeschaltet und schuetzt danach
# gar nichts. Deshalb: kein `set -e`, jeder Fehlerpfad endet in `exit 0`,
# stderr wird verworfen, und das fetch laeuft unter einer harten Zeitgrenze.

# Bewusst KEIN `set -euo pipefail`: ein fehlgeschlagenes git soll hier nichts
# abbrechen, sondern in den stillen Pfad laufen.

FETCH_TIMEOUT="${KLON_CHECK_TIMEOUT:-5}"   # Sekunden fuer das fetch
STDIN_TIMEOUT=2                            # Sekunden fuer die Hook-Eingabe

# Zeitgrenze fuer einen Befehl. `timeout` ist auf macOS ohne coreutils nicht
# vorhanden; der Rueckfall backgroundet den Befehl und raeumt ihn selbst ab.
_timeout_bin=""
for _cand in timeout gtimeout; do
    if command -v "$_cand" >/dev/null 2>&1; then
        _timeout_bin="$_cand"
        break
    fi
done

mit_zeitgrenze() {
    local sekunden="$1"
    shift
    if [ -n "$_timeout_bin" ]; then
        "$_timeout_bin" "$sekunden" "$@"
        return $?
    fi
    "$@" &
    local pid=$!
    local gewartet=0
    while kill -0 "$pid" 2>/dev/null; do
        if [ "$gewartet" -ge "$sekunden" ]; then
            kill -TERM "$pid" 2>/dev/null
            sleep 1
            kill -KILL "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            return 124
        fi
        sleep 1
        gewartet=$((gewartet + 1))
    done
    wait "$pid"
}

# git darf unter keinen Umstaenden nach Zugangsdaten fragen — ein wartender
# Prompt ist genau das Blockieren, das hier ausgeschlossen sein soll.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=true
export SSH_ASKPASS=true
export SSH_ASKPASS_REQUIRE=never
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new"

still_raus() { exit 0; }

# --- Hook-Eingabe: nur bei echtem Sessionstart pruefen -----------------------
# SessionStart feuert auch bei `compact` und `clear` mitten in der Sitzung.
# Dann waere die Pruefung bereits gelaufen; ein erneutes fetch kostete nur
# Zeit. Das Lesen von stdin steht unter Zeitgrenze, damit auch eine offene
# Pipe den Sessionstart nicht anhaelt.
eingabe=""
if [ ! -t 0 ]; then
    eingabe="$(mit_zeitgrenze "$STDIN_TIMEOUT" cat 2>/dev/null)"
fi
quelle="$(printf '%s' "$eingabe" |
    sed -n 's/.*"source"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
case "${quelle:-startup}" in
    startup | resume) ;;
    *) still_raus ;;
esac

# --- Repository finden ------------------------------------------------------
projekt="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$projekt" ]; then
    projekt="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)"
fi
[ -n "$projekt" ] && [ -d "$projekt" ] || still_raus
cd -- "$projekt" 2>/dev/null || still_raus

command -v git >/dev/null 2>&1 || still_raus
[ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ] || still_raus

# Frisch geklonter, noch leerer Branch: es gibt kein HEAD zum Vergleichen.
git rev-parse --verify --quiet HEAD >/dev/null 2>&1 || still_raus

# Kein Remote `origin` — etwa ein rein lokales Repo. Nichts zu pruefen.
git remote get-url origin >/dev/null 2>&1 || still_raus

# --- Default-Branch ermitteln, NICHT annehmen -------------------------------
# Mindestens ein Repo im Portfolio nutzt `master`; die Annahme `main` hat dort
# schon einmal einen Branch 15 Commits alt werden lassen, weil `git fetch
# origin main` mit «couldn't find remote ref main» scheiterte und das wie ein
# Netzproblem aussah.
default_branch="$(mit_zeitgrenze "$FETCH_TIMEOUT" git ls-remote --symref origin HEAD 2>/dev/null |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' | head -1)"

# Rueckfall ohne Netz: der lokal zwischengespeicherte Zeiger von origin/HEAD.
if [ -z "$default_branch" ]; then
    default_branch="$(git symbolic-ref --short --quiet refs/remotes/origin/HEAD 2>/dev/null |
        sed 's|^origin/||')"
fi

# Weder Remote noch Zwischenspeicher: still raus. Hier NICHT auf `main`
# raten — ein Rateschritt ist genau der Fehler, den dieser Hook verhindert.
[ -n "$default_branch" ] || still_raus

# --- fetch unter Zeitgrenze -------------------------------------------------
mit_zeitgrenze "$FETCH_TIMEOUT" git \
    -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=3 \
    fetch --quiet --no-tags --no-recurse-submodules origin "$default_branch" \
    >/dev/null 2>&1 || still_raus

ziel="$(git rev-parse --verify --quiet FETCH_HEAD 2>/dev/null)"
[ -n "$ziel" ] || still_raus

# --- Abstand zaehlen --------------------------------------------------------
# Funktioniert auch bei detached HEAD; gemeldet wird der Stand, nicht der Name.
fehlend="$(git rev-list --count HEAD.."$ziel" 2>/dev/null)"
case "$fehlend" in
    '' | *[!0-9]*) still_raus ;;   # unlesbar -> still raus
    0) still_raus ;;               # aktuell  -> schweigen
esac

hier="$(git symbolic-ref --short --quiet HEAD 2>/dev/null)"
[ -n "$hier" ] || hier="detached HEAD ($(git rev-parse --short HEAD 2>/dev/null))"

commit_wort="Commits"
[ "$fehlend" = "1" ] && commit_wort="Commit"

cat <<MELDUNG
[Klon-Aktualitaet] $hier liegt $fehlend $commit_wort hinter origin/$default_branch.

Vor der Arbeit aktualisieren: git merge FETCH_HEAD  (oder: git pull origin $default_branch)

Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht --
es fehlen dann genau die Commits, die das Gate einfuehrten, an dem der Branch
scheitert. Erst aktualisieren, dann die Gates lokal fahren.
MELDUNG

exit 0
