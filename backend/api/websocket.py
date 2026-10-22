"""
WebSocket handler for ARIA real-time sessions.

Architecture:
  - Audio goes to Gemini Live for voice conversation (audio in -> audio out)
  - Gemini Live transcribes what the user says
  - If the transcription is an action command, it's routed to the ADK agent
  - ADK agent executes browser tools and sends action updates (no duplicate text)
  - Text typed in chat always goes to ADK agent and gets a text response
  - Screenshots are stored as context for the ADK agent
  - Frames of ARIA's own (headless) browser are streamed back as "browser_frame"
  - "interrupt" cancels the running agent turn
"""

import asyncio
import base64
import hashlib
import json
import logging
import re
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from agents.runner import ARIAAgentRunner
from agents.tools.browser_tools import browser_controller
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
        self._text_queue: asyncio.Queue[tuple[str, bool]] = asyncio.Queue()
        # tuple: (message, from_voice) — from_voice=True means don't send text response
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
        self._mic_active = False
        self._audio_chunk_count = 0
        self._current_turn: asyncio.Task | None = None
        self._last_frame_hash: str | None = None

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

    async def _on_action(self, action: str, detail: str, args: dict | None = None):
        payload: dict[str, Any] = {"type": "action", "action": action, "detail": detail}
        args = args or {}
        x, y = args.get("x"), args.get("y")
        if action == "click_element" and isinstance(x, (int, float)) and isinstance(y, (int, float)) and x >= 0 and y >= 0:
            payload["x"], payload["y"] = x, y
        await self.send(payload)
        if action == "notify_user" and args.get("message"):
            await self.send({
                "type": "notification",
                "message": args["message"],
                "level": args.get("level", "info"),
            })

    async def _push_browser_frame(self):
        frame = await browser_controller.frame_jpeg(self.session.session_id)
        if not frame:
            return
        digest = hashlib.md5(frame).hexdigest()
        if digest == self._last_frame_hash:
            return
        self._last_frame_hash = digest
        await self.send({"type": "browser_frame", "data": base64.b64encode(frame).decode()})

    async def _frame_loop(self):
        """Stream ARIA's browser to the client: fast while working, slow when idle."""
        while True:
            busy = self._current_turn is not None and not self._current_turn.done()
            await asyncio.sleep(0.8 if busy else 4.0)
            try:
                await self._push_browser_frame()
            except Exception as e:
                logger.debug(f"Frame push failed: {e}")

    async def interrupt(self):
        turn = self._current_turn
        if turn and not turn.done():
            turn.cancel()
        # Drop queued commands that were waiting behind the interrupted one
        while not self._text_queue.empty():
            item = self._text_queue.get_nowait()
            if item[0] == "":  # keep the shutdown sentinel
                await self._text_queue.put(item)
                break
        self.session.interrupt()
        await self.send({"type": "notification", "message": "Interrupted.", "level": "info"})
        await self._on_state_change(SessionState.INTERRUPTED)
        self.session.resume()
        await self._on_state_change(SessionState.LISTENING)

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
                        await self.interrupt()

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

            # Voice command: Gemini Live already answers out loud, so only actions
            # are shown. Typed text: also send the agent's text response.
            on_text = None if from_voice else (lambda t: self._on_text(t, final=True))
            self._current_turn = asyncio.create_task(
                self.runner.run_turn(
                    user_message=content,
                    screenshot_b64=self._last_screenshot_b64,
                    on_text=on_text,
                    on_action=self._on_action,
                    on_state_change=self._on_state_change,
                )
            )
            try:
                await self._current_turn
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current and current.cancelling():
                    raise  # the handler itself is shutting down
                logger.info("Agent turn interrupted.")
            except Exception as e:
                logger.error(f"ADK turn error: {e}", exc_info=True)
                await self.send({"type": "error", "message": f"Agent error: {e}"})
                await self._on_state_change(SessionState.LISTENING)
            finally:
                self._current_turn = None
                await self._push_browser_frame()

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
        frame_task = asyncio.create_task(self._frame_loop())

        try:
            await receive_task
        except Exception as e:
            logger.error(f"Handler error: {e}")
        finally:
            for task in (text_proc_task, live_task, frame_task):
                task.cancel()
            if self._current_turn:
                self._current_turn.cancel()
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
