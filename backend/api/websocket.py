"""
WebSocket handler for ARIA real-time sessions.

Architecture:
  - Audio goes to Gemini Live for voice conversation (audio in -> audio out)
  - Gemini Live transcribes what the user says
  - If the transcription is an action command, it's routed to the ADK agent
  - ADK agent executes browser tools and sends action updates (no duplicate text)
  - Text typed in chat always goes to ADK agent and gets a text response
  - Screenshots are stored as context for the ADK agent
"""

import asyncio
import base64
import json
import logging
import re
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from agents.runner import ARIAAgentRunner
from services.gemini_live import gemini_live_service
from services.session import ARIASession, SessionState, session_manager

logger = logging.getLogger("aria.ws")

# Keywords that indicate the user wants ARIA to DO something (route to ADK agent)
ACTION_KEYWORDS = re.compile(
    r"\b(search|cherche|navigate|go to|open|ouvre|va sur|click|clique|type|tape|"
    r"scroll|press|appuie|find|trouve|show|montre|close|ferme|download|"
    r"fill|submit|login|sign|select|visit|play|joue|watch|regarde|"
    r"buy|achete|add|ajoute|remove|supprime|delete|write|ecris|"
    r"read|lis|copy|copie|paste|colle|refresh|actualise|back|retour|"
    r"forward|next|suivant|previous|précédent)\b",
    re.IGNORECASE,
)


def _is_action_command(text: str) -> bool:
    """Check if user speech looks like a browser action command."""
    text = text.strip()
    if len(text) < 3:
        return False
    return bool(ACTION_KEYWORDS.search(text))


class ARIAWebSocketHandler:
    def __init__(self, websocket: WebSocket, session: ARIASession):
        self.ws = websocket
        self.session = session
        self.runner = ARIAAgentRunner(session)

        self._last_screenshot_b64: str | None = None
        self._text_queue: asyncio.Queue[tuple[str, bool]] = asyncio.Queue(maxsize=20)
        # tuple: (message, from_voice) — from_voice=True means don't send text response
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
        self._mic_active = False
        self._audio_chunk_count = 0

    # --- Send helpers ---

    async def send(self, payload: dict[str, Any]):
        try:
            await self.ws.send_text(json.dumps(payload))
        except Exception as e:
            logger.warning(f"WS send failed: {e}")

    async def _on_text(self, text: str, final: bool = True, role: str = "aria"):
        await self.send({"type": "text", "content": text, "final": final, "role": role})

    async def _on_audio(self, audio_bytes: bytes):
        await self.send({"type": "audio", "data": base64.b64encode(audio_bytes).decode()})

    async def _on_state_change(self, state: SessionState):
        await self.send({"type": "state", "state": state.value})

    async def _on_action(self, action: str, detail: str):
        await self.send({"type": "action", "action": action, "detail": detail})

    async def _on_user_speech(self, text: str):
        """Called when Gemini Live transcribes user speech.
        Only route to ADK agent if it's an action command."""
        text = text.strip()
        if not text:
            return

        self.session.add_to_history("user", text)
        # Show user speech in transcript
        await self.send({"type": "text", "content": text, "final": True, "role": "user"})

        # Only route to ADK agent for action commands
        if _is_action_command(text):
            logger.info(f"Action command detected: {text!r}")
            if not self._text_queue.full():
                await self._text_queue.put((text, True))  # from_voice=True
        else:
            logger.info(f"Conversation (handled by Gemini Live voice): {text!r}")

    async def _on_live_text(self, text: str, final: bool = True, role: str = "aria"):
        """Text from Gemini Live output transcription — show in chat as transcript."""
        await self.send({"type": "text", "content": text, "final": final, "role": role})

    # --- Inbound receive loop ---

    async def _receive_loop(self):
        try:
            while True:
                raw = await self.ws.receive_text()
                msg = json.loads(raw)

                match msg.get("type"):
                    case "audio":
                        self._mic_active = True
                        chunk = base64.b64decode(msg["data"])
                        if self._audio_chunk_count % 20 == 0:
                            logger.info(f"Audio chunk #{self._audio_chunk_count}: {len(chunk)} bytes")
                        self._audio_chunk_count += 1
                        if not self._audio_queue.full():
                            await self._audio_queue.put(chunk)

                    case "screenshot":
                        self._last_screenshot_b64 = msg["data"]

                    case "text":
                        content = msg.get("content", "").strip()
                        if content:
                            self.session.add_to_history("user", content)
                            await self._text_queue.put((content, False))  # from_voice=False

                    case "interrupt":
                        self.session.interrupt()
                        await self.send({"type": "notification", "message": "Interrupted.", "level": "info"})
                        await self._on_state_change(SessionState.INTERRUPTED)

                    case "ping":
                        await self.send({"type": "pong"})

        except WebSocketDisconnect:
            logger.info(f"Session {self.session.session_id} disconnected.")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            await self._audio_queue.put(None)
            await self._text_queue.put(("", False))  # sentinel

    # --- ADK text-turn processor ---

    async def _text_processor_loop(self):
        while True:
            content, from_voice = await self._text_queue.get()
            if content == "":
                break
            if self.session.interrupted:
                self.session.resume()
                continue

            try:
                await self._on_state_change(SessionState.THINKING)

                if from_voice:
                    # Voice command: only send actions, no text response (Gemini Live handles voice)
                    await self.runner.run_turn(
                        user_message=content,
                        screenshot_b64=self._last_screenshot_b64,
                        on_text=None,  # no text output — voice already responded
                        on_action=self._on_action,
                        on_state_change=self._on_state_change,
                    )
                else:
                    # Typed text: send full text response
                    await self.runner.run_turn(
                        user_message=content,
                        screenshot_b64=self._last_screenshot_b64,
                        on_text=lambda t: self._on_text(t, final=True),
                        on_action=self._on_action,
                        on_state_change=self._on_state_change,
                    )

                await self._on_state_change(SessionState.LISTENING)
            except Exception as e:
                logger.error(f"ADK turn error: {e}", exc_info=True)
                await self.send({"type": "error", "message": f"Agent error: {e}"})
                await self._on_state_change(SessionState.LISTENING)

    # --- Audio generator for Gemini Live ---

    async def _audio_generator(self):
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                break
            yield chunk

    # --- Main run ---

    async def run(self):
        await self.runner.start()
        await self._on_state_change(SessionState.LISTENING)

        receive_task = asyncio.create_task(self._receive_loop())
        text_proc_task = asyncio.create_task(self._text_processor_loop())
        live_task = asyncio.create_task(self._run_live_session())

        try:
            await receive_task
        except Exception as e:
            logger.error(f"Handler error: {e}")
        finally:
            text_proc_task.cancel()
            live_task.cancel()
            await self.runner.stop()

    async def _run_live_session(self):
        """Run Gemini Live for voice. Falls back to text-only if it fails."""
        try:
            await gemini_live_service.run_session(
                aria_session=self.session,
                audio_input_stream=self._audio_generator(),
                on_text=self._on_live_text,
                on_audio=self._on_audio,
                on_state_change=self._on_state_change,
                on_user_speech=self._on_user_speech,
            )
        except Exception as e:
            logger.error(f"Gemini Live session error: {e}")
            await self.send({
                "type": "notification",
                "message": "Voice mode disconnected. Text commands still work.",
                "level": "warning",
            })


async def handle_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    session = await session_manager.get(session_id)
    if not session:
        await websocket.send_text(
            json.dumps({"type": "error", "message": "Session not found or expired."})
        )
        await websocket.close()
        return

    await websocket.send_text(json.dumps({"type": "state", "state": SessionState.IDLE.value}))

    handler = ARIAWebSocketHandler(websocket, session)
    await handler.run()
