# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Hinzugefügt

- **Die fünf Offline-Gates laufen jetzt auch nachts** (`.github/workflows/nightly.yml`,
  cron `41 3 * * *`). `ci.yml` läuft bei Push und Pull Request; eine Codebasis,
  die niemand anfasst, wurde damit nie wieder geprüft — und kann trotzdem
  kaputtgehen, weil jede Abhängigkeit mit offener Untergrenze bei der nächsten
  frischen Installation etwas anderes auflöst.

  Genau das ist passiert: `fastmcp>=3.4` löste am 18.9.2026 zu fastmcp 4 auf,
  vier Gates fielen, und der letzte grüne Lauf auf `main` stammte vom 30.8. —
  **drei Wochen latent rot**, ohne dass ein Commit die Ursache trug und ohne
  dass es jemand sah, weil in dieser Zeit niemand gepusht hat. `live.yml` fängt
  das nicht: es prüft die Datenquelle, nicht die Gates.

  Der Workflow enthält die Gates **nicht selbst**, sondern ruft `ci.yml` per
  `workflow_call` auf. Zwei Listen, die sich stumm einigen müssen, sind eine zu
  viel — dieselbe Konstruktion, an der hier schon der ruff-Pin gescheitert ist.
  Ein nächtliches Gate, das eine andere Version fährt als das im PR, ist
  schlimmer als keines: es sieht nach Deckung aus.
  `tests/test_nightly_gates.py` fällt an dem Tag, an dem jemand die Schritte
  hineinkopiert — auch dann, wenn beide Kopien in dem Moment dasselbe sagen.

- **`scripts/nightly_issue.cjs`** meldet den Befund als Issue: öffnen,
  kommentieren, schliessen. Ein grüner Lauf schliesst den Thread von selbst,
  ein einzelner Aussetzer des Index heilt also über Nacht. **Drei Zustände,
  nicht zwei:** ein abgebrochener Lauf (`cancelled`) hat die Gates nicht
  gefahren und sagt nichts über den Branch — er öffnet nichts und schliesst
  nichts. Das ist der Zustand, an dem `if: failure()` scheitert.

### Geändert

- **`tests/test_live_issue.py` heisst jetzt `tests/test_js_suiten.py`** und
  findet die JS-Suiten per Glob statt eine einzelne beim Namen zu nennen. Als
  die zweite Suite dazukam, waren zwei Wege offen: den Harness kopieren oder
  ihn öffnen. Kopieren hätte die Zählung mitverdoppelt, die eine echte Falle
  abdeckt (eine Datei ohne Test meldet unter `node --test` genau
  `# pass 1`) — und damit die Möglichkeit, dass die Kopien auseinanderlaufen.
  Der Glob nimmt die nächste Suite ausserdem mit, ohne dass jemand daran denkt.

- **`ci.yml` hat einen `workflow_call`-Auslöser**, damit `nightly.yml` es
  aufrufen kann. An den Gates selbst ändert sich nichts.

## [0.4.0] - 2026-09-26

### Geändert

- **Nativ auf MCP-Spec `2026-07-28`.** `fastmcp>=3.4` löste am 18.9.2026 zu
  fastmcp 4.0.5 auf, das `mcp` 2.2.0 mitbringt — und damit zwei Protokoll-Ären
  statt einer. Die vier Gates, die dieses Repo genau dafür aufgestellt hatte,
  sind gefallen und haben getan, wofür sie da waren:
  `test_das_sdk_kennt_hier_nur_eine_aera`,
  `test_der_pin_ist_die_revision_des_sdk`,
  `test_negotiated_protocol_version_matches_pin` und
  `test_die_routing_header_gehoeren_hierher_sobald_das_sdk_sie_liest`.

  `MCP_PROTOCOL_VERSION` beschrieb **eine** Ära; der Server bedient zwei. Neu
  ist ein Paar: `MCP_MODERN_PROTOCOL_VERSION` (`2026-07-28`, ausgehandelt über
  `server/discover` und einen Umschlag pro Anfrage) und
  `MCP_HANDSHAKE_PROTOCOL_VERSION` (`2025-11-25`, klassischer `initialize`).
  Beide werden gegen die SDK-Konstanten `LATEST_MODERN_VERSION` /
  `LATEST_HANDSHAKE_VERSION` gehalten und zusätzlich mit einer echten
  Verbindung nachgefahren.

  Warum nicht einfach der neuere Wert: `LATEST_PROTOCOL_VERSION` ist in
  `mcp` 2.x ein Alias auf die *moderne* Ära. Wer nur dagegen pinnt, sagt nichts
  darüber, was ein Client der alten Ära bekommt — und der Handshake wird
  weiterhin bedient. Ein Pin, der nur eine Ära beschreibt, sieht geprüft aus
  und ist es zur Hälfte.

- **`Client.initialize_result` trägt die Prüfung nicht mehr.** Auf einer
  modernen Verbindung gibt es keinen `initialize`-Handshake, das Feld ist
  `None`. Die alte Zusicherung fiel dort mit einem `AttributeError` auf
  `NoneType` — also mit einer Meldung, die nach kaputtem Test klingt statt nach
  Ärenwechsel. Geprüft wird jetzt über `protocol_version`, den ärenneutralen
  Zugang; ein eigener Test hält den Grund fest, damit niemand die alte Form
  zurückbaut.

- **`fastmcp>=4.0` statt `>=3.4`.** Ein Boden, keine Kosmetik: erst fastmcp 4
  zieht `mcp` 2.x herein, und erst dort existiert die Revision `2026-07-28`
  überhaupt. Unter `>=3.4` konnte eine frische Installation still bei
  `2025-11-25` landen, während READMEs und Pin etwas anderes sagten.

- **Die `logging`-Capability ist mit `2026-07-28` abgekündigt (SEP-2577).** Die
  Tool-Handler schickten auf jeder Anfrage ein `ctx.debug(...)` — eine
  Benachrichtigung über genau die Capability, die diese Revision abkündigt. Die
  Diagnose pro Aufruf liegt jetzt im structlog-Strom auf stderr, wo die README
  sie ohnehin verortet. `report_progress` ist **nicht** betroffen und bleibt;
  ein eigener Test hält das fest, damit «keine Benachrichtigungen mehr» nicht
  versehentlich auch die Fortschrittsmeldung mitnimmt.

### Hinzugefügt

- **Die drei Routing-Header in der CORS-Freigabeliste.** Jede Anfrage der
  modernen Ära trägt `Mcp-Protocol-Version`, `Mcp-Method` und — bei
  `tools/call` — `Mcp-Name`; `classify_inbound_request` weist eine Anfrage, bei
  der sie nicht zum Umschlag passen, mit `HEADER_MISMATCH` (-32020) ab. Ein
  Browser-Client, dem der Preflight diese Header verbietet, kommt gar nicht
  erst bis dorthin. Die Namen stehen nicht als Literal in der Liste, sondern
  werden im Test gegen `mcp.shared.inbound` gehalten.

  `Mcp-Param-*` bleibt bewusst draussen. Eine CORS-Freigabeliste kann kein
  Präfix ausdrücken, und ein Client sendet solche Header nur für Parameter,
  deren Schema die Annotation `x-mcp-header` trägt — kein Tool dieses Servers
  tut das. `test_kein_tool_verlangt_einen_mcp_param_header` fällt an dem Tag,
  an dem eines sie bekommt.

### Behoben

- **Drei neue `source`-Marken der EFV.** Am 22.9.2026 (Last-Modified 08:54:56
  UTC) veröffentlichte die EFV `main_extern.csv` neu, mit den Planjahren des
  Bundes zurück in der Datei und drei Marken, die keine frühere Fassung trug:
  `Budget/Finanzpläne` (207 Zeilen, `bund` 2027–2030, `sv` 2026–2030),
  `Hochrechnung` (23, `bund` 2026) und `Umfrage Budget` (23, `ktn` 2026).
  `is_projection` gab für sie `None` zurück, `fiscal_headline` kennzeichnete
  die Jahre 2026–2030 des Bundes nicht als Prognose. Gemeldet hat es der
  Live-Wächter `test_live_source_vocabulary_is_fully_mapped` mit allen drei
  Namen (Lauf vom 23.9.2026, der zweite rote in Folge).

  Alle drei gelten jetzt als vorausschauend — eingeordnet nach den Zeilen,
  auf denen sie stehen, nicht nach dem Wortlaut: nur 2026 und später, während
  `Rechnung` überall 2025 endet, und kein Schlüssel trägt zwei Marken.

- **`serverInfo.version` meldete die Version von FastMCP statt der eigenen.**
  Ohne `version=` im `FastMCP`-Konstruktor fällt FastMCP auf seine eigene
  Distributionsversion zurück: gemessen am 18.9.2026 meldete dieser Server
  `4.0.5` statt `0.4.0`. Das fällt nicht auf, weil beides plausible Versionen
  sind — ein Client, der die Serverversion protokolliert oder gegen bekannte
  Fehler abgleicht, bekam die Nummer einer fremden Bibliothek. Die Zusicherung
  prüft beides: gegen `__version__` *und* gegen die fastmcp-Version, weil die
  erste Hälfte allein auch bei zufälliger Gleichheit grün bliebe.

- **`EFV_MCP_LOG_LEVEL` war wirkungslos.** `configure_logging` hatte einen
  `if _configured: return`-Wächter, und `client.py` wie `_otel.py` holen ihren
  Logger auf Modulebene — also schon während `from .server import mcp`, bevor
  `main()` überhaupt die Settings gelesen hat. Der Level stand damit auf der
  Vorgabe `INFO`, und `configure_logging(settings.log_level)` lief als No-op
  durch. Gemessen auf dem Stand davor: `EFV_MCP_LOG_LEVEL=DEBUG` gesetzt,
  `settings.log_level` las `DEBUG`, effektiver Root-Level blieb `INFO`. Nichts
  wurde dabei rot.

  Kein Nebenschauplatz: die Diagnose, die oben aus `ctx.debug` in den
  structlog-Strom gewandert ist, wäre dort sonst unsichtbar geblieben.
  `configure_logging` ist jetzt idempotent *pro Level* statt pro Prozess; ein
  anderer Level konfiguriert um. `logging.basicConfig` allein genügt dafür
  nicht — der Aufruf ist ein No-op, sobald der Root-Logger Handler hat.

### Behoben

- **Die EFV stellte die `source`-Spalte auf Deutsch um — `is_projection` fiel
  für jede Zeile auf `None`.** Am 27.8.2026 wurde
  `fs_dashboard/main_extern.csv` neu veröffentlicht (Last-Modified 07:06 UTC),
  mit `Rechnung` statt `Financial statements`, `Prognosen` statt `Forecasts`
  und `Vorhandene Daten` statt `Data available`. Sonst änderte sich nichts:
  gleiche URL, gleiche Kopfzeile, gleiche sieben Spalten, HTTP 200.

  Damit kannte `_PROJECTION_SOURCES`/`_ACTUAL_SOURCES` keine einzige der 6110
  Zeilen mehr, und `fiscal_headline` kennzeichnete produktiv keinen Punkt mehr
  als Prognose. Kein Unit-Test sah es — sie fahren auf handgeschriebenen und
  aufgezeichneten Zeilen, beide englisch. Die Live-Suite fiel in der Nacht
  darauf, aber nur als zwei zusammenhanglose `assert False`; dass der Wortschatz
  gewechselt hatte, stand in keiner Meldung.

  Beide Wortschätze sind jetzt abgebildet. Der englische bleibt: Die
  Aufzeichnung vom 14.8.2026 trägt ihn, und eine Quelle, die einmal die
  Sprache wechselt, kann zurückwechseln. Für die vier englischen Marken ohne
  heute belegte deutsche Entsprechung wird **keine** Übersetzung geraten — ein
  ausgedachter String sieht aus wie ein gemessener.

- **`1990-2029` stimmte nicht mehr.** Dieselbe Neuveröffentlichung liess die
  Voranschlags- und Finanzplanjahre des Bundes weg; die Datei endet bei 2025
  (6110 statt 6579 Zeilen, 414 statt 516 KB). Die Registry-Notiz und die
  Tool-Beschreibung von `fiscal_headline` nannten den alten Horizont als
  Zusicherung und hätten eine Agentin nach Planjahren suchen lassen, die es
  nicht gibt. Beide nennen jetzt kein festes Endjahr mehr — der Horizont
  gehört der Quelle.

- **Der Kommentar über dem Wortschatz behauptete zwei Dinge, die nicht mehr
  stimmten.** Er sagte, die Planjahre des Bundes hiessen «Budget/financial
  plans» und «Forecasts» sei dem Gesamtstaat vorbehalten. Gemessen am
  29.8.2026 hat der Bund gar keine Planjahre mehr, und `Prognosen` steht bei
  `staat` (31 Zeilen), `gdn` (28) und `bund_ktn_gdn` (16). Wer den Kopf des
  Blocks liest, bekam die falsche Auskunft vor der richtigen. Aussagen darüber,
  **wer** Prognosen bekommt, tragen jetzt ein Datum; Regel ist allein die
  Abbildung darunter.

### Hinzugefügt

- **`test_live_source_vocabulary_is_fully_mapped` benennt die nächste Drift.**
  Der Test fährt jede verschiedene `source`-Marke des Dumps durch
  `is_projection` und fällt mit den unbekannten im Klartext:
  «`source` labels the client cannot classify: ['Prognosen', 'Rechnung',
  'Vorhandene Daten']». Gegen die Funktion selbst gefragt, nicht gegen eine
  Kopie der beiden Mengen — eine Kopie stimmt sich selbst zu, während die
  Produktion unabgebildet läuft.

  Das ist die Meldung, die am 27.8. gefehlt hat. `None` von `is_projection`
  liest sich als «diese Zeile sagt nichts» und unterschlägt damit genau den
  Unterschied, auf den es ankommt: ob die Quelle geschwiegen oder ihre
  Taxonomie verschoben hat.

- **`tests/test_source_vocabulary.py`** hält beide Wortschätze im pytest-Gate
  fest, einzeln je Marke und einmal durch `headline_impl`. Jede Marke ist
  nachweislich tragend: Wird sie entfernt, fallen genau die Tests, die sie
  nennen.

### Geändert

- **Die beiden roten Live-Tests prüfen jetzt die Zusage, nicht die Vokabel.**
  `test_live_staat_has_forecasts_label` hing an `p.kind == "Forecasts"` und
  fragt als `test_live_projections_survive_into_the_tool` jetzt
  `is_projection`, denn die Zusage an den Aufrufer ist die Kennzeichnung, nicht
  der Rohtext der EFV. Auch der Haushalt steht nicht mehr im Test: Er wird aus
  dem Dump abgeleitet. `staat`/`fs`/`einnahmen` trug am 29.8.2026 genau **eine**
  Prognosezeile von 75 im ganzen File — die nächste Ausgabe, die den
  Gesamtstaat 2025 abschliesst, hätte den Test wieder rot gemacht, und zwar
  wegen einer Änderung an dem, was die EFV veröffentlicht. Genau der Fehler,
  wegen dem der Bund-Test umgebaut wurde.

  `test_live_headline_saldo_has_projection` verlangte vom Bund Planjahre bis
  2028 — ebenfalls eine Aussage darüber, was die EFV veröffentlicht, nicht
  darüber, was dieser Server tut. Als
  `test_live_headline_saldo_is_classified_and_current` prüft er stattdessen,
  dass jeder Punkt klassifiziert ist, und hält mit `Jahr - 2` eine
  Alterungsschwelle statt eines Horizonts: `Jahr - 1` fiele jeden Januar,
  bevor die Rechnung des Vorjahres erscheint.

- **`timeout-minutes` in `live.yml` von 15 auf 20.** Der siebte Live-Test
  sprengt sonst `test_live_budget_fits_the_job_timeout`: 75 s mal sieben Tests
  mal Sicherheitsfaktor 2 sind 1050 s gegen 900 s. Das Gate hat genau dort
  gegriffen, wofür es gebaut wurde — im PR, nicht nachts.

### Behoben

- **`DELETE` fehlte in `allow_methods`.** Der Preflight wies die Methode mit 400
  ab, ein Browser-Client konnte also Sessions öffnen, aber nie schliessen. Das
  SDK bedient sie sehr wohl — `_handle_delete_request` in
  `mcp.server.streamable_http`, und dessen eigene 405-Antwort wirbt mit
  `Allow: GET, POST, DELETE`. Die Freigabeliste war schmaler als der Server.

  Gemessen vor der Behebung: `Preflight DELETE -> 400` auf beiden Transporten,
  bei `Access-Control-Allow-Methods: GET, POST, OPTIONS`. Danach `200` und
  `GET, POST, DELETE, OPTIONS`.

### Hinzugefügt

- **`tests/test_protocol_version.py` schliesst drei Lücken am Protokoll-Pin.**
  Das Gate selbst gab es schon (`test_negotiated_protocol_version_matches_pin`
  in `test_hardening.py`, ein echter Handshake gegen den Pin) — es bleibt, wo
  es ist. Daneben war offen:

  - `MCP_PROTOCOL_VERSION` war eine freie Zeichenkette. Sie ist jetzt gegen
    `LATEST_PROTOCOL_VERSION` gehalten, also fällt auch ein Tippfehler auf, den
    das SDK gar nicht kennt.
  - Beide READMEs nennen die Revision im Fliesstext, nichts hielt sie gegen den
    Pin. Der Test prüft beide Sprachen einzeln.
  - Nichts sagte, warum hier **eine** Revision steht statt eines Paares.
    `test_das_sdk_kennt_hier_nur_eine_aera` ist an das SDK gebunden statt an
    einen Kommentar: fastmcp 3.x pinnt `mcp` 1.x, wo `mcp.types.version` fehlt;
    zieht ein Upgrade die Zwei-Ären-Konstanten herein, fällt der Test.

### Behoben

- **`allow_headers` stand auf `["*"]`.** Starlette schaltet damit auf
  `allow_all_headers` und spiegelt im Preflight zurück, was der Browser
  ankündigt — jeder gelistete Origin durfte jeden beliebigen Header senden. Die
  Liste nennt jetzt `Content-Type`, `Mcp-Session-Id` und `Last-Event-ID`.
  Letzterer setzt einen abgerissenen SSE-Strom fort und war unter der Wildcard
  nie geprüft: eine Wildcard kann nicht falsch werden und sagt deshalb nichts
  darüber, ob die Header, die das Protokoll braucht, freigegeben sind.

  Die Routing-Header der Spec `2026-07-28` stehen bewusst **nicht** darauf.
  fastmcp 3.x pinnt `mcp` 1.x, wo es `mcp.shared.inbound` nicht gibt und
  niemand sie liest. `test_die_routing_header_gehoeren_hierher_sobald_das_sdk_sie_liest`
  ist an das SDK gebunden statt an eine Notiz und fällt, sobald ein Upgrade das
  Modul hereinzieht.

### Geändert

- **`build_http_app` aus `main` herausgezogen.** Solange der App-Aufbau neben
  `uvicorn.run` stand, liess sich die CORS-Freigabeliste nur lesen, nicht
  ausprobieren — und eine Liste, die richtig aussieht, kann trotzdem nie an der
  Middleware ankommen. `main` ruft die Funktion auf; am Verhalten ändert sich
  nichts.

### Added

- **Die Pruefsummen im Fixture-Nachweis waren Zierde.** `PROVENANCE.md` fuehrt
  je Datei einen SHA-256 — um genau einen Fall zu fangen: eine Aufzeichnung,
  die nach dem Lauf von Hand nachgebessert wurde. Eine korrigierte Antwort ist
  wieder eine erfundene, und von aussen ist ihr das nicht anzusehen.
  Nachgerechnet hat sie kein Test. `test_die_pruefsumme_im_nachweis_stimmt`
  tut es jetzt, ueber die Bytes auf der Platte statt ueber den Loader — genau
  die hat der Recorder gehasht.

- **Aufgezeichnete Fixtures, eine je externem Datensatz, mit Nachweis.**
  `tests/fixtures/` haelt jetzt echte Ausschnitte aller drei Datensaetze —
  `headline`, `budget`, `institutions` —, aufgezeichnet von
  `scripts/record_fixtures.py`. Herkunft, Datum, Auswahlregel und SHA-256
  stehen je Datei in `tests/fixtures/PROVENANCE.md`, wie im uebrigen Portfolio.

  Die Quelldateien sind 0.5 bis 5 MB gross, aufgezeichnet ist je die
  **unveraenderte Kopfzeile** und eine Auswahl Zeilen; keine Spalte entfernt.
  Die Zeilen sind gewaehlt, nicht genommen: `budget.csv` beginnt in der Quelle
  ausschliesslich mit Hierarchie-Ebene 1, obwohl der Client bis Ebene 8 parst,
  und `headline.csv` enthaelt in den ersten tausend Zeilen keine der
  `NA`-Zeilen, auf die `_NULLISH` reagiert. Zusaetzlich haelt die Auswahl
  Thema und Jahr zusammen, sonst waere der Ausschnitt nicht abfragbar.

- **Die handgeschriebenen Szenario-CSVs sind jetzt an die Quelle gebunden.**
  `test_die_handgeschriebenen_koepfe_stimmen_mit_der_quelle` vergleicht ihre
  Kopfzeilen mit den aufgezeichneten. Sie bleiben — sie kodieren bewusste
  Szenarien —, konnten ihre eigene Satzform aber nicht belegen: sie brachten
  ihre Kopfzeile selbst mit und stimmten damit sich selbst zu. Geprueft ergab
  der Vergleich, dass alle drei Koepfe heute exakt stimmen; neu ist, dass eine
  Umbenennung in der Quelle auffaellt statt still weiterzulaufen.

  Gegenprobe: Aufnahmedatum entfernt -> Datums-Check faellt; Spalte umbenannt ->
  Bruecken-Test und Ebenen-Test fallen; nur Ebene 1 behalten (naive Kopfauswahl)
  -> Ebenen-Test faellt; `NA`-Zeile entfernt -> headline-Test faellt.

### Behoben

- **Die Fake-Uhr der Retry-Tests hielt die Event-Loop an — und damit genau die
  Frist ausser Kraft, die sie prüfen sollte.** `fake_clock` setzte
  `monkeypatch.setattr("swiss_efv_mcp.client.time.monotonic", …)`. Das liest
  sich lokal und ist es nicht: `client.time` **ist** das stdlib-Modul, und
  `asyncio` liest `time.monotonic` aus demselben Objekt. Eine eingefrorene Uhr
  hält damit `loop.time()` an, und jede unter ihr geplante Frist wartet auf
  einen Moment, der nie kommt.

  Betroffen ist der Budget-Deckel selbst: `_fetch_with_retry` begrenzt jeden
  Versuch mit `async with asyncio.timeout(remaining)` — der Wanduhr-Frist, die
  das Budget verspricht. In allen vier `fake_clock`-Tests konnte diese Frist
  **nie** auslösen. Gemeldet hat das nichts; die Tests waren grün. Sichtbar
  wurde es erst, weil dieselbe Fixture zusätzlich `asyncio.sleep` prozessweit
  ersetzte und die beiden Patches einander verdeckten: nimmt man den Schlaf-
  Patch weg und lässt den Uhr-Patch stehen, hängt die Suite, statt zu fallen.

  Beide Nahtstellen tragen jetzt einen Namen dieses Moduls — `client._sleep`
  und `client._monotonic` —, und die Tests übernehmen diese statt der
  stdlib-Funktionen. Das ist die Portfolio-Konvention aus `CLAUDE.md` Teil 1;
  dieses Repo war neben `swiss-holidays-mcp` das letzte ohne sie.

  Drei neue Zusicherungen: `test_die_fake_uhr_laesst_die_frist_der_event_loop_laufen`
  (die zentrale — sie war vorher nicht formulierbar und fällt gegen den alten
  Stand), `test_das_uebernehmen_der_naht_laesst_den_prozess_in_ruhe` und
  `test_die_beiden_nahtstellen_gehoeren_dem_modul`, das die Schleife im
  Quelltext liest, damit ein Rückfall auffällt statt still zu bestehen.

- **`_fetch_with_retry` warf zweimal ein nacktes `RuntimeError` — jetzt einen
  eigenen Typ.** Dieses Modul ist die Referenz, gegen die die Retry-Vorlage des
  Portfolios am 7.8.2026 repariert wurde
  ([mcp-data-source-probe-skill#24](https://github.com/malkreide/mcp-data-source-probe-skill/pull/24)).
  Das Manifest, das die Vorlage beschreibt, deklariert `no_bare_runtime_error` —
  «fails with a typed upstream error a caller can branch on» — als Eigenschaft,
  die jede Übernahme halten muss. Gegen die siebzehn Server gelesen war dieses
  Modul **das einzige**, das sie verletzte: Es wirft `RuntimeError`, während es
  als Vorbild für alle anderen zitiert wird.

  Der Preis ist konkret: Ein nacktes `RuntimeError` lässt sich nicht von einem
  Bug in diesem Server unterscheiden. Wer bei Ausfall der Quelle einen alten
  Cache ausliefern will, kann «die Quelle ist unten» nicht von «wir haben einen
  Defekt» trennen — und fängt am Ende beides oder keines.

  Neu:
  - `UpstreamError(RuntimeError)` — Quelle nicht erreichbar, Retries verbraucht.
  - `UpstreamNotAttemptedError(UpstreamError)` — das Budget war weg, bevor ein
    einziger Request rausging. Eigener Typ, weil die Abhilfe eine andere ist:
    Der Quelle wurde nichts abverlangt, das sagt also etwas über unser Budget,
    nicht über ihren Zustand.

  **Additiv, kein Bruch:** Beide erben von `RuntimeError`, jedes bestehende
  `except RuntimeError` läuft unverändert weiter. Die Meldungen selbst sind
  unangetastet — sie nannten Typ, Host und ausgegangenes Limit schon vorher
  richtig; es fehlte nur der Typ der Exception.

  Zwei Tests sichern das zu: dass die Erschöpfung `UpstreamError` und **nicht**
  bloss `RuntimeError` ist, und dass der Fall ohne einen einzigen Versuch seinen
  eigenen Typ hat.

- **Der 20-Sekunden-Deckel war keine Grenze.** Gedeckelt wurde *vor* dem
  Jittern, also wurde ein auf `_MAX_DELAY_SECONDS` gedeckelter Wert
  anschliessend mit bis zu 1.5 multipliziert: exponentielle Wartezeiten bis
  30 s, `Retry-After`-Wartezeiten bis 25 s. Die Konstante behauptete eine
  Schranke, die sie nicht einhielt. Neu wird nach dem Jittern gedeckelt.

- **Das Gesamtbudget war nicht garantiert.** `httpx` wendet sein Timeout pro
  Operation an (connect/read/write/pool), und das Read-Timeout beginnt mit jedem
  Chunk von vorn — eine langsam troepfelnde Antwort konnte das Budget
  ueberdauern, ohne dass ein einzelner Read ablief. Der Kommentar an
  `timeout` benannte genau diese Eigenschaft, und darunter wurde das
  Gesamtbudget trotzdem versprochen. Neu liegt eine `asyncio.timeout`-Deadline
  um den Request; das httpx-Timeout bleibt als feinere Grenze pro Operation
  daneben.

  Beide Befunde stammen aus einem Codex-Review an `parlament-mcp#35`, wo
  dasselbe Muster nach der Uebernahme geprueft wurde. Der Test dazu laeuft
  bewusst **ohne** die Fake-Uhr der uebrigen Budget-Tests: Die Zusicherung
  haengt an echter Zeit, und eine Uhr, die nur beim Schlafen vorrueckt, kann sie
  nicht widerlegen — genau dieser blinde Fleck liess den Fehler durch.


### Hinzugefuegt

- **`Retry-After` wird gelesen und schlaegt die eigene Backoff-Kurve** (ARCH-014).
  Bei 429 und 503 sagt die Quelle im Header, wann sie wieder mag — als
  Sekundenzahl oder als HTTP-Datum; beide Formen kommen vor, beide werden
  gelesen (RFC 9110 §10.2.3). Wer stattdessen seine eigene Kurve faehrt,
  ignoriert eine ausdrueckliche Angabe, und ein Anbieter, der zweimal ignoriert
  wird, sperrt. Ein unbrauchbarer Header fuehrt zu `None` und damit zurueck auf
  die Kurve — eine kaputte Kopfzeile darf auf dem Fehlerpfad nicht zum Absturz
  werden.

- **Backoff ist gestreut (Jitter).** `2**attempt` war deterministisch: Faellt die
  Quelle aus, waehrend mehrere Clients sie abfragen, laufen deren Retries im
  Gleichtakt, und die Last kommt als Welle zurueck — genau wenn die Quelle sich
  erholt. Der Retry-Sturm verlaengert den Ausfall, den er ueberbruecken soll.
  Exponentielle Wartezeiten landen jetzt in `[0.5x, 1.5x]`.

  Auf einem `Retry-After` ist die Streuung **einseitig** (`[1.0x, 1.25x]`): Die
  Quelle hat gesagt, wann wir wiederkommen sollen — spaeter ist hoeflich,
  frueher waere die Missachtung derselben Angabe, die man gerade liest.

- **Deckel von 20 s auf jede einzelne Wartezeit.** Betrifft beides: eine
  Exponentialleiter, die sonst unbegrenzt waechst, und ein `Retry-After`, das
  die Quelle senden darf, das man aber nicht absitzen muss. `backoff_base=0`
  bleibt instant — die Testsuite wartet weiterhin nicht.

- **Gesamtbudget von 25 s ueber den ganzen Aufruf** (ARCH-014). Eine Anzahl
  Versuche ist keine Grenze: Vier Versuche a 60 s Timeout plus Backoff sind
  ueber vier Minuten, und die Zahl `4` sagt das nirgends. Entscheidender ist,
  dass die massgebliche Grenze gar nicht uns gehoert — der Aufrufer hat sein
  eigenes Timeout, und jenseits davon hoert niemand mehr zu: Die Arbeit laeuft
  weiter, die Last landet bei der Quelle, das Ergebnis geht ins Leere.

  Der Anker ist gemessen, nicht geschaetzt: Das Python-MCP-SDK setzt
  `MCP_DEFAULT_TIMEOUT = 30.0` fuer allgemeine Operationen
  (`mcp/shared/_httpx_utils.py`). 25 s lassen Luft fuer MCP-Framing,
  CSV-Parsing und die Tool-Schicht oberhalb des Fetch. Ein Test haelt die
  Beziehung fest und schlaegt an, wenn das SDK seinen Default senkt.

  Geprueft wird vor jedem Versuch: Eine Wartezeit, die das Budget ueberdauern
  wuerde, wird nicht mehr angetreten, und das Timeout eines einzelnen Versuchs
  ist auf die verbleibende Zeit geklemmt. Die Meldung nennt neu, **welche**
  Grenze gegriffen hat — «all 4 attempts used» und «25s budget spent» verlangen
  verschiedene Antworten.

  Der Standardwert von `timeout` faellt von 60 s auf 25 s: Ein Wert oberhalb des
  Budgets haette nur noch behauptet, was er nicht mehr gewaehrt.

  Die Abwaegung ist bewusst: Ein langsamer erster Versuch kann jetzt das Budget
  aufbrauchen und laesst dann keinen Retry mehr zu. Genau das ist die
  beabsichtigte Antwort — ein Retry, der nach dem Aufgeben des Aufrufers fertig
  wird, bringt niemandem etwas und kostet die Quelle eine Anfrage.

### Behoben

- **Fehlermeldung bei unerreichbarem Upstream nannte den Fehler nicht.**
  `RuntimeError: Upstream unreachable after retries: ` endete im Nichts, weil
  `httpx.ConnectTimeout` / `ReadTimeout` / `ConnectError` ein leeres `str()`
  tragen. Die Meldung nennt jetzt immer den Exception-Typ und den Host, also
  z. B. `Upstream unreachable after 4 attempts: ConnectTimeout: no further
  detail (host=www.data.finance.admin.ch)`, und verkettet die Ursache via
  `raise ... from`. Damit ist eine voruebergehende Netzstoerung auf einen Blick
  von einer kaputten URL zu unterscheiden. Der Wortlaut bleibt intern — nach
  aussen maskiert `mask_error_details` weiterhin auf den Typnamen (OBS-002).

### Geaendert

- **Die Live-Suite teilt sich einen `EFVClient`.** Bisher legte jeder Test eine
  eigene Instanz an, womit der Cache nutzlos war und derselbe Dump mehrfach
  geladen wurde. Beim Ausfall am 2026-08-01 lief deshalb viermal dieselbe
  aussichtslose Retry-Leiter: vier Tests, 17 Minuten. Jetzt wird jeder Datensatz
  einmal pro Lauf geholt (Suite-Laufzeit ~10 s), der geteilte Connection-Pool
  wird beim Teardown geschlossen statt pro Test zu lecken, und die Suite nutzt
  engere Timeouts (30 s statt 60 s, Backoff 1.0 statt 2.0): ein toter Upstream
  meldet sich in etwa einer Minute. Der `live`-Workflow bekommt zusaetzlich
  `timeout-minutes: 10` als Backstop.

## [0.3.2] - 2026-08-02

### Fixed

- **`structlog` carried no upper bound, and the index already serves a major past
  the floor.** The declared range was `structlog>=24.1`; PyPI has been serving
  `26.1.0`. The artefact does not change — the resolver's answer to the next
  fresh install does, and that is exactly how `swiss-energy-mcp` 0.3.3 became
  uninstallable when `mcp` 2.0.0 removed the module it imported.

  Now `structlog>=24.1,<27`. The bound is measured rather than guessed: this package
  installs and imports against `structlog 26.1.0` today, so the cap admits what
  demonstrably works and stops only the next, unknown major.

A dependency range only reaches users through a new release, hence the
version bump. No code changed.

## [0.3.1] - 2026-07-31

### Geaendert

- **Der Server gibt sich nicht mehr als Chrome aus.** Bis 0.3.0 sendete er
  `Mozilla/5.0 (X11; Linux x86_64) ... Chrome/124.0 Safari/537.36`, mit dem
  Vermerk, die Endpunkte wiesen alles andere mit 403 ab (gemessen 2026-07-24).

  Am 2026-07-31 nachgemessen: alle drei Datensatz-URLs auf beiden Hosts, je
  vier User-Agents — Chrome, die ehrliche Kennung, `curl/8.5.0` und ganz ohne
  UA-Header. Jede Anfrage antwortete 200/206; die ehrliche Kennung anschliessend
  dreimal ueber alle drei Datensaetze wiederholt, neun von neun erfolgreich.
  Die Einschraenkung besteht nicht mehr.

  Neu sendet der Server `swiss-efv-mcp/<version> (+github.com/...)` aus den
  Paket-Metadaten. Eine gefaelschte Kennung kostet den Betreiber die
  Moeglichkeit, uns in seinen Logs zu erkennen und uns bei Fehlverhalten zu
  erreichen — das ist nur fuer eine Sperre zu zahlen, die es tatsaechlich gibt.
  Sollte die EFV wieder filtern, gehoert zum Zurueckdrehen die Aktualisierung
  des Vermerks: eine veraltete Begruendung ist der Grund, warum diese hier so
  lange unhinterfragt blieb.

## [0.3.0] - 2026-07-25

Medium-findings audit backlog worked through — 0 failing checks; the three
remaining findings are accepted-risk ADR-documented deferrals (SCALE-002,
SCALE-003, SEC-005). See the audit runs under `audits/`.

### Added
- **ARCH-012:** the MCP protocol baseline (`2025-11-25`) is pinned as
  `MCP_PROTOCOL_VERSION` in `server.py`, with a regression test that fails CI if
  a SDK bump changes the negotiated version.
- **SEC-022:** `dump_status` renamed to `fiscal_status` so every tool shares the
  `fiscal_` server-identity namespace; `dump_status` is kept as a documented
  deprecated alias (removed in a future minor). Tool-hash pinning is documented
  as a gateway responsibility in `SECURITY.md`.
- **SCALE-003:** ADR 0002 gains a concrete `Mcp-Session-Id` sticky-session
  example (nginx / Ingress / Traefik) for the multi-replica case.
- **SEC-005:** `docs/network-egress.md` prescribes the network-layer egress
  mitigation (default-deny NetworkPolicy / egress-proxy allow-list) that
  supersedes application-level DNS pinning.
- **SDK-002:** tools now return typed Pydantic models, so FastMCP exposes an
  output schema and structured content for every tool.
- **SDK-003:** `Context` injection — tools emit debug logs and `fiscal_list_dimensions`
  reports progress while loading the dumps.
- **ARCH-002:** tool descriptions carry explicit use-case context.
- **ARCH-003:** empty results return a guidance `note` (pointing at
  `fiscal_list_dimensions` or a different level) instead of a silent empty.
- **OBS-006:** optional OpenTelemetry tracing via the `otel` extra, gated by
  `EFV_MCP_OTEL_ENABLED` (off by default; `src/swiss_efv_mcp/_otel.py`).
- **SCALE-006 / SEC-007:** `compose.yaml` with CPU/memory limits, read-only root
  filesystem, dropped capabilities and `no-new-privileges`.
- **OPS-001:** per-tool live tests (`fiscal_by_institution`, `dump_status`) and a
  scheduled/manual live-test workflow (`.github/workflows/live.yml`).
- **OPS-003:** `docs/roadmap.md` documenting the phase architecture and the
  audit backlog.

### Security
- **SEC-004:** the egress guard now rejects IP-literal hosts and re-asserts the
  allow-list on the final URL after redirects.

## [0.2.0] - 2026-07-25

First public release. Portfolio alignment plus the security/observability
hardening from the MCP best-practice audit (production-ready; audit artifacts
under `audits/`).

### Security
- **SEC-021 — egress allow-list:** an immutable `ALLOWED_HOSTS` frozenset +
  `assert_host_allowed()` (HTTPS-only, two fixed EFV hosts) is enforced before
  every request in `client.py`; documented in `docs/network-egress.md`.
- **OBS-002 — error-detail masking:** raw upstream/internal exception text is no
  longer surfaced to the model; tool results carry a generic message and
  `mask_error_details=True`, with full detail logged to stderr.
- **SEC-018 — input bounds:** tool arguments carry explicit Pydantic constraints
  (year `1900–2100`, `level 1–8`, string `max_length`).
- **SDK-004 — default-deny CORS:** the SSE/HTTP transport sets explicit
  `allowed_origins` (via `EFV_MCP_CORS_ORIGINS`) and exposes only `Mcp-Session-Id`.
- **SEC-005 / SCALE-002 / SCALE-003 — accepted-risk ADRs:** DNS pinning
  (`docs/adr/0001`) and stateful load balancing (`docs/adr/0002`) are deliberately
  deferred with documented re-evaluation triggers.

### Added
- **MCP best-practice audit** against the portfolio catalogue (68 checks, 44
  applicable) under `audits/`: a baseline run and a post-remediation re-audit —
  **production-ready** (0 blocking findings; 17 → 26 pass). Reproducible from the
  stored `verification-results.json` / `summary.json`.
- Tool annotations `readOnlyHint: true` / `destructiveHint: false` on all five
  tools (ARCH-009).
- Structured logging via `structlog` (JSON to stderr) in `logging_config.py`
  (OBS-003 / OBS-004).
- Typed configuration via `pydantic-settings` (`settings.py`); new env vars
  `EFV_MCP_LOG_LEVEL`, `EFV_MCP_CORS_ORIGINS`, plus `EFV_MCP_`-prefixed aliases.
- Shared, lifespan-managed httpx client (one connection pool reused across dumps,
  closed on shutdown) (SDK-001).
- Hardened `Dockerfile`: named runtime stage + `HEALTHCHECK` (SCALE-004).
- Expanded test suite (`tests/test_hardening.py`): egress allow-list, error
  masking, tool annotations, settings, shared-client reuse, and the
  execution-error / protocol-error paths.

### Changed
- `__main__.py` rebuilt for FastMCP 3.x: network transports are served via
  `mcp.http_app(...)` + uvicorn with CORS, fixing the former `mcp.settings` path.
- Repository documentation and structure aligned with the Swiss Public Data MCP
  Portfolio convention.
- `SECURITY.md` / `SECURITY.de.md`: security posture, accepted-risk decisions, and
  the vulnerability-reporting process; linked from both READMEs.
- `CONTRIBUTING.md` / `CONTRIBUTING.de.md` and `PUBLISHING.md` (step-by-step PyPI
  release via Trusted Publishing).
- GitHub Actions CI workflow (`.github/workflows/ci.yml`): ruff + offline pytest
  on Python 3.11–3.13, with a CI status badge in both READMEs.
- `Publish to PyPI` workflow (`.github/workflows/publish.yml`) using PyPI Trusted
  Publishing (OIDC) on GitHub Release, plus MCP Registry publishing; `server.json`
  registry manifest.
- Dependabot config (`.github/dependabot.yml`): monthly `pip` and
  `github-actions` updates.
- Hardened non-root `Dockerfile` (SSE) and `.dockerignore`; `.gitignore`.
- README sections aligned with the portfolio: portfolio banner, linked badges,
  `Available Tools`, `Safety & Limits`, `Project Phase`, `MCP Protocol Version`,
  `Security` and `Contributing`, plus the `mcp-name` registry footer.

### Changed
- Distribution metadata in `pyproject.toml`: `LICENSE`-referenced license,
  per-version Python classifiers (3.11–3.13), author `Hayal Oezkan`, and
  `Repository` / `Issues` / `Changelog` / `Portfolio` project URLs.

### Security
- SSE transport now binds to `127.0.0.1` (loopback) by default instead of
  `0.0.0.0`. Binding to `0.0.0.0` is an explicit opt-in for containers (the
  provided `Dockerfile` sets it). README / SECURITY updated.

## [0.1.0] - 2026-07-24

### Added
- Initial release: MCP server for Swiss federal finances (EFV), Architecture C (Dump-first).
- Tools: `fiscal_headline`, `fiscal_budget_breakdown`, `fiscal_by_institution`,
  `fiscal_list_dimensions`, `dump_status`.
- Dual transport (stdio / SSE), retry with exponential backoff, 24 h TTL cache,
  Pydantic v2 envelopes with `source` + `provenance`.
- respx mock tests (Happy / Retry-on-503 / Timeout / Graceful degradation) plus
  `@pytest.mark.live` tests against the real endpoints.

### Known findings (from live probe 2026-07-24)
- **403 without UA**: `data.finance.admin.ch` and `efv.admin.ch` reject the default
  httpx/curl User-Agent; a browser UA is injected in `client.py`.
- **Landing-page trap**: opendata.swiss lists two datasets as "CSV" but the URL
  serves HTML; real files resolved to DAM paths (`/dam/de/sd-web/{id}/{name}_de.csv`)
  whose opaque id may rotate on re-upload.
- **NA-as-string**: `hh` / `model` / `source` use the literal "NA" for missing;
  centralised `clean()` maps null-ish tokens to `None`.
- **Projection is not one label**: the Bund labels future years "Budget/financial
  plans"; the aggregate state (`staat`) uses "Forecasts". `is_projection` abstracts
  over both so agents need not know the taxonomy.
- **Accounting-model seam 2022/2023**: budget topics split into "bis 2022" and
  "ab 2023"; a `note` flags affected breakdowns.
- **Detail cubes deferred**: `standardauswertung.csv` (157 MB) and `fir_art_funk.csv`
  (1.23 GB) are out of scope for v0.1.0 (Phase 2: pre-process to SQLite/Parquet).
