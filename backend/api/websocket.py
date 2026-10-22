"""
WebSocket handler for ARIA real-time sessions.

Architecture:
  - Audio goes to Gemini Live for voice conversation (audio in -> audio out)
  - Gemini Live decides when an action is needed and calls its
    `execute_browser_task` tool; the ADK agent runs it and the report goes
    back to Gemini Live, which tells the user the result out loud
  - Text typed in chat always goes to the ADK agent and gets a text response
  - The user's shared screen is passed to the agent as context (when it changed)
  - Frames of ARIA's own (headless) browser are streamed back as "browser_frame"
  - "interrupt" cancels the running agent turn
  - The agent runner belongs to the session, so reconnecting keeps its memory
    and browser
"""

import asyncio
import base64
import hashlib
import json
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from agents.runner import ARIAAgentRunner
from agents.tools.browser_tools import browser_controller
from api.auth import websocket_token_is_valid
from services.gemini_live import gemini_live_service
from services.session import ARIASession, SessionState, session_manager

logger = logging.getLogger("aria.ws")

# Close codes understood by the frontend: don't retry these
CLOSE_UNAUTHORIZED = 4401
CLOSE_SESSION_NOT_FOUND = 4404

LIVE_MAX_CONSECUTIVE_FAILURES = 3


class AgentJob:
    """One command for the ADK agent. Voice jobs carry a future for the report."""

    def __init__(self, content: str, from_voice: bool):
        self.content = content
        self.from_voice = from_voice
        self.result: asyncio.Future | None = (
            asyncio.get_running_loop().create_future() if from_voice else None
        )

    def resolve(self, value: dict[str, Any]):
        if self.result and not self.result.done():
            self.result.set_result(value)


class ARIAWebSocketHandler:
    def __init__(self, websocket: WebSocket, session: ARIASession):
        self.ws = websocket
        self.session = session

        self._last_screenshot_b64: str | None = None
        self._last_screenshot_hash: str | None = None
        self._sent_screenshot_hash: str | None = None
        self._jobs: asyncio.Queue[AgentJob | None] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
        self._audio_chunk_count = 0
        self._current_turn: asyncio.Task | None = None
        self._current_job: AgentJob | None = None
        self._last_frame_hash: str | None = None
        self._closed = False

    @property
    def runner(self) -> ARIAAgentRunner:
        return self.session.runner

    # --- Send helpers ---

    async def send(self, payload: dict[str, Any]):
        if self._closed:
            return
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

    # --- Live preview of ARIA's browser ---

    async def _push_browser_frame(self):
        shot = await browser_controller.frame_jpeg(self.session.session_id)
        if not shot:
            return
        frame, url, title = shot
        digest = hashlib.md5(frame).hexdigest()
        if digest == self._last_frame_hash:
            return
        self._last_frame_hash = digest
        await self.send({
            "type": "browser_frame",
            "data": base64.b64encode(frame).decode(),
            "url": url,
            "title": title,
        })

    async def _frame_loop(self):
        """Stream ARIA's browser to the client: fast while working, slow when idle."""
        while True:
            busy = self._current_turn is not None and not self._current_turn.done()
            await asyncio.sleep(0.8 if busy else 4.0)
            try:
                await self._push_browser_frame()
            except Exception as e:
                logger.debug(f"Frame push failed: {e}")

    # --- Interruption ---

    async def interrupt(self):
        turn = self._current_turn
        if turn and not turn.done():
            turn.cancel()
        # Drop queued commands that were waiting behind the interrupted one
        while not self._jobs.empty():
            job = self._jobs.get_nowait()
            if job is None:  # keep the shutdown sentinel
                await self._jobs.put(None)
                break
            job.resolve({"status": "interrupted", "report": "The user interrupted this task."})
        self.session.interrupt()
        await self.send({"type": "notification", "message": "Interrupted.", "level": "info"})
        await self._on_state_change(SessionState.INTERRUPTED)
        self.session.resume()
        await self._on_state_change(SessionState.LISTENING)

    # --- Gemini Live callbacks ---

    async def _on_user_speech(self, text: str):
        """Called when Gemini Live transcribes user speech: show it and log it."""
        text = text.strip()
        if not text:
            return
        self.session.add_to_history("user", text)
        await self.send({"type": "text", "content": text, "final": True, "role": "user"})

    async def _on_live_text(self, text: str, final: bool = True, role: str = "aria"):
        """Text from Gemini Live output transcription — show in chat as transcript."""
        await self.send({"type": "text", "content": text, "final": final, "role": role})
        if final and text:
            self.session.add_to_history("aria", text)

    async def _on_live_tool_call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Gemini Live asked for a browser task: run it on the agent, return the report."""
        if name != "execute_browser_task":
            return {"status": "error", "error": f"Unknown tool {name}"}
        instruction = str(args.get("instruction", "")).strip()
        if not instruction:
            return {"status": "error", "error": "Empty instruction"}
        logger.info(f"Voice task: {instruction!r}")
        job = AgentJob(instruction, from_voice=True)
        await self._jobs.put(job)
        return await job.result

    async def _on_live_tool_cancel(self, ids: list[str]):
        """Gemini Live dropped its pending call (the user moved on): stop the agent."""
        if self._current_job and self._current_job.from_voice:
            turn = self._current_turn
            if turn and not turn.done():
                turn.cancel()

    # --- Inbound receive loop ---

    async def _receive_loop(self):
        try:
            while True:
                raw = await self.ws.receive_text()
                msg = json.loads(raw)

                match msg.get("type"):
                    case "audio":
                        chunk = base64.b64decode(msg["data"])
                        if self._audio_chunk_count % 200 == 0:
                            logger.debug(f"Audio chunk #{self._audio_chunk_count}: {len(chunk)} bytes")
                        self._audio_chunk_count += 1
                        if not self._audio_queue.full():
                            await self._audio_queue.put(chunk)

                    case "screenshot":
                        data = msg.get("data") or ""
                        self._last_screenshot_b64 = data
                        self._last_screenshot_hash = hashlib.md5(data.encode()).hexdigest()

                    case "text":
                        content = msg.get("content", "").strip()
                        if content:
                            self.session.add_to_history("user", content)
                            await self._jobs.put(AgentJob(content, from_voice=False))

                    case "interrupt":
                        await self.interrupt()

                    case "ping":
                        self.session.touch()
                        await self.send({"type": "pong"})

        except WebSocketDisconnect:
            logger.info(f"Session {self.session.session_id} disconnected.")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self._closed = True
            await self._audio_queue.put(None)
            await self._jobs.put(None)  # sentinel

    # --- ADK agent processor ---

    def _screenshot_for_agent(self) -> str | None:
        """The user's screen, only when it changed since the agent last saw it."""
        if not self._last_screenshot_b64 or self._last_screenshot_hash == self._sent_screenshot_hash:
            return None
        self._sent_screenshot_hash = self._last_screenshot_hash
        return self._last_screenshot_b64

    async def _agent_loop(self):
        while True:
            job = await self._jobs.get()
            if job is None:
                break

            actions: list[str] = []

            async def on_action(action: str, detail: str, args: dict | None = None):
                actions.append(f"{action}: {detail}")
                await self._on_action(action, detail, args)

            # Voice: Gemini Live speaks the report. Typed text: show the agent's answer.
            on_text = None if job.from_voice else (lambda t: self._on_text(t, final=True))
            self._current_job = job
            self._current_turn = asyncio.create_task(
                self.runner.run_turn(
                    user_message=job.content,
                    screenshot_b64=self._screenshot_for_agent(),
                    on_text=on_text,
                    on_action=on_action,
                    on_state_change=self._on_state_change,
                )
            )
            try:
                report = await self._current_turn
                page = await browser_controller.get_current_url(self.session.session_id)
                job.resolve({
                    "status": "done",
                    "report": report or "Done.",
                    "actions": actions[-10:],
                    "current_page": page,
                })
            except asyncio.CancelledError:
                job.resolve({"status": "interrupted", "report": "The user interrupted this task."})
                current = asyncio.current_task()
                if current and current.cancelling():
                    raise  # the handler itself is shutting down
                logger.info("Agent turn interrupted.")
            except Exception as e:
                logger.error(f"ADK turn error: {e}", exc_info=True)
                job.resolve({"status": "error", "error": str(e)})
                await self.send({"type": "error", "message": f"Agent error: {e}"})
                await self._on_state_change(SessionState.LISTENING)
            finally:
                self._current_turn = None
                self._current_job = None
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
        if self.session.runner is None:
            self.session.runner = ARIAAgentRunner(self.session)
            await self.session.runner.start()
        else:
            logger.info(f"Session {self.session.session_id} reconnected: reusing agent and browser.")
        self.session.mark_connected()
        await self._on_state_change(SessionState.LISTENING)
        await self._push_browser_frame()

        receive_task = asyncio.create_task(self._receive_loop())
        agent_task = asyncio.create_task(self._agent_loop())
        live_task = asyncio.create_task(self._run_live_session())
        frame_task = asyncio.create_task(self._frame_loop())

        try:
            await receive_task
        except Exception as e:
            logger.error(f"Handler error: {e}")
        finally:
            for task in (agent_task, live_task, frame_task):
                task.cancel()
            if self._current_turn:
                self._current_turn.cancel()
            self.session.mark_disconnected()

    async def _run_live_session(self):
        """Run Gemini Live for voice, reconnecting (with resumption) when the server
        recycles the connection. Gives up after repeated failures: text still works."""
        resume_state: dict[str, Any] = {}
        failures = 0
        while not self._closed:
            started = time.monotonic()
            try:
                await gemini_live_service.run_session(
                    aria_session=self.session,
                    audio_input_stream=self._audio_generator(),
                    on_text=self._on_live_text,
                    on_audio=self._on_audio,
                    on_state_change=self._on_state_change,
                    on_user_speech=self._on_user_speech,
                    on_tool_call=self._on_live_tool_call,
                    on_tool_cancel=self._on_live_tool_cancel,
                    resume_state=resume_state,
                )
                failed = time.monotonic() - started < 5
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Gemini Live session error: {e}")
                failed = True

            if self._closed:
                return
            failures = failures + 1 if failed else 0
            if failures >= LIVE_MAX_CONSECUTIVE_FAILURES:
                await self.send({
                    "type": "notification",
                    "message": "Voice mode disconnected. Text commands still work.",
                    "level": "warning",
                })
                return
            logger.info("Reconnecting to Gemini Live...")
            await asyncio.sleep(1.5 * failures)


async def handle_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if not websocket_token_is_valid(websocket):
        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid or missing access token."}))
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    session = await session_manager.get(session_id)
    if not session:
        await websocket.send_text(
            json.dumps({"type": "error", "message": "Session not found or expired."})
        )
        await websocket.close(code=CLOSE_SESSION_NOT_FOUND)
        return

    await websocket.send_text(json.dumps({"type": "state", "state": SessionState.IDLE.value}))

    handler = ARIAWebSocketHandler(websocket, session)
    await handler.run()
