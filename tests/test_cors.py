"""SDK-004: Die CORS-Freigabeliste nennt jetzt Header statt einer Wildcard.

`allow_headers` stand auf `["*"]`. Starlette schaltet damit auf
`allow_all_headers` und spiegelt im Preflight zurück, was der Browser
ankündigt — jeder gelistete Origin durfte also jeden beliebigen Header senden.

Die zu weite Freigabe ist nur die eine Hälfte. Eine Wildcard kann auch nicht
falsch werden: fällt ein Header weg, den das Protokoll braucht, bleibt alles
grün. Die Liste ist prüfbar, die Wildcard nicht.

Geprüft wird mit echten Preflights gegen die zusammengebaute App. Dafür musste
`build_http_app` aus `main` heraus — solange der Aufbau neben `uvicorn.run`
stand, liess sich die Liste nur lesen, nicht ausprobieren, und eine Liste, die
richtig aussieht, kann trotzdem nie an der Middleware ankommen.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from swiss_efv_mcp.__main__ import CORS_ALLOW_HEADERS, CORS_ALLOW_METHODS, build_http_app
from swiss_efv_mcp.server import mcp
from swiss_efv_mcp.settings import Settings

ORIGIN = "https://client.example"

# Beide Netz-Transporte. Eine Kontrolle, die auf einem hält und auf dem anderen
# nicht, ist schlimmer als eine fehlende: sie sieht nach Durchsetzung aus.
PFADE = {"http": "/mcp/", "sse": "/sse/"}


@pytest.fixture(params=["http", "sse"])
def transport(request) -> str:
    return request.param


@pytest.fixture
def client(transport: str) -> TestClient:
    return TestClient(
        build_http_app(Settings(_env_file=None, transport=transport, cors_origins=[ORIGIN]))
    )


def preflight(client: TestClient, transport: str, request_headers: str, method: str = "POST"):
    """Sende einen Preflight.

    `request_headers` ist, was der Browser anzukündigen vorgibt. Das muss auf
    der Anfrage reiten und nicht bloss von der Antwort abgelesen werden:
    Starlette beantwortet einen Preflight, der einen nicht freigegebenen Header
    nennt, mit **400 und ohne `Access-Control-Allow-Origin`**.
    """
    return client.options(
        PFADE[transport],
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": request_headers,
        },
    )


@pytest.mark.parametrize("header", CORS_ALLOW_HEADERS)
def test_jeder_freigegebene_header_passiert_den_preflight(
    client: TestClient, transport: str, header: str
) -> None:
    """Einzeln parametrisiert: ein Sammelaufruf bliebe grün, wenn nur einer der
    Header freigegeben wäre und Starlette den Rest durchwinkte."""
    resp = preflight(client, transport, header)
    assert resp.status_code == 200, f"Preflight mit {header} abgewiesen"
    assert header.lower() in resp.headers["access-control-allow-headers"].lower()


def test_die_header_zusammen(client: TestClient, transport: str) -> None:
    """Was ein Browser tatsächlich schickt: alle auf derselben Anfrage."""
    resp = preflight(client, transport, ", ".join(h.lower() for h in CORS_ALLOW_HEADERS))
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_ein_nicht_freigegebener_header_wird_abgewiesen(client: TestClient, transport: str) -> None:
    """Die Gegenkontrolle — und der eigentliche Befund.

    Ohne sie wären die Tests darüber gegen die alte Wildcard genauso grün. Sie
    ist die einzige Zusicherung hier, die zwischen «Liste» und «alles erlaubt»
    unterscheidet.
    """
    resp = preflight(client, transport, "x-beliebiger-header")
    assert resp.status_code == 400, "die Freigabeliste winkt weiterhin alles durch"


def test_die_liste_nennt_den_session_header() -> None:
    from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

    assert MCP_SESSION_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_die_liste_nennt_den_wiederaufnahme_header() -> None:
    """`Last-Event-ID` setzt einen abgerissenen SSE-Strom fort. Fehlt er, bricht
    ausschliesslich die Wiederaufnahme nach Paketverlust — unter Last, in
    Produktion, ohne dass ein Test etwas dazu sagt."""
    from mcp.server.streamable_http import LAST_EVENT_ID_HEADER

    assert LAST_EVENT_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_keine_wildcard_in_der_freigabeliste() -> None:
    """Die Regression, die dieser Test abfängt, war genau ein Zeichen."""
    assert "*" not in CORS_ALLOW_HEADERS


def test_die_routing_header_stehen_in_der_freigabeliste() -> None:
    """Die drei Header, über die Spec `2026-07-28` eine Anfrage routet.

    Dieser Test hiess bis zum 18.9.2026 `..._sobald_das_sdk_sie_liest` und
    übersprang sich unter `mcp` 1.x, wo es die Header nicht gab. Er hat
    ausgelöst: `fastmcp>=4` zieht `mcp` 2.x herein, und
    `mcp.server._streamable_http_modern` liest sie auf jeder Anfrage der
    modernen Ära.

    Die Namen kommen weiterhin aus `mcp.shared.inbound` und nicht aus einem
    Literal: eine abgeschriebene Liste kann still von der SDK-Schreibweise
    abweichen, und CORS-Header sind auf beiden Seiten kleingeschrieben zu
    vergleichen.
    """
    from mcp.shared.inbound import (
        MCP_METHOD_HEADER,
        MCP_NAME_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
    )

    erlaubt = {h.lower() for h in CORS_ALLOW_HEADERS}
    noetig = {MCP_METHOD_HEADER, MCP_NAME_HEADER, MCP_PROTOCOL_VERSION_HEADER}
    assert noetig <= erlaubt, (
        f"Die Freigabeliste nennt die Routing-Header nicht: {sorted(noetig - erlaubt)}"
    )


async def test_kein_tool_verlangt_einen_mcp_param_header() -> None:
    """Warum `Mcp-Param-*` **nicht** in der Freigabeliste steht.

    Ein Client sendet einen solchen Header nur für einen Parameter, dessen
    Schema die Annotation `x-mcp-header` trägt. Kein Tool dieses Servers tut
    das, also würde ein Eintrag einen Header freigeben, den nie jemand schickt
    — dieselbe Raterei wie die Wildcard, nur kleiner. Eine CORS-Liste kann ein
    Präfix ohnehin nicht ausdrücken; käme die Annotation je dazu, bräuchte es
    eine andere Lösung als eine Zeile mehr.

    Der Test ist deshalb an die Schemata gebunden und nicht an diesen Absatz:
    bekommt ein Tool die Annotation, fällt er.
    """
    from mcp.shared.inbound import X_MCP_HEADER_KEY

    def traegt_annotation(knoten) -> bool:
        if isinstance(knoten, dict):
            return X_MCP_HEADER_KEY in knoten or any(traegt_annotation(v) for v in knoten.values())
        if isinstance(knoten, list):
            return any(traegt_annotation(v) for v in knoten)
        return False

    # Gegen das *ausgelieferte* Schema geprueft, nicht gegen die Registrierung:
    # der Client entscheidet anhand dessen, was `tools/list` ihm zeigt.
    async with Client(mcp) as c:
        tools = await c.list_tools()
    schuldige = [t.name for t in tools if traegt_annotation(t.input_schema)]
    assert not schuldige, (
        f"{schuldige} tragen jetzt `{X_MCP_HEADER_KEY}`; ein Browser-Client sendet "
        f"dafuer `Mcp-Param-*`-Header, die der Preflight abweist."
    )


@pytest.mark.parametrize("methode", ["GET", "POST", "DELETE"])
def test_jede_freigegebene_methode_passiert_den_preflight(
    client: TestClient, transport: str, methode: str
) -> None:
    """`DELETE` fehlte, und der Preflight wies es mit 400 ab.

    Ein Browser-Client konnte damit Sessions öffnen, aber nie schliessen. Das
    SDK bedient die Methode sehr wohl — `_handle_delete_request` in
    `mcp.server.streamable_http`, und dessen eigene 405-Antwort wirbt mit
    `Allow: GET, POST, DELETE`. Die Freigabeliste war schmaler als der Server.

    Einzeln parametrisiert, damit im Fehlerfall die Methode im Testnamen steht
    und nicht erst aus einer Sammelmeldung herausgelesen werden muss.
    """
    resp = preflight(client, transport, "content-type", method=methode)
    assert resp.status_code == 200, f"Preflight für {methode} abgewiesen"
    assert methode.lower() in resp.headers["access-control-allow-methods"].lower()


def test_eine_nicht_freigegebene_methode_wird_abgewiesen(
    client: TestClient, transport: str
) -> None:
    """Die Gegenkontrolle. Ohne sie wäre der Test darüber auch gegen eine
    Methoden-Wildcard grün — was eine andere Lücke wäre, keine Behebung."""
    resp = preflight(client, transport, "content-type", method="PATCH")
    assert resp.status_code == 400, "die Methodenliste winkt alles durch"


def test_die_methodenliste_nennt_die_sessionbeendigung() -> None:
    """`DELETE` ist der Grund für diese Liste; die Zusicherung hält ihn fest,
    auch wenn jemand die Liste später umbaut."""
    assert "DELETE" in CORS_ALLOW_METHODS


def test_ein_fremder_origin_wird_weiterhin_abgewiesen(client: TestClient, transport: str) -> None:
    """Die Header-Liste ändert nichts an der Origin-Prüfung."""
    resp = client.options(
        PFADE[transport],
        headers={
            "Origin": "https://fremd.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


def test_ohne_konfigurierte_origins_gibt_es_keine_cors_schicht() -> None:
    """Fail-closed: ohne `EFV_MCP_CORS_ORIGINS` wird die Middleware gar nicht
    erst angehängt, ein Preflight bekommt also keine Freigabe."""
    # Als Kontextmanager, damit der Lifespan laeuft: ohne CORS-Schicht gibt es
    # keine Kurzschluss-Antwort, der OPTIONS erreicht also die App selbst.
    with TestClient(build_http_app(Settings(_env_file=None, cors_origins=[]))) as client:
        resp = client.options(
            PFADE["http"],
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert "access-control-allow-origin" not in resp.headers
