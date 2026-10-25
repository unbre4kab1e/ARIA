"""The Live receive loop must survive multiple turns (receive() stops at turn_complete)."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace as NS

import pytest

from services.gemini_live import gemini_live_service
from services.session import ARIASession


def _msg(**sc):
    base = dict(interrupted=False, model_turn=None, output_transcription=None,
                input_transcription=None, turn_complete=False)
    base.update(sc)
    return NS(server_content=NS(**base), tool_call=None, tool_call_cancellation=None,
              session_resumption_update=None, go_away=None)


TURNS = [
    [_msg(input_transcription=NS(text="Bonjour ")), _msg(input_transcription=NS(text="ARIA")),
     _msg(model_turn=NS(parts=[NS(inline_data=NS(data=b"pcm1"))]), output_transcription=NS(text="Salut")),
     _msg(output_transcription=NS(text=" !")), _msg(turn_complete=True)],
    [_msg(input_transcription=NS(text="Cherche des vols")),
     _msg(model_turn=NS(parts=[NS(inline_data=NS(data=b"pcm2"))])), _msg(turn_complete=True)],
]


class FakeLiveSession:
    def __init__(self):
        self.turns = list(TURNS)
        self.audio_in: list[bytes] = []

    async def send_realtime_input(self, audio=None, **_):
        self.audio_in.append(audio.data)

    async def receive(self):
        if not self.turns:
            return
        for m in self.turns.pop(0):
            yield m


@pytest.mark.asyncio
async def test_multi_turn_live_session(monkeypatch):
    fake = FakeLiveSession()

    @asynccontextmanager
    async def connect(**_):
        yield fake

    monkeypatch.setattr(gemini_live_service._client.aio.live, "connect", connect)

    async def audio():
        yield b"chunk"
        await asyncio.Event().wait()  # mic stays open; the server closing ends the session

    texts, audios, speech = [], [], []

    async def on_text(t, final=True):
        texts.append((t, final))

    async def on_audio(a):
        audios.append(a)

    async def on_user_speech(t):
        speech.append(t)

    await asyncio.wait_for(gemini_live_service.run_session(
        aria_session=ARIASession(session_id="s"),
        audio_input_stream=audio(),
        on_text=on_text, on_audio=on_audio, on_user_speech=on_user_speech,
    ), timeout=5)

    assert fake.audio_in == [b"chunk"]
    assert audios == [b"pcm1", b"pcm2"]          # second turn is not lost
    assert speech == ["Bonjour ARIA", "Cherche des vols"]
    assert texts == [("Salut", False), ("Salut !", False), ("Salut !", True)]


@pytest.mark.asyncio
async def test_tool_call_runs_and_answers_live(monkeypatch):
    """Gemini Live calls execute_browser_task; the handler's report is sent back."""
    tool_msg = NS(server_content=None, tool_call_cancellation=None, session_resumption_update=None,
                  go_away=None, tool_call=NS(function_calls=[
                      NS(id="call-1", name="execute_browser_task", args={"instruction": "find flights"})]))

    class ToolSession(FakeLiveSession):
        def __init__(self):
            super().__init__()
            self.turns = [[_msg(input_transcription=NS(text="Trouve des vols")), tool_msg]]
            self.responses = []
            self.answered = asyncio.Event()

        async def send_tool_response(self, function_responses):
            self.responses.extend(function_responses)
            self.answered.set()

        async def receive(self):
            if self.turns:
                for m in self.turns.pop(0):
                    yield m
                return
            await self.answered.wait()  # stream stays open until the tool answered

    fake = ToolSession()

    @asynccontextmanager
    async def connect(**kwargs):
        assert kwargs["config"].tools  # the tool is declared to the model
        yield fake

    monkeypatch.setattr(gemini_live_service._client.aio.live, "connect", connect)

    calls, speech = [], []

    async def on_tool_call(name, args):
        calls.append((name, args))
        return {"status": "done", "report": "Found a flight for 420 EUR"}

    async def on_user_speech(t):
        speech.append(t)

    async def audio():
        await asyncio.Event().wait()
        yield b""

    await asyncio.wait_for(gemini_live_service.run_session(
        aria_session=ARIASession(session_id="s"), audio_input_stream=audio(),
        on_user_speech=on_user_speech, on_tool_call=on_tool_call,
    ), timeout=5)

    assert speech == ["Trouve des vols"]  # shown before the action starts
    assert calls == [("execute_browser_task", {"instruction": "find flights"})]
    assert fake.responses[0].id == "call-1"
    assert fake.responses[0].response["report"] == "Found a flight for 420 EUR"
