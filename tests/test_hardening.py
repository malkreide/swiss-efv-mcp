"""Regression tests for the security/observability hardening.

Covers the audit-driven changes: egress allow-list (SEC-021/004), error-detail
masking (OBS-002), tool annotations (ARCH-009), and typed settings (SEC-018).
"""

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from swiss_efv_mcp.client import DATASETS, EFVClient, assert_host_allowed
from swiss_efv_mcp.server import (
    MCP_HANDSHAKE_PROTOCOL_VERSION,
    MCP_MODERN_PROTOCOL_VERSION,
    headline_impl,
    mcp,
    status_impl,
)
from swiss_efv_mcp.server import client as server_client
from swiss_efv_mcp.settings import Settings
from tests.conftest import FIXTURES

# --- SEC-021 / SEC-004: egress allow-list -----------------------------------


def test_allowlist_accepts_efv_hosts():
    assert_host_allowed("https://www.efv.admin.ch/dam/x.csv")
    assert_host_allowed("https://www.data.finance.admin.ch/y.csv")


def test_allowlist_rejects_off_host():
    with pytest.raises(ValueError):
        assert_host_allowed("https://evil.example/x")


def test_allowlist_rejects_non_https():
    with pytest.raises(ValueError):
        assert_host_allowed("http://www.efv.admin.ch/x")


def test_allowlist_rejects_ip_literal():
    # SEC-004: an IP literal is never on the hostname allow-list.
    with pytest.raises(ValueError):
        assert_host_allowed("https://169.254.169.254/latest/meta-data")


@respx.mock
async def test_redirect_off_host_is_rejected():
    # SEC-004: a redirect to a disallowed host must be refused on the final URL.
    respx.get(DATASETS["headline"].url).mock(
        return_value=httpx.Response(302, headers={"Location": "https://evil.example/x"})
    )
    respx.get("https://evil.example/x").mock(return_value=httpx.Response(200, text="a,b\n1,2\n"))
    c = EFVClient(backoff_base=0)
    with pytest.raises(ValueError):
        await c.load("headline")


def test_dataset_urls_are_all_allowed():
    # Every shipped dataset URL must satisfy the allow-list.
    for ds in DATASETS.values():
        assert_host_allowed(ds.url)


# --- OBS-002: error-detail masking ------------------------------------------


@respx.mock
async def test_error_message_is_masked():
    respx.get(DATASETS["headline"].url).mock(
        side_effect=httpx.ConnectError("secret internal detail 10.0.0.5")
    )
    c = EFVClient(backoff_base=0)
    with pytest.raises(RuntimeError):
        await c.load("headline")
    report = status_impl(c)
    last_error = report.datasets["headline"]["last_error"]
    assert last_error is not None
    # The masked message must not leak the raw upstream exception text/body.
    assert "secret internal detail" not in last_error
    assert "10.0.0.5" not in last_error
    assert "upstream fetch failed" in last_error  # generic, model-safe message


# --- ARCH-009: tool annotations ---------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "fiscal_headline",
        "fiscal_budget_breakdown",
        "fiscal_by_institution",
        "fiscal_list_dimensions",
        "fiscal_status",
        "dump_status",
    ],
)
async def test_tools_are_annotated_read_only(name):
    tool = await mcp.get_tool(name)
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False


# --- SEC-018 / settings -----------------------------------------------------


def test_settings_defaults_are_safe():
    s = Settings()
    assert s.transport == "stdio"
    assert s.host == "127.0.0.1"  # loopback by default (SEC-016)
    assert s.cors_origins == []  # default-deny


def test_cors_origins_accepts_csv(monkeypatch):
    monkeypatch.setenv("EFV_MCP_CORS_ORIGINS", "https://a.example, https://b.example")
    s = Settings()
    assert s.cors_origins == ["https://a.example", "https://b.example"]


# --- SDK-001: shared HTTP client --------------------------------------------


@respx.mock
async def test_client_is_reused_across_loads():
    respx.get(DATASETS["headline"].url).mock(return_value=httpx.Response(200, text="a,b\n1,2\n"))
    c = EFVClient()
    await c.load("headline")
    first = c._http
    # A second (uncached) dataset load must reuse the same client instance.
    respx.get(DATASETS["budget"].url).mock(return_value=httpx.Response(200, text="a\n1\n"))
    await c.load("budget")
    assert c._http is first is not None
    await c.aclose()
    assert c._http is None


# --- OBS-001: protocol vs execution error separation ------------------------


@respx.mock
async def test_execution_error_is_isError_not_leaking(monkeypatch):
    # Force the shared server client's fetch to fail with a secret-bearing error.
    respx.get(DATASETS["headline"].url).mock(
        side_effect=httpx.ConnectError("secret detail 10.0.0.5")
    )
    monkeypatch.setattr(server_client, "backoff_base", 0)
    async with Client(mcp) as c:
        res = await c.call_tool("fiscal_headline", {"variable": "saldo"}, raise_on_error=False)
    assert res.is_error is True  # execution error -> isError tool-result
    assert "secret detail" not in str(res.content)  # masked (mask_error_details)
    assert "10.0.0.5" not in str(res.content)


async def test_protocol_error_on_unknown_tool():
    async with Client(mcp) as c:
        with pytest.raises(ToolError):
            await c.call_tool("does_not_exist", {})


# --- ARCH-012: protocol version is pinned -----------------------------------
#
# Beide Aeren werden mit einer echten Verbindung nachgefahren, nicht bloss
# gegen Konstanten gehalten (das tut `tests/test_protocol_version.py`). Ein
# SDK-Update, das die ausgehandelte Revision verschiebt, faellt hier laut auf
# statt still zu driften.


async def test_negotiated_protocol_version_matches_modern_pin():
    """Was eine frische Verbindung heute aushandelt: die moderne Aera."""
    async with Client(mcp) as c:
        assert c.protocol_version == MCP_MODERN_PROTOCOL_VERSION


async def test_the_handshake_era_is_still_served_at_its_pin():
    """Ein Client der alten Aera bekommt weiterhin eine Verbindung.

    Ohne diese Zeile sagte der Pin nichts darueber, was `mode="legacy"`
    bekommt — und die Handshake-Obergrenze waere eine Zahl, die niemand
    nachfaehrt.
    """
    async with Client(mcp, mode="legacy") as c:
        assert c.protocol_version == MCP_HANDSHAKE_PROTOCOL_VERSION


async def test_die_moderne_verbindung_hat_gar_kein_initialize_ergebnis():
    """Warum der Pin nicht mehr gegen `initialize_result` geprueft wird.

    Bis zum 18.9.2026 stand hier `c.initialize_result.protocolVersion`. Auf
    einer Verbindung der Aera `2026-07-28` gibt es keinen `initialize`-Handshake
    mehr, `initialize_result` ist `None` — die alte Zusicherung faellt dort mit
    einem `AttributeError` auf `NoneType`, also mit einer Meldung, die nach
    einem kaputten Test klingt und nicht nach einem Aerenwechsel.

    `protocol_version` ist der aeren-neutrale Zugang und wird oben benutzt.
    Diese Zeile haelt den Grund fest, damit niemand die alte Form zurueckbaut.
    """
    async with Client(mcp) as c:
        assert c.protocol_version == MCP_MODERN_PROTOCOL_VERSION
        assert c.initialize_result is None
    async with Client(mcp, mode="legacy") as c:
        assert c.initialize_result is not None


# --- SEC-022: fiscal_ namespace + deprecated alias --------------------------


async def test_dump_status_is_deprecated_alias_of_fiscal_status():
    canonical = await mcp.get_tool("fiscal_status")
    alias = await mcp.get_tool("dump_status")
    assert canonical.annotations.read_only_hint is True
    assert "DEPRECATED" in (alias.description or "")
    assert "fiscal_status" in (alias.description or "")


# --- SDK-002: typed output schema -------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "fiscal_headline",
        "fiscal_budget_breakdown",
        "fiscal_by_institution",
        "fiscal_list_dimensions",
        "fiscal_status",
        "dump_status",
    ],
)
async def test_tools_expose_output_schema(name):
    tool = await mcp.get_tool(name)
    assert tool.output_schema is not None  # typed Pydantic return -> outputSchema


@respx.mock
async def test_structured_content_carries_envelope():
    for key, csv_text in FIXTURES.items():
        respx.get(DATASETS[key].url).mock(return_value=httpx.Response(200, text=csv_text))
    async with Client(mcp) as c:
        res = await c.call_tool("fiscal_headline", {"variable": "saldo"})
    sc = res.structured_content or {}
    assert "provenance" in sc and "source" in sc and "points" in sc


# --- ARCH-003: no silent empties --------------------------------------------


@respx.mock
async def test_empty_result_has_guidance_note():
    for key, csv_text in FIXTURES.items():
        respx.get(DATASETS[key].url).mock(return_value=httpx.Response(200, text=csv_text))
    res = await headline_impl(EFVClient(), variable="does-not-exist")
    assert res.points == []
    assert res.note is not None
    assert "fiscal_list_dimensions" in res.note
