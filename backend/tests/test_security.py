import json

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

import main
from config import config
from services import url_guard
from services.url_guard import check_url


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://169.254.169.254/computeMetadata/v1/",   # cloud metadata server
    "http://metadata.google.internal/",
    "http://localhost:8000/api/health",
    "http://127.0.0.1/",
    "http://10.0.0.5/",
    "http://192.168.1.1/admin",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "chrome://settings",
])
async def test_internal_urls_are_blocked(url):
    assert await check_url(url) is not None


@pytest.mark.asyncio
async def test_public_url_allowed():
    assert await check_url("https://8.8.8.8/") is None


@pytest.mark.asyncio
async def test_hostname_resolving_to_private_ip_is_blocked(monkeypatch):
    async def fake_getaddrinfo(host, *a, **k):
        return [(None, None, None, None, ("10.1.2.3", 0))]

    class Loop:
        getaddrinfo = staticmethod(fake_getaddrinfo)

    monkeypatch.setattr(url_guard.asyncio, "get_running_loop", lambda: Loop())
    url_guard._dns_cache.clear()
    assert await check_url("https://evil-rebind.example/") is not None
    url_guard._dns_cache.clear()


@pytest.mark.asyncio
async def test_private_network_opt_in(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_PRIVATE_NETWORK", True)
    assert await check_url("http://127.0.0.1:8765/") is None
    assert await check_url("file:///etc/passwd") is not None  # schemes stay restricted


@pytest.fixture
def token_app(monkeypatch):
    async def noop(*a, **k):
        return None

    monkeypatch.setattr(config, "ACCESS_TOKEN", "s3cret")
    monkeypatch.setattr(main, "check_gemini", noop)
    monkeypatch.setattr(main.browser_controller, "start", noop)
    monkeypatch.setattr(main.browser_controller, "stop", noop)
    with TestClient(main.app) as client:
        yield client


def test_api_requires_token(token_app):
    assert token_app.get("/api/health").status_code == 200  # health stays public
    assert token_app.get("/api/health").json()["auth_required"] is True
    assert token_app.post("/api/sessions").status_code == 401
    assert token_app.post("/api/sessions", headers={"X-ARIA-Token": "wrong"}).status_code == 401
    assert token_app.post("/api/sessions", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_websocket_requires_token(token_app):
    sid = token_app.post("/api/sessions", headers={"X-ARIA-Token": "s3cret"}).json()["session_id"]
    with token_app.websocket_connect(f"/ws/{sid}") as ws:
        assert json.loads(ws.receive_text())["type"] == "error"
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
        assert closed.value.code == 4401
