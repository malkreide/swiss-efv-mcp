# Sicherheitsrichtlinie & Posture

[🇬🇧 English Version](SECURITY.md)

`swiss-efv-mcp` ist ein **Read-only-**, **No-Auth-**, **Public-Open-Data-**MCP-Server.
Dieses Dokument fasst die Sicherheits-Posture zusammen und beschreibt, wie
Schwachstellen gemeldet werden.

## Schwachstelle melden

Bitte ein privates Security Advisory im GitHub-Repository eröffnen oder die in
`README.md` genannte Maintainerin kontaktieren. Für ausnutzbare Schwachstellen
keine öffentlichen Issues erstellen.

## Posture-Zusammenfassung

Alle fünf Tools stellen ausschliesslich Lese-Anfragen an kuratierte öffentliche
EFV-Dump-Files auf zwei festen Hosts (`data.finance.admin.ch`, `efv.admin.ch`);
es gibt keine Schreib-, Sende- oder Dateisystem-Fähigkeiten, und es werden keine
Personendaten verarbeitet.

Diese Posture wurde gegen den Portfolio-MCP-Best-Practice-Katalog geprüft
(44 anwendbare Checks) — siehe [`audits/`](audits/). Die untenstehende Härtung
schliesst den Audit-Backlog; der Lauf ist aus der gespeicherten
`verification-results.json` reproduzierbar.

| Bereich | Kontrolle |
|---|---|
| Egress | Code-Layer-Allow-List: ein modulweites `frozenset` `ALLOWED_HOSTS` + `assert_host_allowed()` vor **jeder** Anfrage weist Nicht-HTTPS und jeden Host ausserhalb der Liste ab. URLs sind fest kodiert; kein Nutzer-Input baut eine URL. Siehe [`docs/network-egress.md`](docs/network-egress.md). (SEC-021) |
| TLS | httpx-Zertifikatsprüfung standardmässig aktiv und im Code nie deaktiviert |
| Auth / Secrets | Unauthentifiziertes öffentliches OGD — keine API-Keys, Tokens oder Secrets gespeichert oder weitergereicht |
| Input | Pydantic-v2-Validierung an allen Tool-Grenzen mit expliziten Bounds (Jahr `1900–2100`, Hierarchie `level 1–8`, String `max_length`); Tool-Argumente filtern nur gecachte Zeilen, sie bauen nie eine URL (SEC-018) |
| Tools | Read-only: jedes Tool ist mit `readOnlyHint: true`, `destructiveHint: false` annotiert; keine dynamische oder Remote-Tool-Registrierung (ARCH-009) |
| Fehler | `mask_error_details=True` plus client-seitige Maskierung: Execution-Fehler erscheinen als `isError`-Tool-Result mit generischer Meldung; rohes Upstream-/Interndetail geht nur ins structlog-stderr-Log, nie ans Modell (OBS-002) |
| Logging | Strukturierte JSON-Logs auf **stderr** via structlog; stdout bleibt dem JSON-RPC-Stream vorbehalten (OBS-003 / OBS-004) |
| Binding | `stdio` als Default (keine Netzwerk-Angriffsfläche). SSE bindet an `HOST`, Default `127.0.0.1` (Loopback); `0.0.0.0` ist ein expliziter Opt-in für Container (SEC-016) |
| CORS | SSE setzt Default-Deny-CORS — Browser-Origins müssen via `EFV_MCP_CORS_ORIGINS` explizit gelistet werden; nur `Mcp-Session-Id` wird exponiert (SDK-004) |
| Container | Gehärtetes non-root [`Dockerfile`](Dockerfile) (uid 10001) mit `HEALTHCHECK` (SEC-007 / SCALE-004) |

## Akzeptierte Risiken (ADRs)

Zwei Kontrollen sind bewusst zurückgestellt und als Accepted-Risk-ADRs
dokumentiert — geringes Risiko für einen Single-Instance-, No-Auth-,
Read-only-Server mit zwei festen Hosts:

- **DNS-Pinning** — [ADR 0001](docs/adr/0001-dns-pinning.md) (SEC-005): kein
  nutzergesteuertes Ziel + die Egress-Allow-List neutralisieren die
  DNS-Rebinding-Vorbedingung.
- **Stateful Load Balancing** — [ADR 0002](docs/adr/0002-scaling-and-deployment.md)
  (SCALE-002 / SCALE-003): als Single-Instance betrieben; Sticky-Sessions /
  Shared-Session-Store mit expliziten Re-Evaluations-Triggern zurückgestellt.

## Akzeptierte Risiken (Kontrollen auf Portfolio-Ebene)

Die folgenden Punkte werden auf der MCP-Gateway-/Host-Ebene behandelt, nicht in
diesem einzelnen Server. Das Restrisiko ist hier gering, weil der Server
read-only und unauthentifiziert ist und nur zwei vertrauenswürdige
Open-Data-Hosts erreicht.

- **Session-Krypto-Bindung** — nicht anwendbar: Es gibt keine Nutzeridentität zum
  Binden, da der Server öffentliche Daten ohne Authentifizierung bereitstellt.
- **Server-übergreifende Tool-Poisoning-Erkennung** — Aufgabe des Gateways/Hosts.
  Die Tool-Definitionen dieses Servers sind versioniert, in-repo verfasst und per
  PR reviewt; es gibt keine dynamische oder Remote-Tool-Registrierung.
- **Netzwerk-Binding für gehostete Deployments** — der SSE-Transport bindet
  standardmässig an `127.0.0.1` (Loopback). Ein Binding an `0.0.0.0` ist ein
  expliziter Opt-in für Container-Deployments; dann mit einem Reverse-Proxy /
  Gateway betreiben, das TLS und Zugriffskontrolle erzwingt.
- **Browser-User-Agent** — die EFV-Endpoints weisen den Default-httpx/curl-UA mit
  HTTP 403 ab, daher wird ein statischer Browser-UA injiziert. Er trägt keine
  Nutzerdaten und ist kein Tracking- oder Authentifizierungs-Token.

## Re-Evaluations-Trigger

Diese Akzeptanzen sind neu zu bewerten, sobald der Server je:

- **Schreib**-Fähigkeit erhält oder **PII** verarbeitet, oder
- ein **Authentifizierungs**-Modell erhält (dann gebundene, TTL-behaftete,
  serverseitig invalidierbare Session-IDs implementieren und vor dem Merge
  re-auditieren), oder
- Tools **dynamisch** / aus Remote-Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann Tool-Allow-Listing
  und Tool-Poisoning-Erkennung des Gateways aktivieren).
