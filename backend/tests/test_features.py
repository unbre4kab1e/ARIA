import asyncio
import json
import os
import time
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from google.adk.models import LlmRequest
from google.genai import types

import main
from agents.aria_agent import keep_only_latest_image
from agents.tools.browser_tools import SENSITIVE_ACTION, BrowserController
from config import config
from services import startup_check
from services.gemini_live import gemini_live_service
from services.session import ARIASession, SessionManager
from tests.test_agent_flow import env, _recv_until  # noqa: F401 (fixture)

CHROMIUM = os.environ.get("BROWSER_EXECUTABLE_PATH", "")


def _img():
    return types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=b"img"))


def test_only_latest_screenshot_reaches_the_model():
    req = LlmRequest(contents=[
        types.Content(role="user", parts=[_img(), types.Part(text="first")]),
        types.Content(role="model", parts=[types.Part(text="ok")]),
        types.Content(role="user", parts=[_img(), types.Part(text="second")]),
    ])
    keep_only_latest_image(None, req)
    first, _, last = req.contents
    assert [p.text for p in first.parts] == ["[earlier screenshot omitted]", "first"]
    assert last.parts[0].inline_data is not None


@pytest.mark.parametrize("label,sensitive", [
    ("Buy now", True), ("Acheter", True), ("Passer au paiement", True), ("Place order", True),
    ("Envoyer le message", True), ("Supprimer", True),
    ("Search", False), ("Rechercher", False), ("Next page", False), ("Accept cookies", False),
])
def test_sensitive_labels(label, sensitive):
    assert bool(SENSITIVE_ACTION.search(label)) is sensitive


@pytest.mark.asyncio
@pytest.mark.skipif(not CHROMIUM and not os.environ.get("ARIA_TEST_BROWSER"),
                    reason="needs Chromium (set BROWSER_EXECUTABLE_PATH or ARIA_TEST_BROWSER=1)")
async def test_sensitive_click_needs_confirmation(monkeypatch):
    monkeypatch.setattr(config, "BROWSER_EXECUTABLE_PATH", CHROMIUM)
    browser = BrowserController()
    await browser.start()
    try:
        page = await (await browser.get_or_create_context("s")).new_page()
        await page.set_content(
            "<button id=buy onclick=\"document.title='bought'\">Acheter maintenant</button>"
            "<button id=go onclick=\"document.title='searched'\">Rechercher</button>"
        )
        assert (await browser.click("s", selector="#go"))["status"] == "ok"
        assert await page.title() == "searched"

        blocked = await browser.click("s", selector="#buy")
        assert blocked["status"] == "needs_confirmation"
        assert await page.title() == "searched"  # nothing bought
        blocked = await browser.click("s", x=20, y=15)  # same button, by coordinates
        assert blocked["status"] == "needs_confirmation"

        assert (await browser.click("s", selector="#buy", confirmed=True))["status"] == "ok"
        assert await page.title() == "bought"

        nav = await browser.navigate("s", "http://169.254.169.254/")
        assert nav["status"] == "error" and "blocked" in nav["error"]
    finally:
        await browser.stop()


def test_session_expires_after_reconnect_grace(monkeypatch):
    monkeypatch.setattr(config, "RECONNECT_GRACE_SECONDS", 60)
    s = ARIASession(session_id="s")
    assert not s.is_expired()          # created, never connected yet
    s.mark_connected()
    s.mark_disconnected()
    assert not s.is_expired()          # within the grace period
    s.disconnected_at = time.time() - 61
    assert s.is_expired()
    s.mark_connected()                 # came back
    assert not s.is_expired()


@pytest.mark.asyncio
async def test_expired_sessions_release_their_runner():
    stopped = []
    manager = SessionManager()
    session = await manager.create()
    session.runner = NS(stop=lambda: _record(stopped))
    session.last_active = 0
    assert await manager.cleanup_expired() == 1
    assert stopped == [True]


async def _record(lst):
    lst.append(True)


def test_reconnect_keeps_agent_memory(env):
    with TestClient(main.app) as client:
        sid = client.post("/api/sessions").json()["session_id"]
        with client.websocket_connect(f"/ws/{sid}") as ws:
            ws.send_text(json.dumps({"type": "text", "content": "open example.com"}))
            _recv_until(ws, lambda m: m["type"] == "text" and m.get("role") == "aria")
        session = main.session_manager._sessions[sid]
        runner, adk_id = session.runner, session.runner._adk_session.id

        with client.websocket_connect(f"/ws/{sid}") as ws:
            _recv_until(ws, lambda m: m.get("state") == "listening")
        assert session.runner is runner
        assert session.runner._adk_session.id == adk_id

        client.delete(f"/api/sessions/{sid}")
        assert session.runner is None  # browser context released


def test_voice_task_goes_through_agent_and_back_to_live(env, monkeypatch):
    """Live calls execute_browser_task -> ADK agent runs navigate_to -> report to Live."""
    fake_browser, _ = env
    responses: list[dict] = []

    async def fake_live(**kw):
        result = await kw["on_tool_call"]("execute_browser_task", {"instruction": "open example.com"})
        responses.append(result)
        await asyncio.Event().wait()

    monkeypatch.setattr(gemini_live_service, "run_session", fake_live)
    with TestClient(main.app) as client:
        sid = client.post("/api/sessions").json()["session_id"]
        with client.websocket_connect(f"/ws/{sid}") as ws:
            seen = _recv_until(ws, lambda m: m["type"] == "action")
            assert seen[-1]["action"] == "navigate_to"
            _recv_until(ws, lambda m: m.get("state") == "listening")
            # Voice turns don't post the agent text: Gemini Live speaks it
            for _ in range(50):
                if responses:
                    break
                time.sleep(0.05)
    assert responses and responses[0]["status"] == "done"
    assert responses[0]["report"] == "Done!"
    assert responses[0]["actions"] == ["navigate_to: example.com"]
    assert fake_browser.calls[0][1] == "example.com"


@pytest.mark.asyncio
async def test_startup_check_reports_bad_key(monkeypatch):
    async def bad_get(model):
        raise RuntimeError("400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key.")

    monkeypatch.setattr(startup_check.genai, "Client", lambda **k: NS(aio=NS(models=NS(get=bad_get))))
    await startup_check.check_gemini()
    assert "invalid" in startup_check.gemini_status["status"]


@pytest.mark.asyncio
async def test_startup_check_reports_unknown_model(monkeypatch):
    async def get(model):
        if model == config.GEMINI_LIVE_MODEL:
            raise RuntimeError("404 NOT_FOUND. models/x is not found")

    monkeypatch.setattr(startup_check.genai, "Client", lambda **k: NS(aio=NS(models=NS(get=get))))
    await startup_check.check_gemini()
    assert startup_check.gemini_status["status"] == f"GEMINI_LIVE_MODEL={config.GEMINI_LIVE_MODEL} does not exist"


@pytest.mark.asyncio
@pytest.mark.skipif(not CHROMIUM and not os.environ.get("ARIA_TEST_BROWSER"),
                    reason="needs Chromium (set BROWSER_EXECUTABLE_PATH or ARIA_TEST_BROWSER=1)")
async def test_page_cannot_reach_private_network(monkeypatch):
    """Requests made by a page (fetch, images, redirects) are guarded too."""
    async def handle(reader, writer):
        await reader.read(1024)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nhi")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    probe = f"fetch('http://127.0.0.1:{port}/', {{mode: 'no-cors'}}).then(() => 'reached', () => 'blocked')"

    monkeypatch.setattr(config, "BROWSER_EXECUTABLE_PATH", CHROMIUM)
    browser = BrowserController()
    await browser.start()
    try:
        page = await (await browser.get_or_create_context("s")).new_page()
        assert await page.evaluate(probe) == "blocked"
        monkeypatch.setattr(config, "ALLOW_PRIVATE_NETWORK", True)
        assert await page.evaluate(probe) == "reached"  # control: the server is up
    finally:
        await browser.stop()
        server.close()
