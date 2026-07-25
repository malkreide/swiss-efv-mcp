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

| Bereich | Kontrolle |
|---|---|
| Egress | Die Datensatz-URLs sind fest kodierte Konstanten auf zwei EFV-Hosts; kein Nutzer-Input gelangt in eine Anfrage, daher keine SSRF-Angriffsfläche |
| TLS | httpx-Zertifikatsprüfung standardmässig aktiv und im Code nie deaktiviert |
| Auth / Secrets | Unauthentifiziertes öffentliches OGD — es werden keine API-Keys, Tokens oder Secrets gespeichert oder weitergereicht |
| Input | Pydantic-v2-Validierung an allen Tool-Grenzen; Tool-Argumente filtern nur gecachte Zeilen, sie bauen nie eine URL |
| Tools | Read-only by design (nur HTTP GET); keine dynamische oder Remote-Tool-Registrierung |
| Fehler | Upstream-Fehler werden über `dump_status` offengelegt, nie stillschweigend verschluckt oder als leeres, vollständig aussehendes Resultat zurückgegeben |
| Stdout | Reserviert für den JSON-RPC-Stream; der Server gibt kein Fremd-Logging auf stdout aus |
| Binding | `stdio` als Default (keine Netzwerk-Angriffsfläche). SSE bindet an `HOST`, Default `127.0.0.1` (Loopback); `0.0.0.0` ist ein expliziter Opt-in für Container |

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
