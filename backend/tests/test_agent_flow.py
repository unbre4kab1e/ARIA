"""
End-to-end tests of the agent loop with a scripted LLM and a fake browser:
WebSocket text -> ADK runner -> tool (session id from ToolContext) -> events back.
"""

import asyncio
import json
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

import main
from agents import aria_agent as aria_agent_module
from agents.tools.browser_tools import browser_controller
from services.gemini_live import gemini_live_service


class ScriptedLlm(BaseLlm):
    """First call: ask for navigate_to. Next call: final text answer."""

    model: str = "scripted"
    delay_s: float = 0.0

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        await asyncio.sleep(self.delay_s)
        last = llm_request.contents[-1]
        if any(p.function_response for p in last.parts or []):
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Done!")]))
        else:
            yield LlmResponse(content=types.Content(role="model", parts=[
                types.Part(function_call=types.FunctionCall(
                    name="navigate_to", args={"url": "example.com"}))
            ]))


class FakeBrowser:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def navigate(self, session_id, url):
        self.calls.append((session_id, url))
        return {"status": "ok", "url": url, "title": "Example"}

    async def get_or_create_context(self, session_id):
        return None

    async def close_context(self, session_id):
        pass

    async def frame_jpeg(self, session_id):
        return b"\xff\xd8fake-jpeg"


@pytest.fixture
def env(monkeypatch):
    fake = FakeBrowser()
    for name in ("navigate", "get_or_create_context", "close_context", "frame_jpeg"):
        monkeypatch.setattr(browser_controller, name, getattr(fake, name))

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(browser_controller, "start", noop)
    monkeypatch.setattr(browser_controller, "stop", noop)

    async def no_live(**kwargs):
        await asyncio.Event().wait()  # voice not under test: idle forever

    monkeypatch.setattr(gemini_live_service, "run_session", no_live)

    llm = ScriptedLlm()
    monkeypatch.setattr(aria_agent_module.aria_agent, "model", llm)
    return fake, llm


def _recv_until(ws, predicate, limit=50):
    seen = []
    for _ in range(limit):
        msg = json.loads(ws.receive_text())
        seen.append(msg)
        if predicate(msg):
            return seen
    raise AssertionError(f"condition not met, got: {seen}")


def test_health(env):
    with TestClient(main.app) as client:
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["gemini_configured"] is True


def test_text_command_runs_tool_with_session_id(env):
    fake, _ = env
    with TestClient(main.app) as client:
        session_id = client.post("/api/sessions").json()["session_id"]
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            ws.send_text(json.dumps({"type": "text", "content": "open example.com"}))
            seen = _recv_until(ws, lambda m: m["type"] == "text" and m.get("role") == "aria")

            actions = [m for m in seen if m["type"] == "action"]
            assert actions and actions[0]["action"] == "navigate_to"
            assert seen[-1]["content"] == "Done!"
            # The tool received the real session id without the model passing it
            assert fake.calls == [(session_id, "example.com")]

            frames = _recv_until(ws, lambda m: m["type"] == "browser_frame")
            assert frames[-1]["data"]

        history = client.get(f"/api/sessions/{session_id}/history").json()["history"]
        roles = [h["role"] for h in history]
        assert roles == ["user", "action", "aria"]


def test_interrupt_cancels_turn_and_next_command_still_runs(env):
    fake, llm = env
    llm.delay_s = 1.5
    with TestClient(main.app) as client:
        session_id = client.post("/api/sessions").json()["session_id"]
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            ws.send_text(json.dumps({"type": "text", "content": "open example.com"}))
            _recv_until(ws, lambda m: m.get("state") == "thinking")
            ws.send_text(json.dumps({"type": "interrupt"}))
            _recv_until(ws, lambda m: m.get("state") == "interrupted")
            assert fake.calls == []  # cancelled before the tool ran

            # Regression: the command after an interrupt used to be dropped
            llm.delay_s = 0.0
            ws.send_text(json.dumps({"type": "text", "content": "open example.com"}))
            seen = _recv_until(ws, lambda m: m["type"] == "text" and m.get("role") == "aria")
            assert seen[-1]["content"] == "Done!"
            assert len(fake.calls) == 1


def test_unknown_session_is_rejected(env):
    with TestClient(main.app) as client:
        with client.websocket_connect("/ws/does-not-exist") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"
