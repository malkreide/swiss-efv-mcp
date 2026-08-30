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

**Ein 4xx ist kein Nein.** Am 29.8.2026 antwortete `past-publications` in
`swiss-procurement-mcp` auf jede Publikation mit Losen mit HTTP 400. Daraus war
geschlossen worden, die Quelle verweigere diese Auskunft; der Befund stand
datiert im Fixture-Nachweis, ein Test bestätigte ihn, alles blieb grün. Die
Spec desselben Endpunkts führt einen als *optional* deklarierten Parameter
`lotId` — für Publikationen mit Losen ist er Pflicht. Mit ihm antwortet
dieselbe Publikation mit 200. Ein Projekt trug sieben Vorgängerpublikationen,
die der Server als «Quelle nicht erreichbar» wegwarf.

Drei Handgriffe daraus:

- **Die Parameterliste der Spec durchgehen, bevor ein Statuscode eingeordnet
  wird.** «Optional» heisst dort oft «optional für die Mehrheit».
- **Einer deterministischen Absage keinen Wiederholungsrat geben.** «Nicht
  erreichbar, bitte später erneut» ist bei einem 400 falsch und liest sich für
  das Modell wie eine Störung. Den Status mitführen und den fehlenden
  Parameter benennen — den Status, nicht den Antwortkörper.
- **Beide Antworten aufzeichnen, mit und ohne den Parameter.** Eine
  Aufzeichnung nur des Fehlschlags kann nicht zeigen, dass er vermeidbar war;
  dass nur der 400er aufgezeichnet war, ist der Grund, warum der falsche
  Befund nicht auffiel.

**Und ein 403 ist gar keine Auskunft.** Am 29.8.2026 sollten für 42 Repos die
Dependabot-Labels nachgemessen werden. Alle 13 Abfragen des ersten Stapels
kamen zurück als:

```
Failed to find label: API rate limit already exceeded for user ID 8864492.
```

Der gefährliche Teil steht vorn: Das Werkzeug verpackt eine Sperre als
Fund-Fehlschlag. Wer die Zeile überfliegt oder nur auf ein leeres Ergebnis
prüft, zählt 39 Repos als «Label fehlt» und hat seine eigene Erschöpfung
gemessen. Das Limit hängt am Konto, nicht am Repo — derselbe Vormittag hatte
es mit 42 eröffneten und 42 gemergten PRs verbraucht.

Das ist der Absatz darüber, andersherum gelesen: dort war ein 400 eine echte,
wiederholbare Antwort und galt als Störung; hier ist eine Störung als Antwort
verpackt. Entscheidend ist nie der Statuscode, sondern ob die Quelle überhaupt
geantwortet hat.

- **Positivkontrolle im selben Repo.** Ein «nicht gefunden» wird erst dadurch
  zur Messung, dass eine gleichzeitige Abfrage etwas findet.
- **Die Messung entlang der Sperre teilen.** `raw.githubusercontent.com` ist
  ein CDN und nicht die REST-API. Um 11:19:27 UTC lieferte es für
  `register-mcp` HTTP 200, während die Label-Abfrage desselben Repos in
  derselben Minute die Sperre meldete. Alle 42 `dependabot.yml` kamen so
  durch, während die Label-Hälfte stand.
- **Am Token vorbei geht es nicht.** Beide Umwege enden am Agent-Proxy, und
  jeder mit einer eigenen irreführenden Begründung. `api.github.com` ohne
  Zugangsdaten:

  ```
  GitHub access is not enabled for this session. An org admin must connect
  the Claude GitHub App for this organization.
  ```

  Das ist keine Aussage über die Organisation, sondern das, was ohne Token
  kommt. Wer ihr folgt, sucht einen Admin für ein Problem, das keiner hat.
  Die HTML-Seite `github.com/<owner>/<repo>/labels` fällt ebenfalls, aber
  anders:

  ```
  This GitHub API path is not available: sessions are bound to their
  configured repositories. Use repository-scoped endpoints
  (repos/{owner}/{repo}/...).
  ```

  Der Proxy behandelt also auch `github.com` als API-Pfad; die zweite Meldung
  klingt nach einem Scope-Problem und ist doch nur dieselbe Sackgasse. Den
  Token aus der Umgebung in einen curl-Header zu setzen, blockiert der
  Klassifikator. Ob es überhaupt hülfe, ist offen: die Sperre nennt ein
  Nutzerkonto, und ob der Token zu diesem gehört, wurde nie geprüft.
- **Die Sperre gilt nicht dem Dienst, sondern dem Zugangspfad.** Unmittelbar
  nachdem eine Abfrage der Checks eines PR sauber durchlief, meldete die
  Label-Abfrage weiter die Sperre. Von einem blockierten Werkzeug also nicht
  auf «GitHub ist zu» schliessen — und umgekehrt eine gelungene Abfrage nicht
  als Entwarnung für die gesperrte nehmen. Das ist dieselbe Asymmetrie wie
  bei der verschwundenen Codex-Meldung weiter unten.

Wann die Sperre fällt, geben diese Beobachtungen nicht her. Die Meldung nennt
keinen Zeitpunkt, und die `X-RateLimit`-Kopfzeilen sind hinter dem Proxy nicht
zu sehen. Belegt sind drei gesperrte Zeitpunkte — 11:14, 11:16 und 11:19 UTC.
Wer daraus eine Dauer macht, hat sie erfunden.

**Dieselbe Falle bei einer Konfigurationsoption: die Vorgabe lesen, bevor man
einen Schlüssel für wirkungslos hält.** Am 29.8.2026 fielen die
`labels:`-Zeilen aus den `dependabot.yml` des Portfolios, begründet mit
«Dependabot legt Labels nicht an». Eine Messung danach zeigte, dass
`dependencies` in 36 von 42 Repos sehr wohl existiert, 35 davon mit GitHubs
Standardbeschreibung. Das las sich zuerst wie ein Beleg, dass die Aktion
falsch war.

Die Optionsreferenz kehrt es um:

```
Dependabot creates these default labels automatically, as necessary in
your repository.

If you define more than one package manager, an additional label for the
ecosystem or language is added to each pull request.

The labels specified are used instead of the default labels.
```

Ohne `labels:` vergibt Dependabot also `dependencies` — und, sobald mehr als
ein Paketmanager deklariert ist, zusätzlich ein Ökosystem-Label — und legt sie
selbst an; eine eigene Liste **ersetzt** diesen Satz, und «if any of these
labels is not defined in the repository, it is ignored». Die Zeile war nicht
wirkungslos — sie tauschte einen sich selbst pflegenden Vorgabesatz gegen eine
starre Liste.

**Die Bedingung nicht weglassen.** Bei nur einem Paketmanager steht das
Ökosystem-Label gar nicht zu; wer es dort trotzdem erwartet, schreibt genau
den Fehlbefund auf, gegen den dieser Abschnitt geschrieben ist — der Abschnitt
liefe an sich selbst vorbei. Im Portfolio deklariert jede `dependabot.yml`
zwei (`pip` und `github-actions`), die Bedingung ist hier also überall
erfüllt; anderswo nicht unbedingt. Aufgefallen ist die fehlende Bedingung
nicht beim Schreiben, sondern durch einen Codex-Review auf
`swiss-environment-mcp` PR #113 — vierzehn Sekunden vor dem Merge desselben
PR.

Was das kostet, ist an `openlex-mcp` gemessen: zwei Ökosysteme deklariert,
also stünden `dependencies` **und** ein Ökosystem-Label zu; vorhanden ist nur
das erste, `github-actions` und `github_actions` fehlen beide (Kontrolle `bug`
vorhanden). `register-mcp` ist die Gegenprobe: dort existieren alle vier
deklarierten Namen mit handgeschriebener Beschreibung, die Liste ist gewollt
und vollständig.

**Dreimal falsch eingeordnet, in drei Richtungen.** Erst die Zeile für bloss
wirkungslos gehalten. Dann die gefundenen Labels für einen Widerspruch. Dann,
auf denselben Fund gestützt, einen richtigen PR geschlossen mit dem Argument,
das Label existiere ja — obwohl es existiert, *weil* die Vorgabe es anlegt.
Der dritte Fehler ist der teuerste, weil er wie eine Messung aussah.

Was die Messung **nicht** hergibt: wer die 36 Labels angelegt hat. Die
Referenz sagt, Dependabot tue es; die Objekt-IDs liegen aber so dicht
beieinander, dass sie eher aus einem Stapellauf stammen. Beides passt zum
Befund, keines ist belegt — die Herkunft blieb ungemessen.

Beim Aufräumen gilt deshalb dieselbe Frage wie bei `lotId`: Was ist die
*Vorgabe*, wenn man das Ding weglässt — nicht bloss, ob der aktuelle Wert
etwas bewirkt.

**`results[0]` ist nur so verlässlich wie die Zusicherung danach.** Pinnt die
Abfrage einen bekannten Datensatz, ist der erste Treffer eine Drift-Wache und
in Ordnung. Hängt die Zusicherung dagegen davon ab, *welche* Variante die
Quelle heute zuoberst hat, prüft der Test den Tag: am 25.8.2026 rot, weil die
neueste Zürcher Publikation zufällig Lose hatte, am 26.8. grün, ohne dass sich
etwas geändert hätte. Den Fall gezielt wählen und beide Zweige fahren.

## Wenn Codex gar nicht erst hinsieht

Die Zeile oben unterstellt, dass es einen Befund geben *kann*. Das ist nicht
immer so, und man sieht es dem PR nicht an.

Am 21.8.2026 war das Code-Review-Kontingent zwischen 08:41 und 09:48
aufgebraucht — davor echte Reviews, danach in 30 Repos nur noch:

```
You have reached your Codex usage limits for code reviews.
```

Wie lange die Sperre dauerte, geben die Beobachtungen nur als Spanne her. Vier
Zeitpunkte sind belegt: letzter gelungener Review am 21.8. um 08:41, erste
Limit-Meldung um 09:48, letzte beobachtete Limit-Meldung am 22.8. um 11:03,
erste *andere* Meldung am 23.8. um 08:22.

Zwischen erster und letzter Limit-Meldung liegen **25 h 15 min**. Das ist der
Abstand zweier Fehlschläge, nicht die Dauer einer Sperre. Wer ihn Untergrenze
nennt, hat die durchgehende Erschöpfung schon vorausgesetzt, die er belegen
soll: Öffnete sich das Fenster zwischendurch und schloss es sich durch neue
Auslöser wieder, waren es zwei kurze Sperren und nie eine von 25 Stunden.
Untergrenze einer *einzelnen* Sperre sind die 25 h 15 min nur unter genau dieser
Annahme — und die ist unbelegt.

Nach oben trägt die Rechnung dagegen. Die längste mit den Beobachtungen
verträgliche Sperre reicht vom letzten Erfolg um 08:41 bis zur abweichenden
Meldung um 08:22, also **47 h 41 min**; länger kann keine einzelne gewesen sein.
Wer stattdessen ab der ersten Limit-Meldung rechnet, unterschlägt die 67
Minuten, in denen das Kontingent schon weg gewesen sein kann, und nennt die
Spanne zwischen zwei Beobachtungen eine Obergrenze.

Beobachtungspunkte sind keine Messreihe — die 21 Stunden vor der abweichenden
Meldung liefen ganz ohne Codex-Auslöser, dort hat niemand gemessen.

In der Zwischenzeit sind 32 PRs mit formal erfülltem Häkchen gemergt worden,
ohne dass jemand hineingesehen hat, und am 22.8. noch einmal 43.

**Fünf** Gründe, warum Codex schweigt, und nur einer davon ist harmlos:

- **Kein Befund** — dann schreibt er einen gewöhnlichen Issue-Kommentar:

  ```
  Codex Review: Didn't find any major issues. Swish!
  ```

  Der Schlusssatz wechselt bei jedem Lauf («Delightful!», «Keep it up!»,
  «More of your lovely PRs please.»); stabil ist nur der Satz davor.
- **Der PR ist ein Draft** — die *automatischen* Auslöser greifen dort nicht.
  Von Hand angestossen läuft Codex sehr wohl auf einem Draft: am 29.8.2026 auf
  `swiss-efv-mcp#64`, 16 Sekunden nach dem Anlegen, Auslöser «Manual request».
  Das ist zugleich der Weg, einen Draft prüfen zu lassen, **bevor** man ihn auf
  ready stellt — und damit das Gegenmittel zu den Sekunden zwischen «ready» und
  Merge weiter unten.
- **Das Kontingent ist weg** — dann schreibt er die Meldung oben.
- **Codex meldet eine fehlende Environment** — dann schreibt er:

  ```
  To use Codex here, create an environment for this repo.
  ```

  «Meldet», nicht «fehlt»: Der Text ist keine verlässliche Auskunft über die
  Konfiguration — am 29.8.2026 stand er in einem Repo, das eine hatte, und war
  eine Minute später weg; am 30.8. kam acht Sekunden nach ihm der Lauf, den sie
  für unmöglich erklärte, ohne zweiten Anstoss. Erst abwarten, dann
  wiederholen, dann konfigurieren; beide Messungen stehen unten im Abschnitt
  über die Environment.
- **Es lief gar kein Auslöser** — und ein Push ist keiner. Codex zählt sie
  selbst im Infokasten auf: einen PR zum Review öffnen, einen Draft auf ready
  stellen, «@codex review» kommentieren. Wer einen Befund behebt und pusht,
  bekommt deshalb keinen zweiten Lauf, sondern gar nichts.

Der vierte kam erst zum Vorschein, als der dritte wegfiel, und das ist kein
Zufall: Die Prüfungen liegen hintereinander. Dass es diese Reihenfolge ist und
nicht die umgekehrte, lässt sich an einem einzigen Repo ablesen — in
`swiss-public-data-mcp` bekam PR #54 am 22.8. um 10:56:55 die Kontingent-Meldung
und PR #56 am 23.8. um 08:22:20 die Environment-Meldung. Läge die
Environment-Prüfung vorn, hätte #54 sie schon am Vortag gesehen; die Environment
fehlte ja bereits. Zwei Meldungen aus demselben Repo schlagen hier jede
Vermutung über die Reihenfolge.

Diese Ableitung hat eine Voraussetzung, die seit dem 29.8.2026 nicht mehr
sicher ist: dass die Environment am 22.8. schon fehlte. Geschlossen wurde das
aus der Meldung vom 23.8. — und die Meldung ist, wie unten gemessen, kein
verlässlicher Beleg für eine fehlende Environment. Die Reihenfolge kann
weiterhin stimmen; ihr Beweis steht auf einer Annahme, die niemand geprüft hat.

Praktisch heisst das: **Eine verschwundene Limit-Meldung ist keine Entwarnung.**
Sie kann bedeuten, dass das Kontingent wieder da ist — und dass jetzt etwas
anderes den Review verhindert. Belegt ist eine Prüfung erst durch ein
Review-Objekt **oder** eine Befundlos-Meldung — **und beide zählen nur für den
Commit, den sie selbst nennen** (weiter unten, «Nennt das jüngste
Codex-Ergebnis den aktuellen Head»). Wer nur das Objekt gelten lässt, zählt
jeden befundlosen Review als ungeprüft — und baut sich denselben Fehlalarm ein,
den dieser Abschnitt verhindern soll, nur in die andere Richtung.

«Kein Kommentar» heisst also nicht «geprüft und sauber». Unterscheiden lässt es
sich an der Form, aber nur für zwei der vier: Ein Review **mit** Befund ist ein
Review-Objekt («💡 Codex Review», mit Commit-Angabe), ein Review **ohne** Befund
ein gewöhnlicher Issue-Kommentar. **Die beiden Ausfallmeldungen — Kontingent wie
Environment — sind an der Form nicht festzumachen**: Sie erscheinen als
Issue-Kommentar *oder* als Review-Kommentar in einem Thread und trennen sich
untereinander nur im Text.

Der zweite Ort ist am 30.8.2026 auf `swiss-efv-mcp#70` gemessen: Die
Environment-Meldung stand dort im Thread, acht Sekunden nach einer Antwort in
genau diesem Thread. Wer die Ausfallmeldungen nur unter den PR-Kommentaren
sucht, übersieht sie.

(Ob die Thread-Antwort selbst ein Auslöser ist, gibt die Messung nicht her —
belegt ist nur, dass die Meldung acht Sekunden danach kam. Der Infokasten
zählt sie nicht auf.)

Beim Draft greift ohne
manuellen Anstoss kein Auslöser, dort steht dann überhaupt nichts; ein
kommentarloser Draft ist deshalb kein Beleg, sondern ein nicht durchgeführter
Test. Ein von Hand angestossener Lauf hinterlässt dagegen auch auf einem Draft
dieselben Spuren wie sonst — Statusbericht, Review-Objekt oder
Befundlos-Meldung —, und die zählen dort genauso.

Der fünfte Grund ist der gefährlichste, weil er nicht wie eine Lücke aussieht,
sondern wie ein Beleg: Nach einem Push steht das Review-Objekt des *vorigen*
Commits weiter im PR. Am 29.8.2026 auf `swiss-efv-mcp#62` — Review auf
`cd2046c` um 11:58:08 (Auslöser «Draft marked ready») mit einem P2-Befund; Fix
als `ca00672` gepusht, dessen CI um 12:01:47 durch war; um 12:02 nannte die
Zusammenfassung weiterhin nur `cd2046c` und war seit 11:58:12 nicht angefasst.
Erst ein «@codex review» von Hand erzeugte um 12:02:55 den zweiten Lauf, der um
12:05:23 befundlos endete. Ohne ihn wäre ausgerechnet der Fix-Commit ungeprüft
geblieben, während im PR ein echtes Review stand und das Häkchen erfüllt
aussah — dieselbe Klasse wie die drei bis fünf Sekunden zwischen «ready» und
Merge weiter unten, nur schwerer zu bemerken, weil hier etwas *da* ist.

Die richtige Frage ist deshalb nie «steht ein Review im PR», sondern **«nennt
das jüngste Codex-Ergebnis den aktuellen Head»**. Wer nach einem Push
weiterarbeiten will, kommentiert «@codex review» — sonst gilt der eigene Fix als
geprüft, ohne es zu sein.

Nur gegen das Review-**Objekt** zu prüfen reicht dafür nicht, und zwar in beide
Richtungen falsch:

- Ein befundloser Lauf erzeugt gar kein Review-Objekt, sondern einen
  Issue-Kommentar. Nach einem befundlosen Wiederholungslauf zeigt das noch
  vorhandene Objekt weiter auf den **alten** Commit — der Head ist geprüft, die
  Prüfung meldet Fehlalarm. Genau so lag es auf `swiss-efv-mcp#62`: Objekt auf
  `cd2046c`, befundloser Lauf auf `ca00672` nur als Kommentar.
- Umgekehrt bleibt eine ältere Befundlos-Meldung nach dem nächsten Push
  einfach stehen. «Es gibt eine Befundlos-Meldung» belegt damit gar nichts.

Zwei Anker, in dieser Reihenfolge:

1. **Der Statusbericht.** Seine Zeile `✅ Completed` nennt den geprüften Commit
   und ist das einzige Objekt, das beide Ausgänge gleich behandelt. Stimmt der
   Commit mit dem Head, ist der Head geprüft — geprüft, nicht notwendig sauber:
   Den Ausgang nennt der Bericht nicht.
2. **Fehlt der Bericht**, trägt jedes Codex-Ergebnis seinen Commit selbst — das
   Review-Objekt wie die Befundlos-Meldung, beide als «Reviewed commit». Dann
   das **jüngste** von beiden nehmen und dessen Commit vergleichen; das ältere
   sagt nichts über den Head.

Was in keinem Fall trägt: die blosse Anwesenheit eines Review-Objekts oder
einer Befundlos-Meldung, ohne den Commit darin zu lesen.

**Zwei Läufe, deren Auslöser vor dem Merge lag, haben ihr Ergebnis verloren.**
Am 30.8.2026 auf `swiss-efv-mcp#68`: «ready for review» um 08:13:31, Merge um
08:13:34, und der dadurch ausgelöste Lauf startete um 08:13:35 — eine Sekunde
*nach* dem Merge. Beim Merge lief also gar nichts; der Lauf war erst ausgelöst.
Um 08:14:41 stand `✅ Completed` auf `34021a9`. Ein Review-Objekt gibt es
nicht, eine Befundlos-Meldung auch nicht.

Als Grund stand hier zuerst «auf einem geschlossenen PR postet Codex sie nicht
mehr». Das ist zu weit gegriffen. Am 30.8.2026 wiederholte sich der Fall auf
`#69` — Merge um 09:56:04, `✅ Completed` auf `85658be` um 09:57:17, kein
Ergebnis —, und ein *danach* um 11:42:47 von Hand angestossener Lauf postete um
11:44:33 ein ganz gewöhnliches Review-Objekt, mit Befund, auf demselben
geschlossenen PR.

Sicher ausgeschlossen ist damit zweierlei: der Zustand des PR beim Posten (beide
Male geschlossen, einmal kam das Ergebnis) und die Frage, ob beim Merge ein Lauf
lief — auf `#68` lief keiner, er war erst ausgelöst.

**Was übrig bleibt, ist nicht isoliert.** Die beiden verlorenen Ergebnisse
stammen aus *automatisch* ausgelösten Läufen, deren Auslöser vor dem Merge lag;
das gelungene aus einem *von Hand* angeforderten danach. Zeitpunkt und
Auslöseweg unterscheiden sich zugleich, und drei Beobachtungen trennen sie
nicht. Belegt ist: **Ein von Hand nach dem Merge angeforderter Lauf postet.**
Die allgemeinere Regel «vorher entfällt, nachher kommt es» ist eine Vermutung,
und sie steht hier als solche.

Die Vorsichtsmassnahme hängt daran ohnehin nicht, und sie ist der Grund, warum
der Unterschied keine Wortklauberei ist. Auf `#68` war beim Merge **kein Lauf zu
sehen** — ausgelöst war er, gestartet nicht —, und sein Ergebnis verfiel
trotzdem. «Es läuft noch nichts» ist also kein sicheres Zeichen. Ob ein Merge
*nach* einem sichtbaren Start das Ergebnis rettet, ist nicht gemessen; wer
sichergehen will, wartet nicht auf den Start, sondern auf das Ergebnis.

Praktisch ist das die gute Nachricht des Abschnitts: Der Ersatz, den er unten
empfiehlt, ist fahrbar. «@codex review» auf dem gemergten PR läuft, und der
geprüfte Commit ist dann der **Merge-Commit** (`21a3224`), nicht der Head des
gemergten Branches.

Übrig bleibt der Statusbericht. Er nennt den geprüften Commit — der Head wurde
also geprüft —, sagt aber nichts über den Ausgang. **Der Ausgang ist in diesem
Fall von aussen nicht feststellbar.**

Naheliegend wäre, ihn aus der 👍-Reaktion am PR zu lesen. Das trägt nicht:

- Das Feld `reactions` aus `issue_read` ist eine **Summe ohne Urheber**. Ein
  Mensch, der die PR-Beschreibung mit 👍 quittiert, erzeugt dasselbe `+1: 1`.
  Zusammen mit `✅ Completed` liesse sich daraus «sauber» ableiten, auch wenn
  Codex einen Befund hatte, der nach dem Merge nicht mehr gepostet wurde.
- Den Urheber nachzuschlagen geht aus den Agent-Sessions nicht: Der
  REST-Endpunkt `/issues/{n}/reactions` ist dort gesperrt, und kein
  MCP-Werkzeug liefert ihn.

Auf `#68` war die Reaktion trotzdem eindeutig — aber nur, weil ausser Codex
niemand den PR angefasst hatte. Das ist ein Sonderfall, keine Regel.

**Der Ausgang des Laufs auf `#68` bleibt dauerhaft unbekannt.** Ein neuer Lauf
holt ihn nicht zurück, er fällt ein eigenes, unabhängiges Urteil — dasselbe Argument wie
weiter unten, wo derselbe Text in 42 Läufen 36-mal einen Befund und 6-mal keinen
bekam. Was bleibt, ist ein Ersatz, keine Rekonstruktion: eine frische Prüfung
auf dem Merge-Commit oder in einem Folge-PR, deren Ergebnis für sich steht.

Ein Statusbericht ohne Ergebnis heisst also «geprüft, Ausgang unbekannt» — und
das ist eine ehrlichere Auskunft als eine Summe, die zwei Urheber nicht trennt.

Das sind verschiedene Abfragen — `get_reviews` fürs Objekt, `get_comments` für
die PR-Kommentare, `get_review_comments` für die Threads; wer nur eine nimmt,
übersieht den Rest. Genau so ist die Limit-Meldung zuerst durchgerutscht, und
die dritte steht hier seit dem 30.8.2026, weil die Environment-Meldung auf `#70`
in einem Thread lag und `get_comments` sie nicht zeigte. «Alles andere» deckt
`get_comments` ohnehin nicht ab: Die Reaktion am PR liegt in keiner der drei —
sie steht im Feld `reactions` von `issue_read`, und weil das eine Summe ohne
Urheber ist, taugt sie ohnehin nicht als Beleg (oben, und weiter unten
ausführlicher).

Der Kommentarzähler allein reicht ohnehin nicht: `comments: 1` kann die
Befundlos-, die Kontingent- **oder** die Environment-Meldung sein — und seit dem
29.8.2026 auch einen blossen Statusbericht, der überhaupt kein Ergebnis meldet:

```
## Codex Review Summary

| Review         | Status                     | Commit    | Review trigger |
| 📝 Code Review | 🔄 Running since 12:02:55  | ca00672   | Manual request |
```

Vier gegensätzliche Bedeutungen unter derselben Zahl. Den Text lesen, nicht die
Zahl. Und einen unbekannten fünften Text wörtlich zitieren, statt ihn in eine
der bekannten Schubladen zu zwingen: Dieser Abschnitt musste schon zweimal
wachsen — von drei auf vier Gründe und dann auf fünf.

Dieser Bericht trägt den HTML-Marker `codex-pull-request-review-summary` und
wird **an Ort und Stelle aktualisiert**, nicht neu geschrieben. Die
Fertigmeldung («✅ Completed») kam deshalb als `issue_comment.edited`: Wer auf
einen *neuen* Kommentar wartet, verpasst sie, und wer den Zähler beobachtet,
sieht gar nichts, weil er sich nicht ändert. Dass «Running» dort steht, heisst
warten, nicht urteilen — ein Lauf ohne Ergebnis ist weder Befund noch Freispruch.

Sein eigentlicher Wert steht in der Spalte daneben: Der Bericht nennt den
geprüften Commit und den Auslöser, beantwortet also genau die Frage, die der
fünfte Grund oben aufwirft.

**Zur 👍-Reaktion: zwei Fassungen lang wurde am falschen Objekt gemessen.**
Hier stand, der Infokasten sei keine Quelle — belegt mit sechs Repos am 23.8., in
denen die Befundlos-Meldung kam «und in keinem die Reaktion». Gesucht wurde an
den Kommentaren jener Läufe; dort war keine.

Die Reaktion sitzt **am PR** — mit einer Einschränkung, die zwei Absätze weiter
unten steht. Am 29.8.2026 auf `swiss-efv-mcp#64` durchgemessen,
an einem PR, den ausser Codex niemand angefasst hatte:

| Zeitpunkt | Zustand des Laufs | Reaktionen am PR |
|---|---|---|
| 16:54:30 | gestartet | `eyes: 1` |
| 16:56:27 | fertig, **mit** Befund | `total_count: 0` — 👀 wieder entfernt |

Und auf `#62` nach einem befundlosen Lauf: `+1: 1` am PR, `0` an jedem der drei
Kommentare. Codex setzt die Reaktion also, nimmt sie zurück und unterscheidet
die Ausgänge — genau wie der Kasten es beschreibt («reacts with 👀 while any
review is running … reacts with 👍 once all reviews finish with no findings»).

Die alte Zeile war damit nicht vorsichtig, sondern **falsch**: Sie hat aus einer
Messung am falschen Ort auf eine Lüge geschlossen. Der Kasten stimmt hier.

**Ein fester Ort ist es trotzdem nicht.** Am 30.8.2026 setzte ein per
«@codex review» angestossener Lauf sein 👀 auf **den auslösenden Kommentar**
(`swiss-efv-mcp#69`, `eyes: 1` um 11:42:47), nicht auf den PR. Das 👍 dagegen
sass auf `#62` nach einem ebenfalls per Kommentar angestossenen Lauf am PR und
an keinem der drei Kommentare. Beide Orte abfragen; welcher trägt, hängt am
Auslöser und am Ausgang, und keiner von beiden ist aus dem anderen zu erraten.

Das ändert nichts an der Beweisregel, sondern nur an ihrer Begründung: Belegt
ist eine Prüfung durch ein Review-Objekt oder eine Befundlos-Meldung, das
jeweils den aktuellen Head nennt. Die Reaktion taugt dafür nicht — und der
Grund ist genau der Commit: Sie nennt keinen und wird beim nächsten Lauf
überschrieben. Sie sagt «gerade läuft etwas» oder «der letzte Lauf war sauber»,
nie «dieser Head ist geprüft».

Das gilt auch im Merge-vor-dem-Ergebnis-Fall oben, wo sie als einzige Quelle
für den Ausgang übrig zu bleiben scheint: Die Summe im Feld `reactions` trennt
Codex nicht von einem Menschen, und den Urheber liefert hier kein Werkzeug.
Was dort fehlt, ersetzt ein neuer Lauf — er fällt ein eigenes Urteil, er holt
das alte nicht zurück. Eine Reaktion liefert es erst recht nicht.

Und ein befundloser Lauf ist kein Freispruch. Am 23.8. lief derselbe Text durch
42 Reviews: 36 meldeten denselben P2-Befund, 6 die Befundlos-Meldung — gleiche
Eingabe, gegenteiliges Urteil, alles in denselben neun Minuten. Ein sauberer
Lauf sagt damit etwas über den Lauf, nicht über den Text. Wer sein Häkchen
daran hängt, hängt es an einen Münzwurf.

Portfolio-weit nachsehen:

```
search_pull_requests: user:malkreide commenter:chatgpt-codex-connector[bot] updated:>=<Datum>
```

Findet nur, wo er *kommentiert* hat. Repos ohne PR-Aktivität tauchen nicht auf
— das ist kein Beleg, dass dort geprüft wurde.

Zweiter Weg, den Prüfer zu verlieren, ganz ohne Kontingentproblem: zu schnell
mergen. Am 21./22.8. lagen zwischen «ready for review» und Merge mehrfach drei
bis fünf Sekunden. Codex wird beim Umschalten von Draft auf ready ausgelöst und
braucht danach Zeit; wer sofort mergt, hat das Häkchen gesetzt und den Review
nicht abgewartet.

Das Kontingent hängt am Konto, nicht am Repo, und Code-Reviews haben einen
eigenen Topf — nur GitHub-getriggerte Reviews zählen hinein. ChatGPT-Pläne
fahren ein rollendes Fünf-Stunden-Fenster plus Wochenlimits; welches greift,
steht im Codex-Dashboard. Welches hier griff, ist **offen**. Die Lücke oben
schliesst das Fünf-Stunden-Fenster nicht aus: Es kann sich zwischendurch
geöffnet und durch neue Auslöser wieder erschöpft haben. Das auszuschliessen
bräuchte den Nachweis, dass in der ganzen Spanne kein einziger Review durchlief
— den gibt es nicht, weil nur Fehlschläge beobachtet wurden. Eine lange Reihe
von Fehlschlägen belegt eine lange Reihe von Fehlschlägen, nicht ihre Ursache.

Zeigt das Dashboard freies Kontingent, während Reviews weiter scheitern, ist
das ein bekannter Fehler bei mehreren verbundenen Konten — dann den
GitHub-Connector in den Codex-Einstellungen trennen und neu verbinden.

Die Environment legt man unter `chatgpt.com/codex/cloud/settings/environments`
an, und zwar **je Repo**. Am 23.8. sah es genau danach aus: In
`swiss-public-data-mcp` kam kein Review, in den übrigen Repos lief Codex am
selben Morgen durch. Eine Environment fürs Konto genügt also nicht — wer eine
anlegt und den Rest für erledigt hält, mergt weiter Ungeprüftes.

**Die Meldung selbst ist aber kein Beleg dafür, dass eine fehlt.** Am
29.8.2026 auf `swiss-efv-mcp#66`:

| Zeit (UTC) | Ereignis |
|---|---|
| 16:56, 17:01, 17:05 | drei Codex-Reviews in diesem Repo, alle durchgelaufen |
| 18:38:34 | «To use Codex here, create an environment for this repo» |
| 18:39:34 | nach «@codex review»: Lauf startet normal, auf demselben Commit |
| 18:44:28 | befundlos fertig |

Sechzig Sekunden zwischen der Meldung und einem gelungenen Lauf, dasselbe Repo,
derselbe Commit, an den Einstellungen nichts geändert. Der Text behauptet eine
Konfigurationslücke; belegt ist nur, dass kein Lauf zustande kam.

**Und es braucht nicht einmal den zweiten Anstoss.** Am 30.8.2026 auf
`swiss-efv-mcp#70` folgte auf **einen einzigen** «@codex review» erst um
11:51:56 die Meldung und dann um 11:52:04 der Start eines gewöhnlichen Laufs,
Auslöser «Manual request», acht Sekunden später, ohne dass jemand etwas tat.
Der Lauf endete um 11:54:08 mit einem Befund. Die Meldung war hier also nicht
einmal ein verlorener Lauf, sondern eine Zwischenmeldung des Laufs, der ohnehin
kam.

Das ist dieselbe Klasse wie der 403 weiter oben — eine Störung, als Auskunft
verpackt —, aber mit der **umgekehrten** Handlungsanweisung als beim 400er:

- Beim 400er war die Absage deterministisch und wiederholbar; ein
  Wiederholungsrat wäre dort falsch gewesen, gesucht werden musste der fehlende
  Parameter.
- Hier trennt genau ein Wiederholungslauf «stabil» von «Aussetzer», und er
  kostet nichts. **Erst abwarten, dann wiederholen, dann konfigurieren** — das
  Abwarten steht seit `#70` vorn, weil der Lauf dort ganz von selbst kam. Wer der Meldung
  sofort folgt, legt eine Environment an, die es schon gibt, und hält das
  Problem danach für gelöst.

Wiederholt sich die Meldung, ist sie stabil — dann gilt der Absatz darüber und
die Environment fehlt wirklich.

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

**ruff:** genau eine Quelle — `ruff==0.16.3` im `dev`-Extra von
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
