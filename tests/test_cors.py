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
from starlette.testclient import TestClient

from swiss_efv_mcp.__main__ import CORS_ALLOW_HEADERS, build_http_app
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


def test_die_routing_header_gehoeren_hierher_sobald_das_sdk_sie_liest() -> None:
    """Warum `Mcp-Method` & Co. hier **nicht** stehen — und wann sie müssen.

    Spec `2026-07-28` routet eine Anfrage über drei Header. Gelesen werden sie
    von `mcp.shared.inbound`, und das Modul gibt es erst ab `mcp` 2.x. fastmcp
    3.x pinnt `mcp` 1.x: dieser Server liest sie schlicht nicht, und sie zu
    nennen wäre dieselbe Raterei wie die Wildcard.

    Der Test ist deshalb an das SDK gebunden statt an eine Notiz im Kommentar.
    Zieht ein Upgrade `mcp.shared.inbound` herein, fällt er — und sagt, dass die
    Liste nachziehen muss, bevor Browser-Clients daran scheitern.
    """
    try:
        from mcp.shared.inbound import (
            MCP_METHOD_HEADER,
            MCP_NAME_HEADER,
            MCP_PROTOCOL_VERSION_HEADER,
        )
    except ModuleNotFoundError:
        pytest.skip("mcp 1.x: es gibt keine Routing-Header, die freizugeben waeren")

    erlaubt = {h.lower() for h in CORS_ALLOW_HEADERS}
    noetig = {MCP_METHOD_HEADER, MCP_NAME_HEADER, MCP_PROTOCOL_VERSION_HEADER}
    assert noetig <= erlaubt, (
        f"Das SDK liest jetzt Routing-Header, die Freigabeliste nennt sie nicht: "
        f"{sorted(noetig - erlaubt)}"
    )


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
