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
    return NS(server_content=NS(**base))


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
