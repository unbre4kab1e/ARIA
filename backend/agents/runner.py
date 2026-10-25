"""
ADK Agent Runner — bridges the ARIA WebSocket session with the Google ADK agent.

Flow:
  1. Receives user messages from the WebSocket handler
  2. Runs them through the ADK InMemoryRunner (stateful, per-session)
  3. Streams text events back via callbacks
  4. ADK handles tool execution automatically

Interruption is done by cancelling the asyncio task running `run_turn`.
"""

import asyncio
import base64
import logging
from typing import Any

from google.adk.runners import InMemoryRunner
from google.adk.sessions import Session
from google.genai import types as genai_types

from agents.aria_agent import SESSION_STATE_KEY, aria_agent
from agents.tools.browser_tools import browser_controller
from services.session import ARIASession, SessionState

logger = logging.getLogger("aria.runner")

APP_NAME = "aria"


class ARIAAgentRunner:
    """
    One instance per ARIA session.
    Wraps ADK InMemoryRunner to handle multi-turn conversations.
    """

    def __init__(self, aria_session: ARIASession):
        self.aria_session = aria_session
        self._runner = InMemoryRunner(
            agent=aria_agent,
            app_name=APP_NAME,
        )
        self._adk_session: Session | None = None
        self._lock = asyncio.Lock()
        # Set when a turn is cancelled between a tool call and its response:
        # that history is invalid for Gemini, so a fresh ADK session is needed.
        self._needs_reset = False

    async def _create_adk_session(self):
        self._adk_session = await self._runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=self.aria_session.session_id,
            state={SESSION_STATE_KEY: self.aria_session.session_id},
        )
        logger.info(f"ADK session started: {self._adk_session.id}")

    async def start(self):
        """Initialize the ADK session."""
        await self._create_adk_session()
        try:
            await browser_controller.get_or_create_context(self.aria_session.session_id)
        except RuntimeError as e:
            logger.warning(f"Browser context not created: {e}")

    async def stop(self):
        """Clean up browser context."""
        await browser_controller.close_context(self.aria_session.session_id)
        logger.info(f"ADK runner stopped for session {self.aria_session.session_id}")

    async def run_turn(
        self,
        user_message: str,
        screenshot_b64: str | None = None,
        on_text: Any = None,
        on_action: Any = None,
        on_state_change: Any = None,
    ) -> str:
        if not self._adk_session:
            raise RuntimeError("Runner not started. Call start() first.")

        async with self._lock:
            if self._needs_reset:
                await self._create_adk_session()
                self._needs_reset = False

            self.aria_session.state = SessionState.THINKING
            self.aria_session.current_task = user_message
            if on_state_change:
                await on_state_change(SessionState.THINKING)

            # Build message with optional screenshot of the user's screen as context
            parts: list[genai_types.Part] = []
            if screenshot_b64:
                parts.append(genai_types.Part(text="[Screenshot of the user's screen, for context]"))
                parts.append(
                    genai_types.Part(
                        inline_data=genai_types.Blob(
                            mime_type="image/jpeg",
                            data=base64.b64decode(screenshot_b64),
                        )
                    )
                )
            parts.append(genai_types.Part(text=user_message))

            content = genai_types.Content(role="user", parts=parts)
            full_response = ""
            pending_tool_call = False

            try:
                async for event in self._runner.run_async(
                    user_id=self.aria_session.session_id,
                    session_id=self._adk_session.id,
                    new_message=content,
                ):
                    calls = event.get_function_calls()
                    if event.get_function_responses():
                        pending_tool_call = False
                    if calls:
                        pending_tool_call = True
                        # Tool call event — narrate the action
                        for call in calls:
                            self.aria_session.state = SessionState.ACTING
                            if on_state_change:
                                await on_state_change(SessionState.ACTING)

                            args = dict(call.args or {})
                            detail = _summarize_tool_call(call.name, args)
                            logger.info(f"Tool call: {call.name}({detail})")

                            if on_action:
                                await on_action(call.name, detail, args)

                            self.aria_session.add_to_history(
                                "action", f"{call.name}: {detail}"
                            )

                    elif event.is_final_response() and event.content and event.content.parts:
                        text = "".join(p.text for p in event.content.parts if p.text)
                        if text:
                            full_response += text
                            if on_text:
                                await on_text(text)

            except asyncio.CancelledError:
                logger.info("Turn cancelled (interrupted).")
                self._needs_reset = pending_tool_call
                raise
            finally:
                self.aria_session.current_task = None

            self.aria_session.state = SessionState.LISTENING
            if on_state_change:
                await on_state_change(SessionState.LISTENING)

            if full_response:
                self.aria_session.add_to_history("aria", full_response)
            return full_response


def _summarize_tool_call(name: str, args: dict | None) -> str:
    a = args or {}
    summaries: dict[str, str] = {
        "navigate_to":             a.get("url", ""),
        "click_element":           a.get("selector") or f"({a.get('x')},{a.get('y')})",
        "type_into_field":         f'"{str(a.get("text", ""))[:40]}" -> {a.get("selector", "")}',
        "scroll_page":             f'{a.get("direction", "down")} {a.get("amount", 500)}px',
        "press_keyboard_key":      a.get("key", ""),
        "read_page_content":       "extracting text",
        "wait_for_element":        a.get("selector", ""),
        "analyze_current_screen":  a.get("user_intent", "") or "analyzing screen",
        "describe_screen_element": f'({a.get("x")},{a.get("y")})',
        "search_web":              f'{a.get("query", "")} ({a.get("engine", "google")})',
        "get_current_url":         "checking current page",
        "get_current_time":        "checking time",
        "notify_user":             a.get("message", ""),
        "summarize_task_history":  "summarizing session",
    }
    return summaries.get(name, str(a)[:80])
