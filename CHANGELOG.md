# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
