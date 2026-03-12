import asyncio
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

import logging

from config import config
from services.session import ARIASession, SessionState

logger = logging.getLogger("aria.live")

ARIA_SYSTEM_PROMPT = """You are ARIA (Adaptive Reality Intelligence Assistant), an advanced AI co-pilot.

Personality:
- Calm, precise, and proactive
- Keep spoken responses short (1-3 sentences)
- When the user asks to search, navigate, click etc., confirm what you will do briefly
- Always confirm task completion: "Done! I have [summary]."
- Respond in the same language as the user
"""


class GeminiLiveService:
    def __init__(self):
        self._client = genai.Client(
            api_key=config.GOOGLE_API_KEY,
            http_options={"api_version": "v1alpha"},
        )

    def _build_live_config(self) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=ARIA_SYSTEM_PROMPT)]
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )

    async def run_session(
        self,
        aria_session: ARIASession,
        audio_input_stream: AsyncIterator[bytes],
        on_text: Any = None,
        on_audio: Any = None,
        on_state_change: Any = None,
        on_user_speech: Any = None,
    ):
        live_config = self._build_live_config()
        logger.info(f"Connecting to Gemini Live: model={config.GEMINI_LIVE_MODEL}")

        async with self._client.aio.live.connect(
            model=config.GEMINI_LIVE_MODEL,
            config=live_config,
        ) as session:
            logger.info("Gemini Live session established.")
            aria_session.state = SessionState.LISTENING
            if on_state_change:
                await on_state_change(SessionState.LISTENING)

            async def _send_audio():
                """Forward raw audio to Gemini Live — it handles VAD, transcription, and response."""
                async for chunk in audio_input_stream:
                    if aria_session.interrupted:
                        continue
                    try:
                        await session.send_realtime_input(
                            media=types.Blob(
                                mime_type="audio/pcm;rate=16000",
                                data=chunk,
                            )
                        )
                    except Exception as e:
                        logger.error(f"Audio send error: {e}")
                        return

            async def _receive():
                # Buffer to accumulate input transcription fragments
                input_buf: list[str] = []

                async for response in session.receive():
                    if not hasattr(response, "server_content") or not response.server_content:
                        continue

                    sc = response.server_content

                    if sc.interrupted:
                        aria_session.interrupt()
                        input_buf.clear()
                        if on_state_change:
                            await on_state_change(SessionState.INTERRUPTED)
                        continue

                    # Audio response from ARIA
                    if hasattr(sc, "model_turn") and sc.model_turn:
                        for part in (sc.model_turn.parts or []):
                            if hasattr(part, "inline_data") and part.inline_data and on_audio:
                                await on_audio(part.inline_data.data)

                    # What ARIA said (text transcript of audio response)
                    if hasattr(sc, "output_transcription") and sc.output_transcription:
                        t = sc.output_transcription
                        if hasattr(t, "text") and t.text and on_text:
                            await on_text(t.text)

                    # What user said — accumulate fragments
                    if hasattr(sc, "input_transcription") and sc.input_transcription:
                        t = sc.input_transcription
                        if hasattr(t, "text") and t.text:
                            input_buf.append(t.text)

                    # Turn complete = user finished speaking
                    if getattr(sc, "turn_complete", False) and input_buf:
                        full_text = "".join(input_buf).strip()
                        input_buf.clear()
                        if full_text:
                            logger.info(f"User said (complete): {full_text!r}")
                            # Notify for ADK routing only — Gemini Live already responds via audio
                            if on_user_speech:
                                await on_user_speech(full_text)

            await asyncio.gather(
                _send_audio(),
                _receive(),
            )

    async def send_text_turn(
        self,
        message: str,
        screenshot_bytes: bytes | None = None,
    ) -> str:
        parts: list[types.Part] = []
        if screenshot_bytes:
            parts.append(
                types.Part(
                    inline_data=types.Blob(mime_type="image/jpeg", data=screenshot_bytes)
                )
            )
        parts.append(types.Part(text=message))

        response = await self._client.aio.models.generate_content(
            model=config.GEMINI_VISION_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=ARIA_SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )
        return response.text


gemini_live_service = GeminiLiveService()
